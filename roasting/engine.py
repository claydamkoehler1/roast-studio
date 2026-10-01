import json
import math
import threading
import time
from .hardware import Bullet, LIMITS
from .automation import RecipeRunner, validate_steps
from .recipes import initial_settings
from .store import now


def number(value, low, high, label='Value'):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a number')
    try:
        value = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(label + ' must be a number') from exc
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be between {low} and {high}')
    return value


def integer(value, low, high, label='Value'):
    n = number(value, low, high, label)
    if n != int(n):
        raise ValueError(label + ' must be a whole number')
    return int(n)


def required(value, label='Name', limit=300):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label} is required (maximum {limit} characters)')
    return value.strip()


class Engine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.bullet = Bullet()
        self.active = None
        saved = store.all('SELECT data FROM workspace WHERE id=1')
        self.workspace = json.loads(saved[0]['data']) if saved else None
        if self.workspace:
            self.workspace['auto_record'] = False
        if self.workspace and self.workspace.get('roast_id'):
            self.workspace = None
            with store.db() as db:
                db.execute('DELETE FROM workspace WHERE id=1')
        self.sim = dict(ibts=25, bt=25, ror=0, power=7, fan=3, drum=9, machine_state='ready')
        self.last_tick = time.monotonic()
        self.speed = 1
        self.auto = False
        self.fired = set()
        self.error = ''
        self.runner = None
        self.stop = threading.Event()

    def save_workspace(self):
        with self.store.db() as db:
            if self.workspace:
                db.execute('INSERT OR REPLACE INTO workspace(id,data) VALUES (1,?)', (json.dumps(self.workspace),))
            else:
                db.execute('DELETE FROM workspace WHERE id=1')

    def prepare(self, data):
        with self.lock:
            if self.active:
                raise ValueError('Finish the active roast first')
            mode = data.get('mode', 'hardware')
            if mode not in ('practice', 'hardware'):
                raise ValueError('Choose Bullet R2 or practice')
            weight = number(data.get('green_g'), 200, 1000, 'Batch weight')
            lid = integer(data['lot_id'], 1, 1e12, 'Beans') if data.get('lot_id') else None
            if mode == 'hardware' and not lid:
                raise ValueError('Add your beans, then select the lot for this roast')
            if lid:
                lot = self.store.one('SELECT * FROM lots WHERE id=? AND archived=0', (lid,))
                if mode == 'hardware' and weight > lot['stock_g']:
                    raise ValueError('Not enough green coffee for this batch')
            pid = integer(data['profile_id'], 1, 1e12, 'Recipe') if data.get('profile_id') else None
            profile = self.store.one('SELECT * FROM profiles WHERE id=?', (pid,)) if pid else None
            steps = validate_steps(json.loads(profile['steps'])) if profile else []
            initial = initial_settings(steps)
            if not profile:
                for key in initial:
                    initial[key] = integer(data.get(key, initial[key]), *LIMITS[key], key)
            self.workspace = dict(mode=mode, name=required(data.get('name'), 'Batch name'),
                lot_id=lid, profile_id=pid, green_g=weight, seasoning=bool(data.get('seasoning')),
                preheat=integer(profile['preheat'] if profile else data.get('preheat', 230), 100, 310, 'Preheat'),
                initial=initial, steps=steps, stage='ready', control_mode='auto' if pid else 'manual', auto_record=False, created=now(), plan_id=data.get('plan_id'))
            self.runner = None
            self.save_workspace()
            return self.snapshot()

    def clear_workspace(self):
        with self.lock:
            if self.active:
                raise ValueError('Finish and save the active roast first')
            self.workspace = None
            self.save_workspace()
            return self.snapshot()

    def transition(self, action, expected_state=None):
        with self.lock:
            w = self.workspace
            if not w:
                raise ValueError('Begin a roast first')
            if w['mode'] == 'practice':
                state = w['stage']
                if expected_state and expected_state != state:
                    raise ValueError('Phase changed. Review the current phase before continuing.')
                if action == 'preheat' and state == 'ready':
                    w['stage'] = 'preheating'
                elif action == 'charge' and state == 'preheating':
                    w['stage'] = 'charge'
                elif action == 'record' and state == 'charge':
                    self.start(w)
                    self.sim.update(w['initial'])
                    w['stage'] = 'roasting'
                    w['roast_id'] = self.active['id']
                elif action == 'cool' and self.active and self.active['status'] == 'roasting':
                    self.drop()
                elif action == 'shutdown' and self.active and self.active['status'] == 'cooling':
                    w['stage'] = 'shutdown'
                else:
                    raise ValueError('That transition is not available in this phase')
            else:
                status = self.bullet.status()
                if not status['fresh']:
                    raise ValueError('Connect the R2 and wait for fresh telemetry')
                state = status['telemetry'].get('machine_state')
                if expected_state != state:
                    raise ValueError('The R2 changed phase. Check the display and try again.')
                if self.active and action not in ('cool', 'shutdown'):
                    raise ValueError('This batch is already recording')
                if action == 'record' and state == 'roasting':
                    self.start(w)
                    w['roast_id'] = self.active['id']
                elif action == 'preheat' and state == 'ready':
                    self.bullet.command('preheat', w['preheat'])
                    self.bullet.command('prs', expected_state=state)
                    w['auto_record'] = True
                elif action == 'charge' and state in ('preheating', 'stabilizing'):
                    self.bullet.command('prs', expected_state=state)
                    w['auto_record'] = True
                elif action == 'watch-charge' and state == 'charge':
                    if not status['armed']:
                        raise ValueError('Enable machine controls first')
                    w['auto_record'] = True
                elif action == 'roast' and state == 'charge':
                    self.bullet.command('prs', expected_state=state)
                    w['auto_record'] = True
                elif action == 'cool' and state == 'roasting' and self.active:
                    self.pause_automation('Cooling requested.')
                    self.bullet.command('prs', expected_state=state)
                elif action == 'shutdown' and state in ('cooldown', 'cooling') and self.active and self.active['status'] == 'cooling':
                    self.bullet.command('prs', expected_state=state)
                else:
                    raise ValueError('That transition is not available in this R2 phase')
            self.save_workspace()
            return self.snapshot()

    def pause_automation(self, reason='Paused by you.'):
        if self.runner and self.active and self.active['status'] == 'roasting':
            self.runner.pause(reason, self.event)
        self.auto = False

    def automation(self, enabled):
        with self.lock:
            if not self.active or self.active['status'] != 'roasting' or not self.runner or not self.runner.recipe:
                raise ValueError('No active recipe to control')
            if not enabled:
                self.pause_automation('Manual control.')
            else:
                status = dict(fresh=True,armed=True,telemetry=self.sim) if self.active['mode']=='practice' else self.bullet.status()
                if not status['fresh'] or not status['armed'] or status.get('pending') or status.get('error') or status['telemetry'].get('machine_state') != 'roasting':
                    raise ValueError('Wait for confirmed roasting telemetry and enable machine controls first')
                self.runner.resume(status['telemetry'], self.active['elapsed'], self.event)
                self.auto = True
            self.active['control_mode'] = 'auto' if enabled else 'manual'
            if self.workspace:
                self.workspace['control_mode'] = self.active['control_mode']
                self.save_workspace()
            return self.snapshot()

    def control_mode(self, mode):
        with self.lock:
            if mode not in ('auto', 'manual'):
                raise ValueError('Choose Auto or Manual')
            session = self.active or self.workspace
            if not session:
                raise ValueError('Begin a roast first')
            if mode == 'auto' and not session.get('profile_id'):
                raise ValueError('Auto requires a recipe')
            if self.active:
                if self.active['status'] != 'roasting':
                    raise ValueError('The roast is no longer running')
                if not self.active.get('profile_id'):
                    return self.snapshot()
                if mode == 'auto' and self.runner and self.runner.state in ('running', 'complete'):
                    return self.snapshot()
                return self.automation(mode == 'auto')
            self.workspace['control_mode'] = mode
            self.save_workspace()
            return self.snapshot()

    def start_worker(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop.is_set():
            # Progress a confirmed change on the next USB frame, not one second later.
            signal = getattr(self.bullet, 'telemetry_received', None)
            if signal is not None:
                signal.wait(0.25)
                signal.clear()
            elif self.stop.wait(0.25):
                break
            try:
                self.tick()
            except Exception as exc:
                with self.lock:
                    self.error = 'Recording error: ' + str(exc)
                    self.auto = False
                    self.bullet.arm(False)

    def start(self, data):
        with self.lock:
            if self.active:
                raise ValueError('Finish the current batch before starting another')
            mode = data.get('mode', 'practice')
            if mode not in ('practice', 'hardware'):
                raise ValueError('Choose practice or hardware mode')
            green = number(data.get('green_g'), 200, 1000, 'R2 batch weight')
            if mode == 'hardware':
                status = self.bullet.status()
                if not status['fresh'] or status['telemetry'].get('machine_state') != 'roasting':
                    raise ValueError('Start the physical roast first. Recording requires fresh telemetry in roasting mode.')
            initial_elapsed = status['telemetry'].get('machine_elapsed', 0) if mode == 'hardware' else 0
            name = required(data.get('name'), 'Batch name')
            lot_id = data.get('lot_id') or None
            pid = data.get('profile_id') or None
            plan_id = data.get('plan_id') or None
            initial = {key: integer(data.get('initial', {}).get(key, value), *LIMITS[key], key)
                       for key, value in dict(power=7, fan=3, drum=9).items()}
            with self.store.db() as db:
                db.execute('BEGIN IMMEDIATE')
                lot = db.execute('SELECT * FROM lots WHERE id=? AND archived=0', (lot_id,)).fetchone() if lot_id else None
                if mode == 'hardware' and not lot:
                    raise ValueError('Select a green coffee lot to record a real roast')
                if lot_id and not lot:
                    raise ValueError('Green lot not found')
                profile = db.execute('SELECT * FROM profiles WHERE id=?', (pid,)).fetchone() if pid else None
                if pid and not profile:
                    raise ValueError('Profile not found')
                steps = validate_steps(data.get('steps', json.loads(profile['steps']) if profile else []))
                if plan_id:
                    plan = db.execute("SELECT * FROM plans WHERE id=? AND status='planned'", (plan_id,)).fetchone()
                    if not plan or plan['lot_id'] != lot_id or abs(plan['batch_g']-green) > .01:
                        raise ValueError('Plan no longer matches this batch')
                if mode == 'hardware':
                    changed = db.execute('UPDATE lots SET stock_g=stock_g-? WHERE id=? AND stock_g>=?', (green, lot_id, green)).rowcount
                    if not changed:
                        raise ValueError('Not enough green coffee in this lot')
                rid = db.execute('INSERT INTO roasts(name,lot_id,profile_id,mode,status,started,green_g,cost_per_kg,seasoning) VALUES (?,?,?,?,?,?,?,?,?)',
                                 (name, lot_id, pid, mode, 'roasting', now(), green, lot['cost_per_kg'] if lot else 0, int(bool(data.get('seasoning'))))).lastrowid
                if mode == 'hardware':
                    db.execute('INSERT INTO movements(lot_id,roast_id,amount_g,reason,created) VALUES (?,?,?,?,?)', (lot_id, rid, -green, 'Roast charge', now()))
                    if plan_id:
                        db.execute("UPDATE plans SET status='roasted',roast_id=? WHERE id=?", (rid, plan_id))
                db.execute('INSERT INTO events(roast_id,elapsed,kind,value,created) VALUES (?,?,?,?,?)', (rid, 0, 'charge', 'Machine clock origin' if mode == 'hardware' else 'Recording started', now()))
                if initial_elapsed:
                    db.execute('INSERT INTO events(roast_id,elapsed,kind,value,created) VALUES (?,?,?,?,?)', (rid, initial_elapsed, 'note', 'Recording joined in progress; earlier telemetry is unavailable', now()))
            self.active = dict(id=rid, mode=mode, status='roasting', elapsed=initial_elapsed, name=name,
                               steps=steps, green_g=green, profile_id=pid,
                               control_mode=data.get('control_mode', 'auto' if pid else 'manual'))
            self.sim = dict(ibts=185, bt=170, ror=-40, power=7, fan=3, drum=9, machine_state='roasting')
            if mode == 'practice':
                if profile:
                    self.sim.update(initial_settings(steps))
                elif self.workspace is data and data.get('initial'):
                    for key, bounds in LIMITS.items():
                        self.sim[key] = integer(data['initial'].get(key), *bounds, key)
            self.last_tick = time.monotonic()
            self.fired = set()
            self.auto = False
            self.error = ''
            self.runner = None
            if pid or data.get('initial'):
                if not data.get('initial'):
                    initial = initial_settings(steps)
                self.runner = RecipeRunner(steps, initial, recipe=bool(pid))
                if pid and self.active['control_mode'] == 'manual':
                    self.runner.pause('Manual control.', self.event)
                elif initial_elapsed > 15:
                    self.runner.pause('Joined a roast in progress. Review settings, then resume future recipe steps.', self.event)
                self.auto = self.runner.state == 'running'
            if self.workspace and data is self.workspace:
                self.workspace['roast_id'] = rid
                self.workspace['auto_record'] = False
                self.save_workspace()
            self.tick(0)
            return self.store.roast(rid)

    def tick(self, forced_dt=None):
        with self.lock:
            t = time.monotonic()
            dt = min(t-self.last_tick, 5) if forced_dt is None else forced_dt
            self.last_tick = t
            if not self.active and self.workspace and self.workspace.get('auto_record') and self.workspace['mode'] == 'hardware':
                status = self.bullet.status()
                if not status['fresh'] or not status['armed'] or status.get('error'):
                    self.workspace['auto_record'] = False
                    self.save_workspace()
                elif status['telemetry'].get('machine_state') == 'roasting':
                    self.start(self.workspace)
                    return
            if not self.active or self.active['status'] != 'roasting':
                return
            a = self.active
            a['elapsed'] += dt * (self.speed if a['mode'] == 'practice' else 1)
            elapsed = a['elapsed']
            if a['mode'] == 'practice':
                # Training model, not a prediction of the physical Bullet.
                for _ in range(max(1, math.ceil(dt*self.speed))):
                    step = dt*self.speed/max(1, math.ceil(dt*self.speed))
                    if elapsed < 65:
                        rate = -(self.sim['ibts']-90)/22
                    else:
                        rate = max(-0.3, (self.sim['power']*0.061 - (self.sim['ibts']-100)*0.0016 - self.sim['fan']*.012))
                    self.sim['ibts'] += rate*step
                    self.sim['bt'] += (self.sim['ibts']-self.sim['bt'])*0.055*step
                    self.sim['ror'] = rate*60
                sample = {k: round(v, 2) if isinstance(v, float) else v for k, v in self.sim.items()}
                if self.runner and self.auto:
                    self.runner.tick(dict(fresh=True, armed=True, telemetry=sample), elapsed,
                                     lambda name, value: self.sim.update({name: value}), self.recipe_event)
                    self.auto = self.runner.state == 'running'
            else:
                status = self.bullet.status()
                if not status['fresh']:
                    self.pause_automation('Telemetry lost. Review the machine before resuming.')
                    if not self.error:
                        self.event('connection', 'Telemetry lost. Recording gap; operate the physical panel.')
                    self.error = 'Telemetry lost. No temperatures are being recorded. Use the physical panel.'
                    return
                if self.error.startswith('Telemetry lost'):
                    self.event('connection', 'Telemetry restored')
                    self.error = ''
                    status['telemetry']['gap_before'] = True
                sample = status['telemetry']
                if 'machine_elapsed' in sample:
                    machine_elapsed = sample['machine_elapsed']
                    if machine_elapsed < a['elapsed'] - dt - 2:
                        self.pause_automation('Machine clock reset. Use the physical panel.')
                    else:
                        a['elapsed'] = elapsed = machine_elapsed
                if sample.get('machine_state') in ('cooldown', 'cooling', 'shutdown'):
                    self.drop()
                    return
                if self.runner:
                    self.runner.tick(status, elapsed, lambda name, value: self.bullet.command(name, value), self.recipe_event)
                    self.auto = self.runner.state == 'running'
            with self.store.db() as db:
                db.execute('INSERT INTO samples(roast_id,elapsed,data) VALUES (?,?,?)', (a['id'], elapsed, json.dumps(sample)))
                db.execute('UPDATE roasts SET elapsed=? WHERE id=?', (elapsed, a['id']))

    def recipe_event(self, kind, value=''):
        if kind in ('yellow', 'first_crack'):
            if self.store.all('SELECT 1 FROM events WHERE roast_id=? AND kind=?', (self.active['id'], kind)):
                return  # A manually marked milestone must not pause the recipe.
        self.event(kind, value)

    def event(self, kind, value=''):
        with self.lock:
            if not self.active or self.active['status'] != 'roasting':
                raise ValueError('No roast is recording')
            if kind not in ('yellow', 'first_crack', 'first_crack_end', 'second_crack', 'note', 'control', 'connection', 'drop', 'popup', 'end_alert', 'recipe_step'):
                raise ValueError('Unknown event')
            rid = self.active['id']
            with self.store.db() as db:
                if kind in ('yellow', 'first_crack', 'first_crack_end', 'second_crack'):
                    if db.execute('SELECT 1 FROM events WHERE roast_id=? AND kind=?', (rid, kind)).fetchone():
                        raise ValueError('That milestone is already marked')
                    prior = {'first_crack_end': 'first_crack', 'second_crack': 'first_crack'}.get(kind)
                    if prior and not db.execute('SELECT 1 FROM events WHERE roast_id=? AND kind=?', (rid, prior)).fetchone():
                        raise ValueError('Mark first crack before this event')
                    if kind == 'yellow' and db.execute("SELECT 1 FROM events WHERE roast_id=? AND kind='first_crack'", (rid,)).fetchone():
                        raise ValueError('Yellowing must precede first crack')
                db.execute('INSERT INTO events(roast_id,elapsed,kind,value,created) VALUES (?,?,?,?,?)',
                           (rid, self.active['elapsed'], kind, str(value)[:3000], now()))

    def control(self, name, value, source='manual'):
        with self.lock:
            lo, hi = LIMITS.get(name, (0, 0))
            if name not in LIMITS:
                raise ValueError('Unknown control')
            value = integer(value, lo, hi, name)
            if not self.active or self.active['status'] != 'roasting':
                raise ValueError('Start recording a roast first')
            if source == 'manual':
                self.pause_automation('Manual adjustment. Resume when ready to follow future steps.')
            if self.active['mode'] == 'practice':
                self.sim[name] = value
            else:
                self.bullet.command(name, value)
            self.event('control', f'{source}: {name}={value}' + (' requested' if self.active['mode'] == 'hardware' else ''))

    def drop(self):
        with self.lock:
            if not self.active or self.active['status'] != 'roasting':
                raise ValueError('No roast is recording')
            self.event('drop', 'Roast ended; cool and weigh beans')
            self.active['status'] = 'cooling'
            if self.workspace:
                self.workspace['stage'] = 'cooling'
                self.save_workspace()
            self.auto = False
            if self.runner:
                self.runner.state = 'stopped'
                self.runner.queue.clear()
            with self.store.db() as db:
                db.execute("UPDATE roasts SET status='cooling',elapsed=?,ended=? WHERE id=?", (self.active['elapsed'], now(), self.active['id']))

    def finish(self, data):
        with self.lock:
            if not self.active or self.active['status'] != 'cooling':
                raise ValueError('Mark drop before saving the finished batch')
            weight = number(data.get('roasted_g'), 1, self.active['green_g'], 'Roasted weight')
            rid = self.active['id']
            with self.store.db() as db:
                db.execute("UPDATE roasts SET status='complete',roasted_g=?,notes=? WHERE id=?", (weight, str(data.get('notes', ''))[:10000], rid))
            self.active = None
            self.workspace = None
            self.save_workspace()
            self.auto = False
            self.runner = None
            return self.store.roast(rid)

    def snapshot(self):
        with self.lock:
            result = dict(active=dict(self.active) if self.active else None, hardware=self.bullet.status(),
                          speed=self.speed, auto=self.auto, automation=self.runner.snapshot() if self.runner else None,
                          error=self.error, workspace=dict(self.workspace) if self.workspace else None)
            if self.active:
                detail = self.store.roast(self.active['id'])
                result['samples'] = detail['samples']
                result['events'] = detail['events']
                result['telemetry'] = self.sim.copy() if self.active['mode'] == 'practice' else result['hardware']['telemetry']
            else:
                result.update(samples=[], events=[], telemetry=result['hardware']['telemetry'] if result['hardware']['fresh'] else {})
            return result
