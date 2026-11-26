import copy,json,tempfile,time,unittest
from pathlib import Path
from opportunityos.connected_gmail import GmailApplications,call,tool_config,_matches,approve_request,preview,APP
from opportunityos.store import Store,now

class Mailbox:
 def __init__(self):self.calls=[];self.message=None;self.fail_send=False
 def __call__(self,action,args,*unused,**options):
  self.calls.append(action)
  if action=='get_profile':return {'email':'audit@example.invalid'}
  if action=='create_draft':
   self.message={'id':'message-1','label_ids':['DRAFT'],'payload':{'mime_type':'multipart/mixed','headers':[{'name':'To','value':args['to']},{'name':'Subject','value':args['subject']}],'parts':[{'mime_type':'text/plain','body':{'content':args['payload']['body']['content']}}]+[{'mime_type':'text/plain','filename':Path(p).name,'body':{'size':Path(p).stat().st_size}} for p in args.get('attachment_files',[])]}}
   return {'id':'draft-1','message':{'id':'message-1'}}
  if action=='list_drafts':return {'drafts':[{'draft_id':'draft-1','message_id':self.message['id']}],'next_page_token':None}
  if action=='read_email':return copy.deepcopy(self.message)
  if action=='send_draft':
   if not options.get('approved'):raise AssertionError('No explicit approval')
   if args!={'draft_id':'draft-1'}:raise AssertionError('Wrong draft')
   if self.fail_send:return {'id':'sent-1'}
   return {'id':'sent-1','label_ids':['SENT']}
  raise AssertionError(action)

