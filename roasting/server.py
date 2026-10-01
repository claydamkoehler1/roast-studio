import csv
import io
import json
import mimetypes
import os
import secrets
import sqlite3
import tempfile
import traceback
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .engine import Engine, number, integer, required
from .store import Store, now
from .instance import InstanceLock
from .astra import Astra
from .knowledge import SOURCES, VERSION
from .recipes import validate_steps, import_roastime, replay_recipe
from .runtime import database_path

ROOT = Path(__file__).resolve().parent.parent


class App:
    def __init__(self, path):
        self.instance_lock = InstanceLock(Path(path).resolve())
        try:
            self.store = Store(path)
        except Exception:
            self.instance_lock.close()
            raise
        self.engine = Engine(self.store)
        self.astra = Astra(self.store)
        self.token = secrets.token_urlsafe(32)

    def close(self):
        self.astra.close()
        self.engine.stop.set()
        if hasattr(self.engine, 'thread'):
            self.engine.thread.join(3)
        self.engine.bullet.disconnect()
        self.instance_lock.close()

    def get(self, path, query):
        s = self.store
        if path == '/api/bootstrap':
            return dict(app='roast-studio', token=self.token, settings=s.settings(), version='3.2.0', database=str(s.path))
        if path == '/api/ai/conversations':
            return self.astra.conversations()
        if path.startswith('/api/ai/conversations/'):
            return self.astra.conversation(path.split('/')[-1])
        if path == '/api/ai/status':
            return dict(self.astra.status(refresh=query.get('refresh') == ['1']), sources=SOURCES, knowledge_version=VERSION)
        if path == '/api/ai/jobs':
            return self.astra.jobs()
        if path.startswith('/api/ai/jobs/'):
            return self.astra.job(integer(path.split('/')[-1],1,1e12,'AI request'))
        if path == '/api/state':
            return self.engine.snapshot()
        if path == '/api/hardware/diagnostics':
            return self.engine.bullet.diagnostics()
        if path == '/api/data':
            return dict(lots=[dict(l, details=json.loads(l['details'])) for l in s.all('SELECT * FROM lots WHERE archived=0 ORDER BY id DESC')],
                        profiles=[dict(p, steps=json.loads(p['steps']), guidance=json.loads(p['guidance'])) for p in s.all('SELECT * FROM profiles ORDER BY id DESC')],
                        roasts=s.all('''SELECT r.*,l.name AS lot_name,
                            (SELECT elapsed FROM events WHERE roast_id=r.id AND kind='first_crack' LIMIT 1) AS fc,
                            (SELECT COALESCE(SUM(count*grams_each),0) FROM packages WHERE roast_id=r.id) AS packaged_g
                            FROM roasts r LEFT JOIN lots l ON r.lot_id=l.id ORDER BY r.id DESC'''),
                        plans=s.all('SELECT p.*,l.name AS lot_name FROM plans p JOIN lots l ON p.lot_id=l.id ORDER BY p.scheduled,p.id'),
                        maintenance=s.all('SELECT * FROM maintenance ORDER BY id DESC'),
                        packages=s.all('SELECT * FROM packages ORDER BY id DESC'))
        if path.startswith('/api/roasts/'):
            return s.roast(integer(path.split('/')[-1], 1, 1e12, 'Roast ID'))
        if path == '/api/movements':
            return s.all('SELECT m.*,l.name AS lot_name FROM movements m JOIN lots l ON l.id=m.lot_id ORDER BY m.id DESC LIMIT 500')
        raise ValueError('Endpoint not found')

    def post(self, path, d):
        s, e = self.store, self.engine
        if path == '/api/beans/import':
            return self.astra.import_bean(d)
        if path == '/api/beans/save':
            return self.astra.save_bean(d)
        if path == '/api/ai/conversations':
            return self.astra.create_conversation(d)
        if path == '/api/ai/conversations/update':
            return self.astra.update_conversation(d)
        if path == '/api/ai/chat':
            return self.astra.start(dict(d, task='chat'))
        if path == '/api/prepare':
            return e.prepare(d)
        if path == '/api/transition':
            return e.transition(d.get('action'), d.get('expected_state'))
        if path == '/api/automation':
            return e.automation(bool(d.get('enabled')))
        if path == '/api/control-mode':
            return e.control_mode(d.get('mode'))
        if path == '/api/workspace/cancel':
            return e.clear_workspace()
        if path == '/api/ai/generate':
            return self.astra.start(d)
        if path == '/api/ai/cancel':
            self.astra.cancel()
            return {'ok': True}
        if path == '/api/ai/save':
            return self.astra.save(d.get('id'))
        if path == '/api/start':
            return e.start(d)
        if path == '/api/event':
            e.event(d.get('kind'), d.get('value', ''))
        elif path == '/api/control':
            e.control(d.get('name'), d.get('value'))
        elif path == '/api/drop':
            if e.active and e.active['mode'] == 'hardware' and d.get('send_cooling'):
                e.bullet.command('prs')
            e.drop()
        elif path == '/api/finish':
            return e.finish(d)
        elif path == '/api/practice':
            with e.lock:
                if not e.active or e.active['mode'] != 'practice':
                    raise ValueError('Practice settings require an active practice roast')
                e.speed = integer(d.get('speed', e.speed), 1, 30, 'Playback speed')
                e.auto = bool(d.get('auto', e.auto))
        elif path == '/api/connect':
            e.bullet.connect()
        elif path == '/api/disconnect':
            if e.active and e.active['mode'] == 'hardware':
                raise ValueError('Finish recording before disconnecting')
            e.bullet.disconnect()
        elif path == '/api/arm':
            with e.lock:
                if not d.get('enabled'):
                    e.pause_automation('Machine controls disabled.')
                e.bullet.arm(bool(d.get('enabled')))
        elif path == '/api/machine':
            e.bullet.command(d.get('name'), d.get('value'))
        elif path == '/api/lots':
            stock = number(d.get('stock_g'), 0, 1e8, 'Green weight')
            cost = number(d.get('cost_per_kg'), 0, 10000, 'Landed cost per kg')
            name = required(d.get('name'))
            origin = required(d.get('origin'), 'Origin')
            process = required(d.get('process'), 'Process')
            details = d.get('details', {})
            if not isinstance(details, dict):
                raise ValueError('Bean details must be an object')
            details = json.dumps(details, allow_nan=False)
            if len(details) > 240000:
                raise ValueError('Bean context must be under 240,000 characters')
            with s.db() as db:
                if d.get('id'):
                    # Stock can only change through audited inventory movements.
                    if not db.execute('SELECT 1 FROM lots WHERE id=?', (d['id'],)).fetchone():
                        raise ValueError('Lot not found')
                    db.execute('UPDATE lots SET name=?,origin=?,process=?,supplier=?,cost_per_kg=?,notes=?,details=? WHERE id=?',
                               (name, origin, process, str(d.get('supplier', ''))[:300], cost, str(d.get('notes', ''))[:10000], details, d['id']))
                else:
                    lid = db.execute('INSERT INTO lots(name,origin,process,supplier,received,stock_g,cost_per_kg,notes,details) VALUES (?,?,?,?,?,?,?,?,?)',
                                     (name, origin, process, str(d.get('supplier', ''))[:300], str(d.get('received') or now()[:10])[:10], stock, cost, str(d.get('notes', ''))[:10000], details)).lastrowid
                    db.execute('INSERT INTO movements(lot_id,amount_g,reason,created) VALUES (?,?,?,?)', (lid, stock, 'Initial receipt', now()))
        elif path == '/api/stock':
            amount = number(d.get('amount_g'), -1e8, 1e8, 'Adjustment')
            reason = required(d.get('reason'), 'Adjustment reason')
            with s.db() as db:
                if not db.execute('UPDATE lots SET stock_g=stock_g+? WHERE id=? AND stock_g+?>=0', (amount, d.get('id'), amount)).rowcount:
                    raise ValueError('Lot missing or adjustment would make stock negative')
                db.execute('INSERT INTO movements(lot_id,amount_g,reason,created) VALUES (?,?,?,?)', (d['id'], amount, reason, now()))
        elif path == '/api/profiles/import':
            return import_roastime(d.get('recipe'))  # Preview only; saving uses /api/profiles.
        elif path == '/api/profiles/from-roast':
            return replay_recipe(s.roast(integer(d.get('id'),1,1e12,'Roast ID')), d.get('preheat'))
        elif path == '/api/profiles':
            steps = validate_steps(d.get('steps', []))
            ref = d.get('reference_roast_id') or None
            if ref:
                s.one('SELECT id FROM roasts WHERE id=?', (ref,))
            values = (required(d.get('name')), required(d.get('style'), 'Style'), integer(d.get('preheat'), 100, 310, 'Preheat'),
                      number(d.get('batch_g'), 200, 1000, 'Batch size'), str(d.get('notes', ''))[:10000], json.dumps(steps), ref)
            with s.db() as db:
                if d.get('id'):
                    original = db.execute('SELECT guidance FROM profiles WHERE id=?', (d['id'],)).fetchone()
                    if original:
                        guidance = json.loads(original['guidance'])
                        if guidance:
                            guidance['edited'] = True
                            db.execute('UPDATE profiles SET guidance=? WHERE id=?', (json.dumps(guidance), d['id']))
                    if not db.execute('UPDATE profiles SET name=?,style=?,preheat=?,batch_g=?,notes=?,steps=?,reference_roast_id=? WHERE id=?', values+(d['id'],)).rowcount:
                        raise ValueError('Profile not found')
                else:
                    pid = db.execute('INSERT INTO profiles(name,style,preheat,batch_g,notes,steps,reference_roast_id) VALUES (?,?,?,?,?,?,?)', values).lastrowid
                    if d.get('import_source'):
                        import_roastime(d['import_source'])  # Check the source before retaining it.
                        db.execute('UPDATE profiles SET guidance=? WHERE id=?',
                                   (json.dumps({'import': {'type': 'RoasTime R2', 'source': d['import_source'], 'created': now()}}), pid))
            return {'id': d.get('id') or pid}
        elif path == '/api/plans':
            s.one('SELECT id FROM lots WHERE id=? AND archived=0', (d.get('lot_id'),))
            with s.db() as db:
                db.execute('INSERT INTO plans(name,lot_id,profile_id,batch_g,scheduled) VALUES (?,?,?,?,?)',
                           (required(d.get('name')), d['lot_id'], d.get('profile_id') or None,
                            number(d.get('batch_g'), 200, 1000, 'Batch weight'), required(d.get('scheduled'), 'Date', 10)))
        elif path == '/api/plan/cancel':
            with s.db() as db:
                db.execute("UPDATE plans SET status='cancelled' WHERE id=? AND status='planned'", (d.get('id'),))
        elif path == '/api/roast/update':
            roast = s.one('SELECT * FROM roasts WHERE id=?', (d.get('id'),))
            score = number(d['score'], 0, 100, 'Cupping score') if d.get('score') not in ('', None) else None
            weight = number(d['roasted_g'], 1, roast['green_g'], 'Roasted weight') if d.get('roasted_g') not in ('', None) else roast['roasted_g']
            packaged = s.one('SELECT COALESCE(SUM(count*grams_each),0) AS g FROM packages WHERE roast_id=?', (roast['id'],))['g']
            if weight is not None and weight < packaged:
                raise ValueError('Weight cannot be less than already packaged coffee')
            status = 'complete' if roast['status'] == 'interrupted' and weight else roast['status']
            if roast['status'] in ('roasting', 'cooling'):
                raise ValueError('Finish the batch from Roast studio first')
            with s.db() as db:
                db.execute('UPDATE roasts SET notes=?,tasting=?,score=?,rest_days=?,roasted_g=?,status=? WHERE id=?',
                           (str(d.get('notes', roast['notes']))[:10000], str(d.get('tasting', roast['tasting']))[:10000], score,
                            integer(d.get('rest_days', 5), 0, 90, 'Rest days'), weight, status, roast['id']))
        elif path == '/api/packages':
            count = integer(d.get('count'), 1, 10000, 'Bag count')
            grams = number(d.get('grams_each'), 1, 10000, 'Bag weight')
            price = number(d.get('price_each'), 0, 10000, 'Price')
            with s.db() as db:
                db.execute('BEGIN IMMEDIATE')
                roast = db.execute('SELECT * FROM roasts WHERE id=?', (d.get('roast_id'),)).fetchone()
                if not roast or roast['status'] != 'complete' or roast['mode'] != 'hardware' or roast['seasoning']:
                    raise ValueError('Only completed, non-seasoning hardware batches can be packaged')
                used = db.execute('SELECT COALESCE(SUM(count*grams_each),0) FROM packages WHERE roast_id=?', (roast['id'],)).fetchone()[0]
                if count*grams > roast['roasted_g']-used+0.001:
                    raise ValueError('Not enough unpackaged roasted coffee')
                db.execute('INSERT INTO packages(roast_id,count,grams_each,price_each,created) VALUES (?,?,?,?,?)', (roast['id'], count, grams, price, now()))
        elif path == '/api/settings':
            settings = s.settings()
            bounds = dict(bag_g=(1, 10000), sale_price=(0, 10000), packaging=(0, 10000), energy=(0, 10000), fee_percent=(0, 100), loss_percent=(0, 60), labor_per_bag=(0, 10000), fixed_per_bag=(0, 10000))
            for key, value in d.items():
                if key not in settings:
                    raise ValueError('Unknown setting')
                if key in bounds:
                    settings[key] = number(value, *bounds[key], key)
                elif key == 'units':
                    if value not in ('C', 'F'):
                        raise ValueError('Units must be C or F')
                    settings[key] = value
                elif key == 'machine_seasoned':
                    if not isinstance(value, bool):
                        raise ValueError('Seasoning status must be true or false')
                    settings[key] = value
                elif key == 'astra_expertise':
                    if value not in ('beginner', 'intermediate', 'advanced'):
                        raise ValueError('Choose Beginner, Intermediate or Advanced')
                    settings[key] = value
                else:
                    settings[key] = required(value, 'Studio name', 80)
            with s.db() as db:
                for k, v in settings.items():
                    db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(v), k))
        elif path == '/api/maintenance':
            with s.db() as db:
                db.execute('INSERT INTO maintenance(task,notes,created) VALUES (?,?,?)', (required(d.get('task')), str(d.get('notes', ''))[:3000], now()))
        else:
            raise ValueError('Endpoint not found')
        return {'ok': True}


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[0]).startswith('POST'):
                super().log_message(fmt, *args)

        def send(self, body, content_type='application/json', status=200, filename=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def trusted(self):
            host = self.headers.get('Host', '')
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if host not in allowed:
                return False
            origin = self.headers.get('Origin')
            return not origin or origin == 'http://' + host

        def do_GET(self):
            try:
                if not self.trusted():
                    return self.send({'error': 'Local access only'}, status=403)
                url = urlparse(self.path)
                if url.path == '/api/backup':
                    with tempfile.TemporaryDirectory() as temp:
                        target = Path(temp)/'roasting.sqlite3'
                        app.store.backup(target)
                        return self.send(target.read_bytes(), 'application/vnd.sqlite3', filename='roast-studio-backup.sqlite3')
                if url.path.startswith('/api/export/'):
                    rid = integer(url.path.split('/')[-1], 1, 1e12)
                    roast = app.store.roast(rid)
                    fmt = parse_qs(url.query).get('format', ['json'])[0]
                    if fmt == 'csv':
                        output = io.StringIO(newline='')
                        cols = ['elapsed', 'ibts', 'bt', 'ror', 'power', 'fan', 'drum', 'pressure', 'watts']
                        writer = csv.DictWriter(output, fieldnames=cols, extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(roast['samples'])
                        return self.send(output.getvalue().encode(), 'text/csv', filename=f'roast-{rid}.csv')
                    return self.send(json.dumps(roast, indent=2).encode(), filename=f'roast-{rid}.json')
                if url.path.startswith('/api/'):
                    return self.send(app.get(url.path, parse_qs(url.query)))
                rel = url.path.lstrip('/') or 'index.html'
                target = (ROOT/'web'/rel).resolve()
                if not target.is_relative_to((ROOT/'web').resolve()) or not target.is_file():
                    return self.send({'error': 'Not found'}, status=404)
                mime = 'text/javascript' if target.suffix == '.js' else mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                return self.send(target.read_bytes(), mime)
            except ValueError as exc:
                self.send({'error': str(exc)}, status=400)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                traceback.print_exc()
                self.send({'error': 'Server error. See the local terminal log.'}, status=500)

        def do_POST(self):
            try:
                if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Roast-Token', ''), app.token):
                    return self.send({'error': 'Reload the local app to authorize this request'}, status=403)
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 1_000_000 or 'application/json' not in self.headers.get('Content-Type', ''):
                    return self.send({'error': 'A JSON body under 1 MB is required'}, status=400)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected a JSON object')
                if urlparse(self.path).path == '/api/shutdown':
                    with app.engine.lock:
                        if app.engine.active:
                            raise ValueError('Finish and save the active batch before stopping the server')
                        self.send({'ok': True})
                        threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                with app.engine.lock:
                    result = app.post(urlparse(self.path).path, data)
                self.send(result)
            except (ValueError, TypeError, KeyError, sqlite3.IntegrityError) as exc:
                self.send({'error': str(exc)}, status=400)
            except Exception as exc:
                traceback.print_exc()
                self.send({'error': str(exc)}, status=500)
    return Handler


def serve(port=8740, database=None):
    app = App(database or database_path())
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(app))
    app.engine.start_worker()
    print(f'Roast Studio is ready at http://127.0.0.1:{port}\nSQLite: {app.store.path}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.server_close()
