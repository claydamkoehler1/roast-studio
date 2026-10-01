import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from roasting.bean_pages import PageText, public_url, public_address, validate_document
from roasting.server import App


def document():
    return dict(name='Guatemala test coffee',origin='Guatemala',process='Washed',supplier='Test seller',
        summary='A balanced coffee with chocolate notes, according to the seller.',flavors=['Cocoa'],
        facts=[dict(label='Unusual seller attribute',value='Shade-dried on raised beds')],
        sections=[dict(title='A story unique to this coffee',body='A small cooperative prepared this lot.')],
        roasting_context='Seller suggests City to Full City. AI suggestion: validate on the R2 with a first trial.',
        unknowns=['No measured moisture reported.'])


class CaptureTest(unittest.TestCase):
    def test_page_capture_preserves_product_data_and_discards_executable_content(self):
        parser=PageText()
        parser.feed('<nav>Unrelated products</nav><script>alert("bad")</script><h1>Coffee</h1><p>Wet processed.</p>'
                    '<script type="application/ld+json">{"@type":"Product","name":"Coffee","description":"Rare detail"}</script>'
                    '<div>Altitude: 1700 m</div><style>display:none</style>')
        text=parser.text()
        self.assertIn('Rare detail',text)
        self.assertIn('1700 m',text)
        self.assertNotIn('alert',text)
        self.assertNotIn('Unrelated products',text)

    def test_rejects_local_destinations_and_credentials(self):
        for url in ['file:///etc/passwd','http://localhost/a','https://user:secret@example.com','https://example.com:1234']:
            with self.subTest(url=url),self.assertRaises(ValueError):public_url(url)
        self.assertEqual(public_url('https://example.com/product#notes'),'https://example.com/product')
        for address in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','::ffff:127.0.0.1']:
            with patch('roasting.bean_pages.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]):
                with self.assertRaises(ValueError):public_address('store.example',443)

    def test_document_keeps_arbitrary_characteristics_and_rejects_empty_extraction(self):
        self.assertEqual(validate_document(document())['facts'][0]['label'],'Unusual seller attribute')
        bad=document();bad['facts']=[];bad['sections']=[]
        with self.assertRaises(ValueError):validate_document(bad)


class ImportFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=App(Path(self.temp.name)/'beans.sqlite3')
        self.a,self.s=self.app.astra,self.app.store

    def tearDown(self):
        self.app.close();self.temp.cleanup()

    def test_import_worker_and_idempotent_save_keep_full_source_in_recipe_context(self):
        source='A rare coffee source detail that does not fit a fixed trait schema. Shade-dried, then rested for 40 days.'
        with patch.object(self.a,'_work'):
            job=self.a.import_bean(dict(text=source,url='https://example.com/coffee'))
            self.a.thread.join()
        prompts=[]
        class Process:
            returncode=0
            def __init__(self,args,**kwargs):self.output=Path(args[args.index('-o')+1])
            def communicate(self,prompt,timeout):
                prompts.append(prompt);self.output.write_text(json.dumps(document()),encoding='utf-8');return '', ''
            def poll(self):return 0
        with patch.object(self.a,'status',return_value={'ready':True}),patch('roasting.astra.client',return_value=('codex',{})),patch('roasting.astra.subprocess.Popen',Process),patch('roasting.astra.capture_page') as fetch:
            self.a._work(job['id'],job['context'])
            fetch.assert_not_called()
        self.assertEqual(self.a.job(job['id'])['status'],'complete')
        self.assertIn('untrusted DATA',prompts[0])
        first=self.a.save_bean(dict(id=job['id'],stock_g=1500,cost_per_kg=20))
        second=self.a.save_bean(dict(id=job['id'],stock_g=1500,cost_per_kg=20))
        self.assertEqual(first,second)
        self.assertEqual(len(self.s.all('SELECT * FROM lots')),1)
        self.assertEqual(len(self.s.all('SELECT * FROM movements')),1)
        context=self.a.context(dict(lot_id=first['id'],batch_g=500))
        self.assertEqual(context['bean']['details']['source']['text'],source)
        self.assertEqual(context['bean']['details']['document']['facts'][0]['value'],'Shade-dried on raised beds')
        self.assertNotIn('cost_per_kg',context['bean'])
        self.assertEqual(self.s.one('SELECT stock_g FROM lots')['stock_g'],1500)
        # Editing operational notes must not flatten or discard the imported document.
        lot=self.app.get('/api/data',{})['lots'][0]
        self.app.post('/api/lots',dict(lot,notes='A correction from the owner'))
        self.assertEqual(json.loads(self.s.one('SELECT details FROM lots')['details'])['source']['text'],source)
        self.app.close();self.app=App(self.s.path)
        self.assertEqual(self.app.astra.job(job['id'])['lot_id'],first['id'])

    def test_failed_fetch_never_creates_inventory_or_calls_model(self):
        with patch.object(self.a,'_work'):
            job=self.a.import_bean(dict(url='https://example.com/product'));self.a.thread.join()
        with patch.object(self.a,'status',return_value={'ready':True}),patch('roasting.astra.capture_page',side_effect=ValueError('Paste the page text instead.')),patch('roasting.astra.subprocess.Popen') as model:
            self.a._work(job['id'],job['context']);model.assert_not_called()
        self.assertEqual(self.a.job(job['id'])['status'],'failed')
        self.assertEqual(self.s.all('SELECT * FROM lots'),[])
        with self.assertRaises(ValueError):self.a.save_bean(dict(id=job['id']))


if __name__=='__main__':unittest.main()
