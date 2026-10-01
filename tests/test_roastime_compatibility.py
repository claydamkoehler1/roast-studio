"""Interoperability fixtures from inspected RoasTime 4.14.3 semantics.

These verify software behavior, not equivalence of physical USB writes.
"""
import copy
import json
import struct
import tempfile
import time
import unittest
from pathlib import Path
from roasting.recipes import import_roastime, validate_steps, as_group, matches, replay_recipe
from roasting.automation import RecipeRunner
from roasting.hardware import decode_frame
from roasting.server import App
from test_recipe_control import EmulatedUSB


def event(sensor, value, actions=None, comparison=0):
    return dict(trigger=sensor, condition=comparison, value=value, actions=actions or [])


def reference():
    # The structures and early thresholds mirror inspected Aillio Select rules.
    return dict(name='R2 compatibility fixture', deviceType='r2', tempMeasurement='C',
                preheatTemp=225, weight=200, startSettings=dict(power=6, fan=1, drum=9),
                events=[[event(0,54.9,[dict(action=0,value=8)]),event(3,5)],
                        [event(1,124,[dict(action=5,value=1)]),event(3,90)],
                        [event(1,161,[dict(action=6,value=1)]),event(3,330)]],
                endSettings=[event(0,208,[dict(action=4,value='Inspect and cool')]),event(3,465)])


