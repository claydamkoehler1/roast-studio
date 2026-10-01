import ast
import importlib.util
import json
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'.deps'))
from roasting.server import App, handler_for
from roasting.store import Store
from roasting.hardware import Bullet, command_packet, decode_frame


class FakeBullet:
    def __init__(self):
        self.fresh = True
        self.telemetry = dict(ibts=180.0, bt=168.0, ror=12.0, power=7, fan=3, drum=9, machine_state='roasting')

    def status(self):
        return dict(fresh=self.fresh, connected=True, telemetry=self.telemetry.copy(), armed=False)

    def arm(self, enabled):
        pass

    def disconnect(self):
        pass


class AppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name)/'test.sqlite3')
        self.s = self.app.store
        self.e = self.app.engine

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def lot(self, stock=1000):
        self.app.post('/api/lots', dict(name='Test Guatemala', origin='Guatemala', process='Washed', stock_g=stock, cost_per_kg=20))
        return self.s.all('SELECT * FROM lots')[0]['id']

    def start(self, mode='practice', lot=None, **extra):
        return self.e.start(dict(name='Test batch', mode=mode, green_g=500, lot_id=lot, **extra))

    def real(self, stock=1000, **extra):
        lid = self.lot(stock)
        self.e.bullet = FakeBullet()
        return lid, self.start('hardware', lid, **extra)

    def finish(self):
        self.e.tick(20)
        self.e.event('yellow')
        self.e.tick(20)
        self.e.event('first_crack')
        self.e.tick(20)
        self.e.drop()
        return self.e.finish({'roasted_g': 425, 'notes': 'Balanced'})

    def test_practice_end_to_end_does_not_consume_stock(self):
        lid = self.lot()
        r = self.start(lot=lid)
        self.e.control('power', 6)
        final = self.finish()
        self.assertEqual(final['status'], 'complete')
        self.assertGreaterEqual(len(final['samples']), 4)
        self.assertEqual([x['kind'] for x in final['events']], ['charge','control','yellow','first_crack','drop'])
        self.assertEqual(self.s.one('SELECT stock_g FROM lots WHERE id=?', (lid,))['stock_g'], 1000)
        with self.assertRaises(ValueError):
            self.app.post('/api/packages', dict(roast_id=r['id'],count=1,grams_each=340,price_each=17))

    def test_hardware_stock_deducted_once_and_packaging_limit(self):
        lid,r = self.real()
        with self.assertRaises(ValueError):
            self.start('hardware',lid)
        final = self.finish()
        self.assertEqual(self.s.one('SELECT stock_g FROM lots WHERE id=?',(lid,))['stock_g'],500)
        package = dict(roast_id=r['id'],count=1,grams_each=340.194,price_each=17)
        self.app.post('/api/packages',package)
        with self.assertRaises(ValueError):
            self.app.post('/api/packages',package)
        self.assertEqual(len(self.s.all('SELECT * FROM packages')),1)

    def test_insufficient_inventory_rolls_back_roast(self):
        lid=self.lot(400)
        self.e.bullet=FakeBullet()
        with self.assertRaises(ValueError):
            self.start('hardware',lid)
        self.assertEqual(self.s.all('SELECT * FROM roasts'),[])
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'],400)

    def test_duplicate_milestones_and_invalid_weights(self):
        self.start()
        with self.assertRaises(ValueError):
            self.e.event('second_crack')
        self.e.event('first_crack')
        with self.assertRaises(ValueError):
            self.e.event('first_crack')
        with self.assertRaises(ValueError):
            self.e.event('yellow')
        with self.assertRaises(ValueError):
            self.e.finish({'roasted_g':425})
        self.e.drop()
        for v in (0,501,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                self.e.finish({'roasted_g':v})

    def test_stale_hardware_creates_gap_not_fake_samples(self):
        self.real()
        count=len(self.s.all('SELECT * FROM samples'))
        self.e.bullet.fresh=False
        self.e.tick(10)
        self.e.tick(10)
        self.assertEqual(len(self.s.all('SELECT * FROM samples')),count)
        self.assertEqual(len(self.s.all("SELECT * FROM events WHERE kind='connection'")),1)
        self.e.bullet.fresh=True
        self.e.tick(10)
        self.assertEqual(len(self.s.all('SELECT * FROM samples')),count+1)
        self.assertEqual(self.e.error,'')

    def test_machine_cooling_ends_recording(self):
        self.real()
        self.e.bullet.telemetry['machine_state']='cooling'
        self.e.tick(1)
        self.assertEqual(self.e.active['status'],'cooling')
        self.assertEqual(self.s.one("SELECT COUNT(*) n FROM events WHERE kind='drop'")['n'],1)

    def test_restart_recovers_record_and_does_not_refund_consumed_beans(self):
        lid,r=self.real()
        self.e.tick(20)
        self.app.close()
        restarted=App(self.s.path)
        record=restarted.store.roast(r['id'])
        self.assertEqual(record['status'],'interrupted')
        self.assertTrue(record['samples'])
        self.assertEqual(restarted.store.one('SELECT stock_g FROM lots')['stock_g'],500)
        restarted.post('/api/roast/update',dict(id=r['id'],roasted_g=420,notes='Recovered',score=85,rest_days=5))
        self.assertEqual(restarted.store.roast(r['id'])['status'],'complete')
        restarted.close()

    def test_database_rejects_second_recorder(self):
        self.start()
        with self.assertRaises(ValueError):
            App(self.s.path)
        self.assertEqual(self.s.one('SELECT status FROM roasts')['status'],'roasting')

    def test_backup_is_consistent_and_restorable(self):
        self.lot()
        self.start()
        target=Path(self.temp.name)/'backup.sqlite3'
        self.s.backup(target)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM roasts').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM samples').fetchone()[0],1)
        db.close()

    def test_negative_adjustment_rolls_back(self):
        lid=self.lot(500)
        with self.assertRaises(ValueError):
            self.app.post('/api/stock',dict(id=lid,amount_g=-501,reason='Correction'))
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'],500)
        self.assertEqual(len(self.s.all('SELECT * FROM movements')),1)

    def test_practice_recipe_runs_once(self):
        self.app.post('/api/profiles',dict(name='Test recipe',style='Test',preheat=230,batch_g=500,steps=[dict(trigger='time',at=10,control='power',value=5)]))
        pid=self.s.all('SELECT id FROM profiles ORDER BY id DESC')[0]['id']
        self.start(profile_id=pid)
        self.app.post('/api/practice',dict(auto=True,speed=1))
        self.e.tick(15)
        self.e.tick(15)
        self.assertEqual(self.e.sim['power'],5)
        self.e.tick(1)  # Observe the simulated target confirmation.
        self.assertEqual(len(self.s.all("SELECT * FROM events WHERE kind='control' AND value='recipe: power=5 confirmed'")),1)

    def test_seasoning_cannot_be_packaged(self):
        _,r=self.real(seasoning=True)
        self.finish()
        with self.assertRaises(ValueError):
            self.app.post('/api/packages',dict(roast_id=r['id'],count=1,grams_each=100,price_each=17))

    def test_plan_completed_only_by_real_roast(self):
        lid=self.lot()
        self.app.post('/api/plans',dict(name='Planned',lot_id=lid,batch_g=500,scheduled='2026-09-15'))
        pid=self.s.one('SELECT id FROM plans')['id']
        self.start(lot=lid,plan_id=pid)
        self.finish()
        self.assertEqual(self.s.one('SELECT status FROM plans')['status'],'planned')
        self.e.bullet=FakeBullet()
        self.start('hardware',lid,plan_id=pid)
        self.assertEqual(self.s.one('SELECT status FROM plans')['status'],'roasted')

    def test_network_origin_and_token_enforcement(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.app))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base+'/api/bootstrap') as response:
                bootstrap = json.load(response)
                self.assertEqual(bootstrap['version'],'3.2.0')
                self.assertEqual(bootstrap['app'],'roast-studio')
            for headers in ({},{'X-Roast-Token':self.app.token,'Origin':'https://attacker.example'}):
                request=urllib.request.Request(base+'/api/settings',b'{"units":"C"}',headers={'Content-Type':'application/json',**headers})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,403)
            request=urllib.request.Request(base+'/api/settings',b'{"units":"C"}',headers={'Content-Type':'application/json','X-Roast-Token':self.app.token})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status,200)
            self.assertEqual(self.s.settings()['units'],'C')
            request=urllib.request.Request(base+'/api/bootstrap',headers={'Host':'attacker.example'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403)
            self.start()
            shutdown=urllib.request.Request(base+'/api/shutdown',b'{}',headers={'Content-Type':'application/json','X-Roast-Token':self.app.token})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(shutdown)
            self.assertEqual(error.exception.code,400)
            self.finish()
            with urllib.request.urlopen(shutdown) as response:
                self.assertEqual(response.status,200)
            thread.join(2)
            self.assertFalse(thread.is_alive())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class ProtocolTest(unittest.TestCase):
    def test_command_packets_match_artisan_reference(self):
        # Execute only the two pure CRC/packet methods from the pinned source;
        # no upstream constructor, driver reset, thread, or USB open is run.
        tree=ast.parse((ROOT/'research'/'aillio_r2_reference.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AillioR2')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('calculate_crc32','prepare_command')]
        safe=ast.Module(body=[ast.ClassDef(name='Reference',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
        namespace={}
        exec(compile(ast.fix_missing_locations(safe),'reference','exec'),namespace)
        reference=namespace['Reference']()
        for payload in ([0x30,1,0,0],[0x34,1,0xaa,0xaa],[0x34,2,0xaa,0xaa],[0x31,1,0xaa,0xaa],[0x32,2,0xaa,0xaa],[0x35,0,0,230]):
            self.assertEqual(command_packet(payload),reference.prepare_command(payload))

    def test_temperature_frame_and_invalid_data(self):
        frame=bytearray(64)
        frame[0]=0xa0
        for offset,value in ((4,190.5),(8,12.3),(12,32.0),(16,175.5),(20,9.0),(24,10.0),(28,2.5)):
            struct.pack_into('<f',frame,offset,value)
        frame[46],frame[48],frame[50],frame[51],frame[53],frame[59]=7,30,7,3,9,6
        result=decode_frame(frame)
        self.assertEqual(result['ibts'],190.5)
        self.assertEqual(result['machine_elapsed'],450)
        self.assertEqual(result['machine_state'],'roasting')
        struct.pack_into('<f',frame,4,float('nan'))
        with self.assertRaises(ValueError):decode_frame(frame)
        with self.assertRaises(ValueError):decode_frame(bytes(63))

    def test_controls_require_fresh_data_and_acknowledgment(self):
        b=Bullet()
        with self.assertRaises(ValueError):b.arm(True)
        b.device=object()
        b.updated=time.monotonic()
        b.latest=dict(power=7,fan=3,drum=9,machine_state='roasting')
        class Sink:
            def __init__(self):self.writes=[]
            def write(self,packet,timeout):self.writes.append(packet)
        b.ep_out=Sink()
        b.arm(True)
        with self.assertRaises(ValueError):b.command('power',5)
        b.command('power',6)
        self.assertEqual(len(b.ep_out.writes),1)
        self.assertEqual(b.latest['power'],7) # never fake confirmation
        with self.assertRaises(ValueError):b.command('fan',4)
        b.updated-=5
        self.assertFalse(b.status()['armed'])
        b.updated=time.monotonic()
        self.assertFalse(b.status()['armed']) # fresh readings never re-arm automatically


if __name__=='__main__':
    unittest.main(verbosity=2)