class ConnectedGmail(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=Store(self.temp.name);self.mailbox=Mailbox();self.gmail=GmailApplications(self.store,runner=self.mailbox);self.opportunity='manual:email-test'
  folder=self.store.directory/'documents';folder.mkdir(mode=0o700);self.cv='a'*32;(folder/self.cv).write_text('Synthetic test CV')
  with self.store.db() as db:
   item={'title':'Synthetic email test','description':'A synthetic fixture for testing email only.','location':'Remote','application_link':'mailto:apply@example.invalid'}
   db.execute("INSERT INTO opportunities VALUES (?,?,?,?,?,?,'Listed')",(self.opportunity,'manual','https://example.invalid',json.dumps(item),now(),now()))
   db.execute('INSERT INTO documents VALUES (?,?,?,?)',(self.cv,'Test CV.txt',17,now()))
   app={'draft':'Application text','email_to':'apply@example.invalid','email_subject':'An application','email_body':'My CV is attached.','document_ids':[self.cv],'version':1}
   db.execute("INSERT INTO applications VALUES (?,?,'Awaiting review',?)",(self.opportunity,json.dumps(app),now()))
 def wait(self,ident):
  end=time.monotonic()+3
  while ident in self.gmail.events and time.monotonic()<end:time.sleep(.01)
  self.assertNotIn(ident,self.gmail.events);return self.gmail.jobs[ident]
 def prepared(self):
  ident=self.gmail.start(self.opportunity);job=self.wait(ident);self.assertEqual(job['status'],'Awaiting approval',job);return ident,job
 def test_saved_draft_cv_review_and_single_approved_send(self):
  ident,job=self.prepared();self.assertEqual(self.mailbox.calls.count('create_draft'),1);self.assertNotIn('send_draft',self.mailbox.calls)
  self.assertIn('Test CV.txt',str(job['fields']))
  with self.assertRaises(ValueError):self.gmail.control(ident,'approve','wrong')
  token=job['approval_token'];self.gmail.control(ident,'approve',token);self.wait(ident)
  self.assertEqual(job['status'],'Submitted')
  with self.assertRaises(ValueError):self.gmail.control(ident,'approve',token)
  self.assertEqual(self.mailbox.calls.count('send_draft'),1)
  with self.store.db() as db:self.assertEqual(db.execute('SELECT status FROM applications').fetchone()[0],'Submitted')
 def test_changed_remote_recipient_cannot_be_sent(self):
  ident,job=self.prepared();self.mailbox.message['payload']['headers'][0]['value']='other@example.invalid'
  self.gmail.control(ident,'approve',job['approval_token']);self.wait(ident)
  self.assertEqual(job['status'],'Needs attention');self.assertNotIn('send_draft',self.mailbox.calls)
  self.gmail.control(ident,'refresh');self.wait(ident)
  self.assertIsNone(job['approval_token']);self.assertTrue(job['missing'])
 def test_changed_profile_invalidates_saved_approval(self):
  ident,job=self.prepared()
  with self.store.db() as db:db.execute("UPDATE facts SET value='changed@example.invalid' WHERE key='email'")
  self.gmail.control(ident,'approve',job['approval_token']);self.wait(ident)
  self.assertEqual(job['status'],'Needs attention');self.assertNotIn('send_draft',self.mailbox.calls)
 def test_reopen_and_restart_reuse_external_draft(self):
  ident,job=self.prepared();restarted=GmailApplications(self.store,runner=self.mailbox)
  self.assertIsNone(restarted.jobs[ident]['approval_token']);self.assertEqual(restarted.jobs[ident]['status'],'Interrupted')
  second=restarted.start(self.opportunity)
  end=time.monotonic()+3
  while second in restarted.events and time.monotonic()<end:time.sleep(.01)
  self.assertEqual(self.mailbox.calls.count('create_draft'),1)
  self.assertEqual(restarted.jobs[second]['status'],'Awaiting approval')
 def test_missing_send_confirmation_never_marks_submitted_or_retries(self):
  ident,job=self.prepared();self.mailbox.fail_send=True;self.gmail.control(ident,'approve',job['approval_token']);self.wait(ident)
  self.assertEqual(job['status'],'Unconfirmed')
  with self.assertRaises(ValueError):self.gmail.start(self.opportunity)
  self.assertEqual(self.mailbox.calls.count('send_draft'),1)
  with self.store.db() as db:self.assertEqual(db.execute('SELECT status FROM applications').fetchone()[0],'Awaiting review')
 def test_stop_invalidates_pending_approval(self):
  ident,job=self.prepared();token=job['approval_token'];self.gmail.cancel_all()
  with self.assertRaises(ValueError):self.gmail.control(ident,'approve',token)
  self.assertNotIn('send_draft',self.mailbox.calls)
 def test_extra_recipients_and_unapproved_send_fail_closed(self):
  with self.assertRaises(ValueError):call('send_draft',{'draft_id':'draft-1'})
  self.assertFalse(_matches('create_draft',{'to':'x','bcc':'hidden@example.invalid'},{'to':'x'}))
  self.assertIn('gmail.create_draft',tool_config('create_draft'));self.assertNotIn('send_draft',tool_config('create_draft'))
 def test_provider_gate_rejects_wrong_draft_and_second_execution(self):
  params={'_meta':{'codex_approval_kind':'mcp_tool_call','connector_id':APP,'tool_name':'gmail.send_draft','tool_params':{'draft_id':'reviewed-draft'}}}
  self.assertFalse(approve_request(params,'send_draft',{'draft_id':'reviewed-draft'},False))
  self.assertFalse(approve_request(params,'send_draft',{'draft_id':'different-draft'},True))
  self.assertTrue(approve_request(params,'send_draft',{'draft_id':'reviewed-draft'},True))
  self.assertFalse(approve_request(params,'send_draft',{'draft_id':'reviewed-draft'},True,used=True))
 def test_real_gmail_nullable_mime_parts(self):
  message={'payload':{'mime_type':'multipart/mixed','body':None,'headers':[{'name':'To','value':'Audit <audit@example.invalid>'}],'parts':[{'mime_type':'text/plain','body':{'content':'Hello\r\n'},'parts':None},{'filename':'CV.pdf','body':{'size':42},'parts':None}]}}
  result=preview(message);self.assertEqual(result['body'],'Hello');self.assertEqual(result['to'],['audit@example.invalid']);self.assertEqual(result['attachments'],[{'name':'CV.pdf','size':42}])
 def test_expired_approval_requires_fresh_review(self):
  ident,job=self.prepared();job['approval_expires']=0
  with self.assertRaises(ValueError):self.gmail.control(ident,'approve',job['approval_token'])
  self.assertNotIn('send_draft',self.mailbox.calls)
 def test_expired_opportunity_cannot_be_sent_from_an_old_review(self):
  ident,job=self.prepared()
  with self.store.db() as db:
   item=json.loads(db.execute('SELECT payload FROM opportunities').fetchone()[0]);item['deadline']='2020-01-01';db.execute('UPDATE opportunities SET payload=?',(json.dumps(item),))
  self.gmail.control(ident,'approve',job['approval_token']);self.wait(ident)
  self.assertEqual(job['status'],'Needs attention');self.assertNotIn('send_draft',self.mailbox.calls)
 def test_unallowed_email_source_is_blocked_before_browser_or_connector(self):
  from opportunityos.browser_applications import BrowserApplications
  browser=BrowserApplications(self.store)
  with self.assertRaisesRegex(ValueError,'allow this source'):browser.start(self.opportunity)
  self.assertEqual(browser.gmail.jobs,{})
