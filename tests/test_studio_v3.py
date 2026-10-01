import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from roasting.server import App
from roasting.astra import validate_recipe
from test_astra import recipe
from test_app import FakeBullet


class StudioFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name)/'test.sqlite3')
        self.e, self.s, self.a = self.app.engine, self.app.store, self.app.astra

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_manual_practice_phases_and_reload(self):
        self.e.prepare(dict(name='Manual', mode='practice', green_g=400, preheat=225, power=6, fan=2, drum=9))
        self.assertEqual(self.e.workspace['stage'], 'ready')
        self.app.close()
        self.app = App(self.s.path)
        self.e, self.s = self.app.engine, self.app.store
        self.assertEqual(self.e.workspace['preheat'], 225)
        with self.assertRaises(ValueError):
            self.e.transition('record', 'ready')
        self.e.transition('preheat', 'ready')
        with self.assertRaises(ValueError):
            self.e.transition('charge', 'ready')
        self.e.transition('charge', 'preheating')
        self.e.transition('record', 'charge')
        self.assertEqual(self.e.sim['power'], 6)
        self.assertEqual(self.e.sim['fan'], 2)
        self.assertEqual(self.e.snapshot()['samples'][0]['power'], 6)
        with self.assertRaises(ValueError):
            self.e.clear_workspace()
        self.e.event('yellow')
        self.e.event('first_crack')
        self.e.drop()
        self.e.transition('shutdown', 'cooling')
        self.e.finish(dict(roasted_g=340))
        self.assertIsNone(self.e.workspace)
        self.assertEqual(self.s.all('SELECT * FROM workspace'), [])

    def test_real_preparation_does_not_deduct_and_stale_transition_fails(self):
        self.app.post('/api/lots', dict(name='Real beans', origin='Guatemala', process='Washed', stock_g=1000,cost_per_kg=20))
        lid = self.s.one('SELECT id FROM lots')['id']
        self.e.bullet = FakeBullet()
        self.e.prepare(dict(name='Real', mode='hardware',green_g=500,lot_id=lid))
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'],1000)
        with self.assertRaises(ValueError):
            self.e.transition('record','charge')
        self.e.transition('record','roasting')
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'],500)
        with self.assertRaises(ValueError):
            self.e.transition('record','roasting')
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'],500)

    def test_chat_context_persists_turns_and_generates_from_conversation(self):
        c = self.a.create_conversation(dict(bean={'name':'New coffee','origin':'Guatemala','process':'Washed'},batch_g=500,brew='Filter',goal='Chocolate',community_reference='A supplied community recipe: P7 F3 D9.'))
        replies = [dict(message='Try a balanced approach. Do you prefer filter or espresso?',source_ids=['rw-recipes'],recipe=None),
                   dict(message='I will retain your chocolate goal and use espresso.',source_ids=['r2-specs'],recipe=None), recipe()]
        prompts = []
        class Process:
            returncode = 0
            def __init__(self,args,**kwargs): self.output=Path(args[args.index('-o')+1])
            def communicate(self,prompt,timeout):
                prompts.append(prompt)
                self.output.write_text(json.dumps(replies.pop(0)),encoding='utf-8')
                return '', ''
            def poll(self): return 0
        with patch.object(self.a,'status',return_value={'ready':True}), patch('roasting.astra.client',return_value=('codex',{})), patch('roasting.astra.subprocess.Popen',Process):
            first = self.a.start(dict(conversation_id=c['id'],task='chat',message='I want chocolate notes.'))
            self.a.thread.join(5)
            second = self.a.start(dict(conversation_id=c['id'],task='chat',message='Espresso please.'))
            self.a.thread.join(5)
            final = self.a.start(dict(conversation_id=c['id']))
            self.a.thread.join(5)
        self.assertEqual(self.a.job(first['id'])['status'],'complete')
        self.assertEqual(self.a.job(second['id'])['status'],'complete')
        self.assertIn('I want chocolate notes.',prompts[-1])
        self.assertIn('Espresso please.',prompts[-1])
        self.assertIn('A supplied community recipe',prompts[-1])
        self.assertEqual(len(self.a.conversation(c['id'])['messages']),6)
        pid = self.a.save(final['id'])['id']
        self.assertEqual(json.loads(self.s.one('SELECT guidance FROM profiles WHERE id=?',(pid,))['guidance'])['conversation_id'],c['id'])
        with self.assertRaises(ValueError): self.a.save(first['id'])
        self.app.close()
        self.app = App(self.s.path)
        self.assertEqual(len(self.app.astra.conversation(c['id'])['messages']),6)

    def test_curve_requires_ordered_finite_points_and_old_recipes_still_load(self):
        validate_recipe(recipe(),500)
        r=recipe();r['target_curve']=[dict(elapsed=t,ibts=temp) for t,temp in [(0,180),(60,100),(300,155),(600,210)]]
        validate_recipe(r,500)
        r['target_curve'][2]['elapsed']=30
        with self.assertRaises(ValueError): validate_recipe(r,500)


if __name__=='__main__': unittest.main()
