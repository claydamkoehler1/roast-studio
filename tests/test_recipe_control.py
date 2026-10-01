import json
import struct
import tempfile
import time
import unittest
from pathlib import Path

from roasting.hardware import Bullet, command_packet, STATES
from roasting.server import App


class EmulatedUSB(Bullet):
    """Exercise the actual command encoder and telemetry acknowledgments, with no USB device."""
    def __init__(self):
        super().__init__()
        self.device = object()
        self.writes = []
        self.ep_out = self
        self.feed(machine_state='ready', power=5, fan=2, drum=7, ibts=25, bt=25, ror=0, machine_elapsed=0)

    def write(self, packet, timeout):
        assert packet == command_packet(packet[:4])
        self.writes.append(bytes(packet[:4]))

    def connect(self):
        pass

    def disconnect(self):
        self.device = None

    def feed(self, **changes):
        values = dict(self.latest, **changes)
        frame = bytearray(64)
        frame[0] = 0xa0
        for offset, key in ((4, 'ibts'), (8, 'ror'), (16, 'bt')):
            struct.pack_into('<f', frame, offset, values[key])
        seconds = int(values['machine_elapsed'])
        frame[46], frame[48] = seconds // 60, seconds % 60
        frame[50], frame[51], frame[53] = values['power'], values['fan'], values['drum']
        frame[59] = next(code for code, state in STATES.items() if state == values['machine_state'])
        self._accept_frame(frame)

    def acknowledge(self):
        if self.pending:
            key, value, _ = self.pending
            self.feed(**{key: value})
        else:
            self.feed()


class RecipeControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name) / 'automation.sqlite3')
        self.e, self.s = self.app.engine, self.app.store
        self.b = self.e.bullet = EmulatedUSB()
        self.b.arm(True)
        self.app.post('/api/lots', dict(name='Control test', origin='Guatemala', process='Washed', stock_g=1000, cost_per_kg=20))
        self.lid = self.s.one('SELECT id FROM lots')['id']
        self.steps = [dict(trigger='time', at=0, control='power', value=7),
                      dict(trigger='time', at=10, control='power', value=4),
                      dict(trigger='ibts', at=160, control='fan', value=5),
                      dict(trigger='time', at=180, control='power', value=3)]
        self.app.post('/api/profiles', dict(name='Automatic test', style='Balanced', preheat=230, batch_g=500, steps=self.steps))
        self.pid = self.s.one('SELECT id FROM profiles ORDER BY id DESC')['id']
        self.e.prepare(dict(name='Automatic test batch', mode='hardware', lot_id=self.lid, profile_id=self.pid, green_g=500))

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def begin(self):
        self.e.transition('preheat', 'ready')
        self.b.acknowledge()
        self.b.feed(machine_state='charge')
        self.e.transition('roast', 'charge')
        self.b.acknowledge()
        self.e.tick(0)

    def settle(self, count=24):
        for _ in range(count):
            self.b.acknowledge()
            self.e.tick(0)

    def test_progress_reports_pending_and_confirmed_steps(self):
        self.begin()
        self.assertTrue(self.e.runner.snapshot()['initializing'])
        self.settle()
        snapshot = self.e.runner.snapshot()
        self.assertFalse(snapshot['initializing'])
        self.assertEqual(snapshot['last_completed_index'], 0)
        self.b.feed(machine_elapsed=10)
        self.e.tick(0)
        snapshot = self.e.runner.snapshot()
        self.assertEqual(snapshot['applying_index'], 1)
        self.assertEqual(snapshot['last_completed_index'], 0)
        self.assertNotIn(1, snapshot['completed'])
        self.settle()
        snapshot = self.e.runner.snapshot()
        self.assertIsNone(snapshot['applying_index'])
        self.assertEqual(snapshot['last_completed_index'], 1)
        self.assertIn(1, snapshot['completed'])

    def test_step_start_markers_are_persisted_once_at_execution(self):
        self.begin()
        self.settle()
        self.b.feed(machine_elapsed=10, ibts=135)
        self.e.tick(0)
        events = self.s.roast(self.e.active['id'])['events']
        markers = [json.loads(e['value']) for e in events if e['kind'] == 'recipe_step']
        self.assertEqual([m['step'] for m in markers], [1, 2])
        self.assertEqual(markers[-1]['elapsed'], 10)
        self.assertEqual(markers[-1]['ibts'], 135)
        self.assertEqual(markers[-1]['settings'], dict(power=4, fan=3, drum=9))
        self.assertNotIn(1, self.e.runner.done)  # marker is the start, not the final acknowledgement
        self.settle()
        events = self.s.roast(self.e.active['id'])['events']
        self.assertEqual(sum(e['kind'] == 'recipe_step' for e in events), 2)

    def test_manual_choice_before_roast_persists_and_prevents_recipe_writes(self):
        self.app.post('/api/control-mode', dict(mode='manual'))
        saved = json.loads(self.s.one('SELECT data FROM workspace WHERE id=1')['data'])
        self.assertEqual(saved['control_mode'], 'manual')
        self.begin()
        self.assertEqual(self.e.runner.state, 'paused')
        writes = len(self.b.writes)
        self.b.feed(machine_elapsed=20)
        self.settle()
        self.assertEqual(len(self.b.writes), writes)
        self.assertEqual(self.b.latest['power'], 5)
        self.e.control('power', 6)
        self.b.acknowledge()
        self.e.tick(0)
        self.assertEqual(self.b.latest['power'], 6)
        self.app.post('/api/control-mode', dict(mode='auto'))
        self.assertIn(1, self.e.runner.skipped)
        self.b.feed(machine_elapsed=90, ibts=165, ror=10)
        self.settle()
        self.assertEqual(self.b.latest['fan'], 5)
        self.assertEqual(self.b.latest['power'], 6)

    def test_switching_to_manual_stops_future_actions_and_auto_requires_recipe(self):
        self.begin()
        self.settle()
        self.app.post('/api/control-mode', dict(mode='manual'))
        self.assertFalse(self.e.auto)
        self.b.feed(machine_elapsed=20)
        writes = len(self.b.writes)
        self.settle()
        self.assertEqual(len(self.b.writes), writes)
        self.app.post('/api/control-mode', dict(mode='auto'))
        self.assertIn(1, self.e.runner.skipped)
        self.app.post('/api/control-mode', dict(mode='auto'))
        self.assertEqual(self.e.runner.state, 'running')
        with self.assertRaises(ValueError):
            self.app.post('/api/control-mode', dict(mode='other'))

    def test_full_phase_flow_records_once_and_runs_recipe(self):
        self.begin()
        self.assertEqual(self.b.writes[:3], [bytes([0x35, 0, 0, 230]), bytes([0x30, 1, 0, 0]), bytes([0x30, 1, 0, 0])])
        self.assertIsNotNone(self.e.active)
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'], 500)
        # A pending power command prevents all further writes until new telemetry confirms it.
        writes = len(self.b.writes)
        self.e.tick(0)
        self.assertEqual(len(self.b.writes), writes)
        self.settle()
        self.assertEqual([self.b.latest[k] for k in ('power', 'fan', 'drum')], [7, 3, 9])
        self.b.feed(machine_elapsed=10)
        self.settle()
        self.assertEqual(self.b.latest['power'], 4)
        self.b.feed(machine_elapsed=90, ibts=165, ror=10)
        self.settle()
        self.assertEqual(self.b.latest['fan'], 5)
        self.e.transition('cool', 'roasting')
        self.assertEqual(self.e.active['status'], 'roasting') # wait for the machine, not the click
        self.b.acknowledge()
        self.e.tick(0)
        self.assertEqual(self.e.active['status'], 'cooling')
        self.assertEqual(self.e.runner.state, 'stopped')
        self.e.transition('shutdown', 'cooldown')
        self.b.acknowledge()
        self.assertEqual(self.b.latest['machine_state'], 'shutdown')
        self.e.finish(dict(roasted_g=420))
        self.assertEqual(self.s.one('SELECT status FROM roasts')['status'], 'complete')
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM movements WHERE reason='Roast charge'")['n'], 1)

    def test_automatic_charge_detection_and_manual_initial_settings(self):
        self.e.clear_workspace()
        self.e.prepare(dict(name='Manual', mode='hardware', lot_id=self.lid, green_g=500, power=6, fan=4, drum=8))
        self.e.transition('preheat', 'ready')
        self.b.acknowledge()
        self.b.feed(machine_state='roasting') # bean detection; no PRS click from the app
        self.e.tick(0)
        self.settle()
        self.assertEqual([self.b.latest[k] for k in ('power','fan','drum')], [6,4,8])
        self.assertEqual(self.e.runner.state, 'complete')
        self.assertEqual(len(self.s.all('SELECT * FROM roasts')), 1)

    def test_manual_override_pauses_and_resume_skips_overdue(self):
        self.begin()
        self.settle()
        self.e.control('power', 6)
        self.assertEqual(self.e.runner.state, 'paused')
        self.b.acknowledge()
        self.b.feed(machine_elapsed=20)
        self.e.tick(0)
        self.e.automation(True)
        self.settle()
        self.assertEqual(self.b.latest['power'], 6)
        self.assertIn(1, self.e.runner.skipped)
        self.b.feed(machine_elapsed=180, ibts=155, ror=10)
        self.settle()
        self.assertEqual(self.b.latest['power'], 3)

    def test_temperature_steps_respect_explicit_time_without_global_ror_gate(self):
        self.begin()
        self.b.feed(ibts=220, ror=-20)
        self.settle()
        self.assertEqual(self.b.latest['fan'], 3)
        self.b.feed(machine_elapsed=4, ibts=165, ror=-2)
        self.settle()
        self.assertEqual(self.b.latest['fan'], 3)
        self.b.feed(machine_elapsed=5, ror=-2)
        self.settle()
        self.assertEqual(self.b.latest['fan'], 5)

    def test_telemetry_loss_does_not_resume_writes(self):
        self.begin()
        self.settle()
        self.b.updated -= 10
        self.e.tick(1)
        self.assertEqual(self.e.runner.state, 'paused')
        self.b.feed(machine_elapsed=20)
        self.b.arm(True)
        writes = len(self.b.writes)
        self.e.tick(1)
        self.assertEqual(len(self.b.writes), writes)
        self.assertEqual(self.e.runner.state, 'paused')

    def test_unconfirmed_command_pauses_without_retry(self):
        self.begin()
        key, value, _ = self.b.pending
        self.b.pending = (key, value, time.monotonic()-1)
        self.b.feed()
        self.e.tick(0)
        self.assertFalse(self.b.status()['armed'])
        self.assertEqual(self.e.runner.state, 'paused')
        writes = len(self.b.writes)
        self.e.tick(0)
        self.assertEqual(len(self.b.writes), writes)

    def test_physical_panel_override_pauses_recipe(self):
        self.begin()
        self.settle()
        self.b.feed(power=0, fan=12)
        self.e.tick(0)
        self.assertEqual(self.e.runner.state, 'paused')
        self.assertIn('Settings changed', self.e.runner.reason)

    def test_cooling_can_interrupt_setting_but_not_repeat_prs(self):
        self.begin()
        self.assertTrue(self.b.status()['pending_control'])
        self.e.transition('cool', 'roasting')
        with self.assertRaises(ValueError):
            self.e.transition('cool', 'roasting')
        self.b.acknowledge()
        self.e.tick(0)
        writes = len(self.b.writes)
        self.settle()
        self.assertEqual(len(self.b.writes), writes)

    def test_stale_phase_and_disarmed_commands_do_not_write(self):
        with self.assertRaises(ValueError): self.e.transition('preheat', 'charge')
        self.b.arm(False)
        with self.assertRaises(ValueError): self.e.transition('preheat', 'ready')
        self.assertEqual(self.b.writes, [])

    def test_preparation_is_immutable_and_restart_never_autostarts(self):
        self.e.transition('preheat', 'ready')
        self.b.acknowledge()
        with self.s.db() as db:
            db.execute('UPDATE profiles SET steps=? WHERE id=?', (json.dumps([dict(trigger='time', at=0, control='power', value=1)]), self.pid))
        self.app.close()
        self.app = App(self.s.path)
        self.e = self.app.engine
        self.assertFalse(self.e.workspace['auto_record'])
        self.assertEqual(self.e.workspace['steps'][0]['value'], 7)
        self.e.bullet = EmulatedUSB()
        self.e.bullet.feed(machine_state='roasting')
        self.e.bullet.arm(True)
        self.e.tick(0)
        self.assertIsNone(self.e.active)

    def test_invalid_recipe_is_rejected_before_inventory_or_commands(self):
        with self.s.db() as db:
            db.execute('UPDATE profiles SET steps=? WHERE id=?', (json.dumps([dict(trigger='time',at=0,control='power',value=14)]), self.pid))
        with self.assertRaises(ValueError):
            self.e.prepare(dict(name='Invalid', mode='hardware', lot_id=self.lid, profile_id=self.pid, green_g=500))
        self.assertEqual(self.b.writes, [])
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'], 1000)

    def test_late_join_requires_resume_and_does_not_apply_initial_heat(self):
        self.b.feed(machine_state='roasting', machine_elapsed=120, power=3, fan=4, ibts=180, ror=8)
        self.e.transition('record', 'roasting')
        self.assertEqual(self.e.runner.state, 'paused')
        self.assertEqual(self.b.writes, [])
        self.e.automation(True)
        self.settle()
        self.assertEqual(self.b.latest['power'], 3)
        self.assertEqual(self.e.runner.skipped, {0,1,2})

    def test_machine_error_disarms_and_stays_paused_after_error_clears(self):
        self.begin()
        self.settle()
        frame = bytearray(64)
        frame[0], frame[4] = 0xa1, 1
        self.b._accept_frame(frame)
        self.e.tick(0)
        self.assertFalse(self.b.status()['armed'])
        self.assertEqual(self.e.runner.state, 'paused')
        frame[4] = 0
        self.b._accept_frame(frame)
        self.b.arm(True)
        self.assertEqual(self.e.runner.state, 'paused')

    def test_phase_change_between_read_and_write_is_rejected(self):
        self.b.feed(machine_state='cooldown')
        with self.assertRaises(ValueError):
            self.b.command('prs', expected_state='roasting')
        self.assertEqual(self.b.writes, [])


if __name__ == '__main__':
    unittest.main()
