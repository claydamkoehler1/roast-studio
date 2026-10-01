import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from roasting.server import App
from test_astra import recipe


class ConversationRecipeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name) / 'chat.sqlite3')
        self.a = self.app.astra
        self.initial_profiles = len(self.app.store.all('SELECT * FROM profiles'))
        self.c = self.a.create_conversation(dict(bean={'name': 'Washed Guatemala'}, batch_g=500, brew='Filter', goal='Balanced'))

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def run_replies(self, requests, replies, stderr=''):
        prompts = []
        class Process:
            returncode = 1 if stderr else 0
            def __init__(self, args, **kwargs):
                self.output = Path(args[args.index('-o') + 1])
            def communicate(self, prompt, timeout):
                prompts.append(prompt)
                if not stderr:
                    self.output.write_text(json.dumps(replies.pop(0)), encoding='utf-8')
                return '', stderr
            def poll(self):
                return self.returncode
        jobs = []
        with patch.object(self.a, 'status', return_value={'ready': True}), patch('roasting.astra.client', return_value=('codex', {})), patch('roasting.astra.subprocess.Popen', Process):
            for request in requests:
                job = self.app.post('/api/ai/chat', dict(conversation_id=self.c['id'], **request))
                self.a.thread.join(5)
                jobs.append(self.a.job(job['id']))
        return jobs, prompts

    def test_offer_accept_recipe_save_and_follow_up_share_one_conversation(self):
        jobs, prompts = self.run_replies([
            {'message': 'I like chocolate notes.'}, {'message': 'Yes, please.'}, {'message': 'Why this airflow?'}
        ], [
            dict(message='Would you like me to make a first-trial recipe?', source_ids=['r2-specs'], recipe=None),
            dict(message='Here is your first-trial recipe.', source_ids=['r2-specs'], recipe=recipe()),
            dict(message='The initial airflow balances heat retention with exhaust.', source_ids=['r2-specs'], recipe=None),
        ])
        self.assertTrue(all(j['status'] == 'complete' for j in jobs))
        self.assertIn('Would you like me to make', prompts[1])
        self.assertIn('previous_recipe', prompts[2])
        self.assertEqual(len(self.a.conversation(self.c['id'])['messages']), 6)
        # HTTP route IDs arrive as strings; SQLite JSON comparisons need the numeric ID.
        fetched = self.app.get('/api/ai/conversations/' + str(self.c['id']), {})
        self.assertEqual(len(fetched['jobs']), 3)
        self.assertIsNotNone(fetched['jobs'][1]['result']['recipe'])
        saved = self.a.save(jobs[1]['id'])
        self.assertEqual(saved, self.a.save(jobs[1]['id']))
        with self.assertRaises(ValueError):
            self.a.save(jobs[2]['id'])
        self.assertEqual(len(self.app.store.all('SELECT * FROM profiles')), self.initial_profiles + 1)
        self.assertEqual(self.app.store.all('SELECT * FROM roasts'), [])
        self.assertFalse(self.app.engine.bullet.status()['connected'])

    def test_invalid_attached_recipe_never_becomes_a_saveable_draft(self):
        bad = recipe()
        bad['steps'][0]['value'] = 14
        jobs, _ = self.run_replies([{'message': 'Make a recipe.'}], [dict(message='Ready.', source_ids=['r2-specs'], recipe=bad)])
        self.assertEqual(jobs[0]['status'], 'failed')
        self.assertEqual(len(self.a.conversation(self.c['id'])['messages']), 1)
        with self.assertRaises(ValueError):
            self.a.save(jobs[0]['id'])

    def test_experience_persists_and_applies_to_existing_conversation(self):
        self.assertEqual(self.app.store.settings()['astra_expertise'], 'beginner')
        jobs, prompts = self.run_replies([{'message':'Explain preheat.'}], [dict(message='Warm the empty drum to 392 °F.',source_ids=['r2-specs'],recipe=None)])
        self.assertEqual(jobs[0]['context']['expertise'], 'beginner')
        self.assertIn('Assume the person has never roasted', prompts[0])
        self.assertIn('human-readable prose must use Fahrenheit only', prompts[0])
        self.assertIn('MUST remain Celsius for the machine', prompts[0])
        self.app.post('/api/settings', {'astra_expertise':'advanced'})
        jobs, prompts = self.run_replies([{'message':'Explain the same choice in depth.'}], [dict(message='Consider retained drum heat.',source_ids=['r2-specs'],recipe=None)])
        self.assertEqual(jobs[0]['context']['expertise'], 'advanced')
        self.assertIn('quantitative reasoning', prompts[0])
        self.assertIn('Explain preheat.', prompts[0])
        with self.assertRaises(ValueError):
            self.app.post('/api/settings', {'astra_expertise':'unknown'})
        self.app.close()
        self.app = App(Path(self.temp.name) / 'chat.sqlite3')
        self.assertEqual(self.app.store.settings()['astra_expertise'], 'advanced')

    def test_retry_keeps_one_user_message_and_recovers_permissions_error(self):
        failed, _ = self.run_replies([{'message': 'Make a recipe.'}], [], stderr='Error: failed to initialize in-process app-server client: Access is denied. (os error 5)')
        self.assertIn('Windows blocked', failed[0]['error'])
        jobs, prompts = self.run_replies([{'retry_job_id': failed[0]['id']}], [dict(message='Ready.', source_ids=['r2-specs'], recipe=recipe())])
        self.assertEqual(jobs[0]['status'], 'complete')
        messages = self.a.conversation(self.c['id'])['messages']
        self.assertEqual([m['role'] for m in messages], ['user', 'assistant'])
        self.assertEqual(messages[0]['job_id'], jobs[0]['id'])
        context = jobs[0]['context']['conversation']
        self.assertEqual(sum(m['content'] == 'Make a recipe.' for m in context), 1)
        with self.assertRaises(ValueError):
            self.a.start(dict(conversation_id=self.c['id'], retry_job_id=failed[0]['id']))


if __name__ == '__main__':
    unittest.main()