class RecipeCompatibilityTest(unittest.TestCase):
    def test_early_ibts_rule_is_five_seconds_even_when_falling(self):
        g=import_roastime(reference())['steps'][3]
        self.assertFalse(matches(g,dict(ibts=60,bt=200,ror=-10),4))
        self.assertTrue(matches(g,dict(ibts=60,bt=200,ror=-10),5))
        self.assertFalse(matches(g,dict(ibts=54.8,bt=200),100))

    def test_probe_rule_requires_probe_and_time(self):
        g=import_roastime(reference())['steps'][4]
        self.assertFalse(matches(g,dict(ibts=180,bt=123),100))
        self.assertFalse(matches(g,dict(ibts=180,bt=125),89))
        self.assertTrue(matches(g,dict(ibts=90,bt=124),90))
        self.assertFalse(matches(g,dict(ibts=180),100))

    def test_less_than_and_fahrenheit_conversion(self):
        r=reference();r.update(tempMeasurement='F',preheatTemp=437)
        r['events']=[[event(1,248,[dict(action=2,value=5)],1),event(3,20)]]
        r['endSettings']=[]
        p=import_roastime(r);g=p['steps'][3]
        self.assertEqual(p['preheat'],225)
        self.assertTrue(matches(g,dict(bt=120,ibts=200),20))
        self.assertFalse(matches(g,dict(bt=121,ibts=200),20))

    def test_second_time_condition_minimum_and_explicit_end_deduplication(self):
        r=reference();r['events'][0][1]['value']=0
        self.assertEqual(import_roastime(r)['steps'][3]['conditions'][1]['value'],5)
        r['events'][0][0]['actions'].append(dict(action=4,value='Early end alert'))
        self.assertEqual(len(import_roastime(r)['steps']),6)

    def test_event_json_and_action_order_are_preserved(self):
        r=reference();r['events'][0][0]['actions']=[dict(action=2,value=4),dict(action=0,value=5),dict(action=3,value='Check aroma')]
        r['events']=json.dumps(r['events'])
        actions=import_roastime(r)['steps'][3]['actions']
        self.assertEqual([a['control'] for a in actions],['fan','power','popup'])

    def test_rejects_other_models_and_unsupported_actions_without_truncating(self):
        variants=[]
        for model in ('r1','r2pro','aio',None):
            r=reference();r['deviceType']=model;variants.append(r)
        r=reference();r['events'][0][0]['trigger']=2;variants.append(r)
        r=reference();r['events'][0][0]['actions']=[dict(action=99,value=1)];variants.append(r)
        r=reference();r['startSettings']['power']=11;variants.append(r)
        r=reference();r['events'][0][0]['value']=float('nan');variants.append(r)
        for r in variants:
            with self.subTest(recipe=r),self.assertRaises(ValueError):import_roastime(r)

    def test_p10_telemetry_and_actual_increment_packet(self):
        b=EmulatedUSB();b.feed(machine_state='roasting',power=9);b.arm(True)
        b.command('power',10)
        self.assertEqual(b.writes[-1],bytes.fromhex('3401aaaa'))
        b.acknowledge()
        self.assertEqual(b.status()['telemetry']['power'],10)
        self.assertFalse(b.status()['pending'])
        with self.assertRaises(ValueError):b.command('power',11)

    def test_idle_zero_speeds_and_timeout_without_another_frame(self):
        b=EmulatedUSB();b.feed(fan=0,drum=0)
        self.assertTrue(b.status()['fresh'])
        b.feed(machine_state='roasting',power=9,fan=1,drum=1);b.arm(True)
        b.command('power',10)
        b.pending=('power',10,time.monotonic()-1)
        self.assertFalse(b.status()['armed'])
        self.assertIn('not confirmed',b.status()['error'])

    def test_group_actions_run_once_end_alert_never_sends_prs(self):
        initial=dict(power=7,fan=3,drum=9)
        steps=[dict(conditions=[dict(sensor='bt',op='>=',value=120),dict(sensor='time',op='>=',value=5)],
                    actions=[dict(control='power',value=5),dict(control='fan',value=4),dict(control='yellow',value=1),dict(control='popup',value='Aroma'),dict(control='end_alert',value='Check beans')])]
        runner=RecipeRunner(steps,initial)
        sample=dict(initial,bt=125,ibts=180,machine_state='roasting');sent=[];log=[]
        def send(k,v):sent.append((k,v));sample[k]=v
        for _ in range(15):runner.tick(dict(fresh=True,armed=True,telemetry=sample),5,send,lambda k,v:log.append((k,v)))
        self.assertEqual(sent,[('power',6),('power',5),('fan',4)])
        self.assertEqual([k for k,v in log if k in ('yellow','popup','end_alert')],['yellow','popup','end_alert'])
        self.assertEqual(runner.state,'complete')

    def test_new_rules_use_explicit_conditions_legacy_guard_is_optional(self):
        step=dict(trigger='ibts',at=160,control='fan',value=5,min_time=90)
        group=as_group(validate_steps([step])[0])
        self.assertTrue(matches(group,dict(ibts=165,ror=-1),90))
        group['after_turn']=True
        self.assertFalse(matches(group,dict(ibts=165),90))
        self.assertTrue(matches(group,dict(ibts=165),90,rising=True))

    def test_condition_crossing_is_retained_while_usb_command_is_pending(self):
        rule=dict(conditions=[dict(sensor='bt',op='<=',value=120)],
                  actions=[dict(control='popup',value='Threshold observed')])
        runner=RecipeRunner([rule],dict(power=7,fan=3,drum=9))
        sample=dict(power=7,fan=3,drum=9,bt=119,machine_state='roasting')
        log=[]
        runner.tick(dict(fresh=True,armed=True,pending=True,telemetry=sample),5,
                    lambda *args:self.fail('Unexpected USB write'),lambda *args:log.append(args))
        sample['bt']=125
        for _ in range(3):
            runner.tick(dict(fresh=True,armed=True,telemetry=sample),6,
                        lambda *args:self.fail('Unexpected USB write'),lambda *args:log.append(args))
        self.assertEqual(log.count(('popup','Threshold observed')),1)

    def test_import_preview_save_prepare_and_milestones_in_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            app=App(Path(directory)/'test.sqlite3')
            try:
                count=len(app.store.all('SELECT id FROM profiles'))
                imported=app.post('/api/profiles/import',dict(recipe=reference()))
                self.assertEqual(len(app.store.all('SELECT id FROM profiles')),count)
                pid=app.post('/api/profiles',imported)['id']
                source=json.loads(app.store.one('SELECT guidance FROM profiles WHERE id=?',(pid,))['guidance'])
                self.assertEqual(source['import']['source']['deviceType'],'r2')
                app.post('/api/lots',dict(name='Fixture beans',origin='Guatemala',process='Washed',stock_g=1000,cost_per_kg=20))
                lid=app.store.one('SELECT id FROM lots')['id']
                e=app.engine;b=e.bullet=EmulatedUSB();b.arm(True)
                e.prepare(dict(name='Fixture roast',mode='hardware',lot_id=lid,profile_id=pid,green_g=200))
                self.assertEqual(e.workspace['initial'],dict(power=6,fan=1,drum=9))
                b.feed(machine_state='roasting');e.transition('record','roasting')
                def settle():
                    for _ in range(30):b.acknowledge();e.tick(0)
                settle();b.feed(machine_elapsed=5,ibts=60);settle()
                self.assertEqual(b.latest['power'],8)
                b.feed(machine_elapsed=90,bt=124);settle()
                b.feed(machine_elapsed=330,bt=161);settle()
                b.feed(machine_elapsed=465,ibts=208);settle()
                kinds=[v['kind'] for v in e.snapshot()['events']]
                self.assertEqual(kinds.count('yellow'),1)
                self.assertEqual(kinds.count('first_crack'),1)
                self.assertEqual(kinds.count('end_alert'),1)
                self.assertEqual(e.active['status'],'roasting')
                self.assertTrue(all(packet[0]!=0x30 for packet in b.writes))
                diagnostics=app.get('/api/hardware/diagnostics',{})
                self.assertFalse(diagnostics['hardware_validated'])
                self.assertTrue(any(t['direction']=='out' for t in diagnostics['trace']))
            finally:app.close()

    def test_replay_uses_observed_time_settings_and_end_alert(self):
        roast=dict(id=9,name='Reference',mode='hardware',status='complete',green_g=500,elapsed=500,
                   samples=[dict(elapsed=0,power=7,fan=3,drum=9),dict(elapsed=120,power=6,fan=3,drum=9),
                            dict(elapsed=120,power=5,fan=4,drum=9),dict(elapsed=400,power=4,fan=4,drum=9)])
        recipe=replay_recipe(roast,230)
        self.assertEqual(recipe['reference_roast_id'],9)
        self.assertEqual(recipe['steps'][1]['conditions'][0]['value'],120)
        self.assertEqual(recipe['steps'][1]['actions'],[dict(control='power',value=5),dict(control='fan',value=4)])
        self.assertEqual(recipe['steps'][-1]['actions'][0]['control'],'end_alert')
        self.assertTrue(all(c['sensor']=='time' for s in recipe['steps'] for c in s['conditions']))

    def test_replay_rejects_missing_start_and_telemetry_gaps(self):
        roast=dict(id=1,name='Partial',mode='hardware',status='complete',green_g=500,elapsed=500,
                   samples=[dict(elapsed=30,power=7,fan=3,drum=9)])
        with self.assertRaises(ValueError):replay_recipe(roast,230)
        roast['samples'][0].update(elapsed=0,gap_before=True)
        with self.assertRaises(ValueError):replay_recipe(roast,230)
        roast['samples'][0].pop('gap_before');roast['mode']='practice'
        with self.assertRaises(ValueError):replay_recipe(roast,230)

    def test_legacy_database_migration_preserves_hidden_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'legacy.sqlite3';app=App(path)
            with app.store.db() as db:
                db.execute('UPDATE profiles SET steps=?',(json.dumps([dict(trigger='ibts',at=160,control='power',value=5)]),))
                db.execute('PRAGMA user_version=4')
            app.close();app=App(path)
            try:
                step=json.loads(app.store.one('SELECT steps FROM profiles')['steps'])[0]
                self.assertEqual(step['min_time'],65)
                self.assertTrue(step['after_turn'])
            finally:app.close()


if __name__=='__main__':unittest.main()
