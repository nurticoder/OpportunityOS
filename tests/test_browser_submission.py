"""Real Playwright submission tests, restricted to a disposable loopback form."""
import json,threading,time,tempfile,unittest,importlib.util
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from opportunityos.store import Store,now
from opportunityos.browser_applications import BrowserApplications,_BROWSER
from opportunityos import browser_engine as engine

FORM='''<!doctype html><html><body><h1>Authorized local application test</h1><form method="post" enctype="multipart/form-data"><label>Full name<input name="name" required></label><label>Email<input name="email" type="email" required></label><label>CV<input name="cv" type="file" required></label><button>Submit application</button></form></body></html>'''
@unittest.skipUnless(importlib.util.find_spec("playwright") and Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists(), "Install requirements-browser.txt and Chrome for browser integration tests")
class BrowserSubmission(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=Store(self.temp.name);self.posts=[];self.confirm=True
  owner=self
  class FormServer(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    data=FORM.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(data)
   def do_POST(self):
    owner.posts.append(self.rfile.read(int(self.headers.get('Content-Length','0'))))
    data=('Your application has been received. LOCAL-TEST-confirmed' if owner.confirm else 'We could not confirm this action.').encode()
    self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(data)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),FormServer);threading.Thread(target=self.server.serve_forever,daemon=True).start()
  self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
  self.url=f'http://127.0.0.1:{self.server.server_port}';self.ident='manual:fixture';cv='a'*32
  folder=self.store.directory/'documents';folder.mkdir(mode=0o700);(folder/cv).write_text('A synthetic CV used only on the authorized local form.')
  with self.store.db() as db:
   for key,value in {'name':'Audit Applicant','email':'audit@example.invalid'}.items():db.execute('UPDATE facts SET value=?,verified=1,share=1 WHERE key=?',(value,key))
   item={'id':self.ident,'source_link':self.url,'application_link':self.url,'url':self.url,'title':'Local test','organization':'Audit','raw_text':'Synthetic test only','description':'Synthetic test only','location':'Remote','category':'Internship','title':'AI Internship'}
   db.execute("INSERT INTO opportunities VALUES (?,?,?,?,?,?,'Listed')",(self.ident,'manual',self.url,json.dumps(item),now(),now()))
   db.execute('INSERT INTO documents VALUES (?,?,?,?)',(cv,'Test CV.txt',50,now()))
   app={'draft':'Test application','method':'ChatGPT via Codex','fields':{},'missing':[],'document_ids':[cv],'version':1}
   db.execute("INSERT INTO applications VALUES (?,?,'Awaiting review',?)",(self.ident,json.dumps(app),now()))
  self.browser=BrowserApplications(self.store,test_origins=[self.url],headless=True,cloud_mapping=False)
  self.addCleanup(self.close)
 def close(self):
  self.browser.cancel_all()
  until=time.monotonic()+6
  while _BROWSER.locked() and time.monotonic()<until:time.sleep(.05)
 def wait(self,job,status,timeout=20):
  until=time.monotonic()+timeout
  while time.monotonic()<until:
   value=self.browser.jobs[job]
   if value['status']==status:return value
   if value['status']=='Needs attention' and status!='Needs attention':raise AssertionError(value['message'])
   time.sleep(.05)
  raise AssertionError(self.browser.jobs[job])
 def test_approval_required_and_confirmation_recorded_once(self):
  job=self.browser.start(self.ident);preview=self.wait(job,'Awaiting approval')
  self.assertEqual(self.posts,[])
  with self.assertRaises(ValueError):self.browser.control(job,'approve','bad-token')
  token=preview['approval_token'];self.browser.control(job,'approve',token)
  with self.assertRaises(ValueError):self.browser.control(job,'approve',token)
  self.wait(job,'Submitted');self.assertEqual(len(self.posts),1)
  self.assertIn(b'Test CV.txt',self.posts[0])
  with self.store.db() as db:self.assertEqual(db.execute('SELECT status FROM applications').fetchone()[0],'Submitted')
  with self.assertRaises(ValueError):self.browser.start(self.ident)
 def test_changed_profile_invalidates_approval(self):
  job=self.browser.start(self.ident);preview=self.wait(job,'Awaiting approval')
  with self.store.db() as db:db.execute("UPDATE facts SET value='changed@example.invalid' WHERE key='email'")
  self.browser.control(job,'approve',preview['approval_token'])
  self.wait(job,'Needs attention');self.assertEqual(self.posts,[])
 def test_no_confirmation_is_not_submitted_or_retried(self):
  self.confirm=False;job=self.browser.start(self.ident);preview=self.wait(job,'Awaiting approval')
  self.browser.control(job,'approve',preview['approval_token']);self.wait(job,'Unconfirmed',timeout=25)
  with self.store.db() as db:self.assertEqual(db.execute('SELECT status FROM applications').fetchone()[0],'Awaiting review')
  with self.assertRaises(ValueError):self.browser.start(self.ident)
  self.assertEqual(len(self.posts),1)
 def test_legal_consent_and_unknown_fields_are_not_guessed(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
   try:
    page=browser.new_page();page.set_content('<form><label>Full name<input required></label><label>I agree to terms<input type="checkbox" required></label><label>Passport number<input required></label></form>')
    result=engine.fill(page,self.store,{'answers':[]},use_cloud=False)
    self.assertFalse(page.locator('input[type=checkbox]').is_checked())
    self.assertIn('Passport number',result['missing']);self.assertTrue(any('declaration' in value for value in result['missing']))
    page.set_content('<form><label>I agree to marketing emails<input type="checkbox"></label></form>')
    optional=engine.fill(page,self.store,{'answers':[]},use_cloud=False)
    self.assertEqual(optional['missing'],[]);self.assertFalse(page.locator('input').is_checked())
   finally:browser.close()

 def test_email_preview_binds_actual_recipient(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
   try:
    page=browser.new_page();page.set_content('<div role="dialog"><span email="apply@example.invalid">Recipient</span><input name="subjectbox" value="Application"><div role="textbox" contenteditable="true">My application</div></div>')
    app={'email_to':'apply@example.invalid','document_ids':[]}
    preview=self.browser._snapshot('test',page,app,True)
    self.assertEqual(preview['missing'],[])
    page.locator('[email]').evaluate('el=>el.setAttribute("email","other@example.invalid")')
    changed=self.browser._snapshot('test',page,app,True)
    self.assertTrue(changed['missing']);self.assertNotEqual(engine.fingerprint(preview),engine.fingerprint(changed))
   finally:browser.close()

 def test_public_read_query_never_allows_mutation(self):
  url='https://jobs.ashbyhq.com/api/non-user-graphql'
  self.assertTrue(engine.read_only_request(url,json.dumps({'operationName':'ApiJobPosting','query':'query ApiJobPosting { job { title } }'})))
  self.assertFalse(engine.read_only_request(url,json.dumps({'operationName':'ApiJobPosting','query':'mutation ApiJobPosting { submit }'})))
  self.assertFalse(engine.read_only_request(url,json.dumps({'operationName':'SubmitApplication','query':'query Q { job { title } }'})))
  self.assertFalse(engine.read_only_request('https://example.invalid/api/non-user-graphql',json.dumps({'operationName':'ApiJobPosting','query':'query Q { title }'})))
