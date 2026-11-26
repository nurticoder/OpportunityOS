import copy,json,os,tempfile,threading,unittest
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
from opportunityos import applications,documents,cloud_ai
from opportunityos.extraction import FIELDS,validate_fields
from opportunityos.ingestion import ingest_posts
from opportunityos.store import Store,now
from opportunityos.tasks import Tasks

RAW={'id':'telegram:fixture/1','source_link':'https://example.invalid/post','raw_text':'AI Internship\nOrganization: Aurora Lab\nDeadline: 15 December 2027\nNationality: Kyrgyzstan\nApply mailto:apply@example.invalid'}
def response():
 fields={key:{'value':'unknown','confidence':0,'evidence':''} for key in FIELDS}
 for key,value in [('title','AI Internship'),('organization','Aurora Lab'),('application_link','mailto:apply@example.invalid'),('apply_method','email')]:
  fields[key]={'value':value,'confidence':.99,'evidence':value if key!='apply_method' else 'mailto:apply@example.invalid'}
 opportunity={k:v for k,v in fields.items() if k not in {'nationality','country_of_study','level'}}
 opportunity['eligibility']={k:fields[k] for k in ('nationality','country_of_study','level')}
 return {'opportunity':opportunity,'application':{'draft':'I study AI at Audit University and am interested in this internship.','answers':[],'email_subject':'AI internship application','email_body':'Please consider my application. My CV is attached.','used_sources':['fact:university'],'missing_information':['Work authorization requires review']}}

class CloudPreparation(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=Store(self.temp.name)
  with self.store.db() as db:
   db.execute("INSERT INTO settings VALUES ('extraction_provider','\"regex\"')")
   for key,value in {'name':'Audit Applicant','email':'audit@example.invalid','university':'Audit University','program':'AI'}.items():db.execute('UPDATE facts SET value=?,verified=1,share=1 WHERE key=?',(value,key))
  ingest_posts(self.store,'manual',[RAW],quick=True)
 def test_cloud_package_regenerates_and_retains_history(self):
  provider=lambda *args,**kwargs:response()
  applications.prepare(self.store,RAW['id'],'First question',provider=provider)
  applications.prepare(self.store,RAW['id'],'Second question',provider=provider)
  with self.store.db() as db:app=json.loads(db.execute('SELECT payload FROM applications').fetchone()[0])
  self.assertEqual(app['prompt'],'Second question');self.assertEqual(app['version'],2)
  self.assertEqual(app['draft_history'][0]['prompt'],'First question')
  self.assertEqual(app['method'],'ChatGPT via Codex · human review required')
 def test_cv_read_and_unsent_email_attachment(self):
  ident='a'*32;folder=self.store.directory/'documents';folder.mkdir(mode=0o700)
  (folder/ident).write_text('Audit Applicant studies AI and built an educational app. This is a synthetic CV.')
  with self.store.db() as db:db.execute('INSERT INTO documents VALUES (?,?,?,?)',(ident,'Master CV.txt',80,now()))
  result=documents.context(self.store)
  self.assertEqual(len(result['documents']),1);self.assertFalse(self.store.facts()['skills']['verified'])
  applications.prepare(self.store,RAW['id'],provider=lambda *a,**k:response())
  message=BytesParser(policy=policy.default).parsebytes(applications.email_file(self.store,RAW['id']))
  self.assertEqual(message['To'],'apply@example.invalid');self.assertEqual(message['X-Unsent'],'1')
  self.assertEqual(next(message.iter_attachments()).get_filename(),'Master CV.txt')
 def test_contradicted_quote_is_rejected(self):
  doc=response()['opportunity']
  doc['deadline']={'value':'2027-12-25','confidence':.99,'evidence':'Deadline: 15 December 2027'}
  doc['eligibility']['nationality']={'value':['India'],'confidence':.99,'evidence':'Nationality: Kyrgyzstan'}
  fields=validate_fields(doc,RAW,.8)
  self.assertEqual(fields['deadline']['value'],'unknown');self.assertEqual(fields['nationality']['value'],'unknown')
 def test_no_paid_environment_fallback(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'fake','CODEX_API_KEY':'fake'}):
   self.assertNotIn('OPENAI_API_KEY',cloud_ai.environment());self.assertNotIn('CODEX_API_KEY',cloud_ai.environment())
 def test_cancellation_does_not_persist_application(self):
  cancel=threading.Event();cancel.set()
  with self.assertRaises(InterruptedError):applications.prepare(self.store,RAW['id'],cancel=cancel,provider=lambda *a,**k:response())
  with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM applications').fetchone()[0],0)
 def test_restart_does_not_restart_cloud_tasks(self):
  tasks=Tasks(self.store);ident='b'*32
  (tasks.folder/(ident+'.json')).write_text(json.dumps({'id':ident,'opportunity':RAW['id'],'status':'Running'}))
  restarted=Tasks(self.store)
  self.assertEqual(restarted.jobs[ident]['status'],'Interrupted')
 def test_unavailable_evidence_fails_closed(self):
  doc=response();doc['application']['used_sources']=['fact:invented-award']
  with self.assertRaises(ValueError):applications.prepare(self.store,RAW['id'],provider=lambda *a,**k:doc)
  with self.store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM applications').fetchone()[0],0)
