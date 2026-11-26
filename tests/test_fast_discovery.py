import json,tempfile,threading,unittest
from unittest.mock import patch
from opportunityos.store import Store,now
from opportunityos.agent import Agent
from opportunityos.ingestion import ingest_posts
from opportunityos.identity import group_duplicates,destination
from opportunityos.sources import ashby

class FastDiscovery(unittest.TestCase):
 def test_parallel_fetch_never_invokes_model(self):
  with tempfile.TemporaryDirectory() as directory:
   store=Store(directory)
   with store.db() as db:
    db.execute("INSERT INTO settings VALUES ('enabled_sources','[\"waymo\",\"figma\",\"cloudflare\"]')")
   barrier=threading.Barrier(3)
   def fetch(*args,**kwargs):
    self.assertTrue(kwargs['quick']);barrier.wait(timeout=3);return 2
   agent=Agent(store)
   with patch('opportunityos.agent.refresh',side_effect=fetch),patch('opportunityos.extraction.generate') as model:
    agent.start();agent.worker.join(5)
   self.assertFalse(agent.worker.is_alive());self.assertEqual(agent.progress['posts'],6);model.assert_not_called()
 def test_quick_scan_saves_without_loading_model(self):
  with tempfile.TemporaryDirectory() as directory:
   store=Store(directory)
   raw={'id':'test:1','raw_text':'AI Internship\nApply https://example.invalid/apply','source_link':'https://example.invalid/post'}
   with patch('opportunityos.extraction.generate',side_effect=AssertionError('AI must not run')):
    ingest_posts(store,'test',[raw],quick=True)
   with store.db() as db:item=json.loads(db.execute('SELECT payload FROM opportunities').fetchone()[0])
   self.assertEqual(item['extraction_fallback_reason'],'fast_scan')
 def test_duplicate_urls_preserve_evidence_and_existing_application(self):
  rows=[{'id':'a','state':'Listed','checked':now(),'application_link':'https://example.invalid/job?utm_source=a','source_link':'https://example.invalid/post1'},
        {'id':'b','state':'Listed','checked':now(),'application_link':'https://example.invalid/job','source_link':'https://example.invalid/post2'}]
  grouped=group_duplicates(rows,[{'opportunity':'b'}])
  self.assertEqual(grouped[0]['duplicate_of'],'b');self.assertEqual(len(grouped[1]['also_seen_at']),2)
  self.assertNotEqual(destination('https://example.invalid/?id=1'),destination('https://example.invalid/?id=2'))
 def test_ashby_filters_real_post_shapes(self):
  data={'jobs':[{'id':'test','title':'AI Internship','jobUrl':'https://jobs.ashbyhq.com/openai/test','descriptionPlain':'Undergraduate research','location':'Remote','isListed':True},
                {'id':'other','title':'Senior Developer','jobUrl':'https://jobs.ashbyhq.com/openai/other'},
                {'id':'closed','title':'AI Internship','jobUrl':'https://jobs.ashbyhq.com/openai/closed','isListed':False}]}
  with patch('opportunityos.sources.ashby.get_json',return_value=data):posts=ashby.fetch('ashby:openai')
  self.assertEqual(len(posts),1);self.assertEqual(posts[0]['organization'],'OpenAI')
