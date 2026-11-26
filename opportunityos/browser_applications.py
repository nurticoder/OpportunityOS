"""Persistent browser preparation and one-use, preview-bound submission approval."""
import hashlib,ipaddress,json,queue,re,secrets,threading,time
from pathlib import Path
from urllib.parse import urlsplit
from . import browser_engine as engine,documents
from .identity import destination
from .sources import BOARDS
from .store import now

_BROWSER=threading.Lock()

def public_url(url):
 p=urlsplit(url)
 if p.scheme!='https' or not p.hostname or p.username or p.password:return False
 try:return ipaddress.ip_address(p.hostname).is_global
 except ValueError:return p.hostname not in {'localhost'} and not p.hostname.endswith(('.local','.localhost'))

def application_hash(store,ident):
 with store.db() as db:row=db.execute('SELECT payload FROM applications WHERE opportunity=?',(ident,)).fetchone()
 if not row:raise ValueError('Prepare the application first')
 payload=json.loads(row['payload'])
 values={'application':{k:v for k,v in payload.items() if k not in {'browser_attempt'}},'facts':{k:[v['value'],v['verified'],v['share']] for k,v in store.facts().items()},'documents':[]}
 for doc_id in payload.get('document_ids',[]):
  doc,data=documents.document_bytes(store,doc_id);values['documents'].append([doc_id,hashlib.sha256(data).hexdigest()])
 return hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

class BrowserApplications:
 def __init__(self,store,test_origins=(),headless=False,cloud_mapping=True):
  from .connected_gmail import GmailApplications
  self.gmail=GmailApplications(store)
  self.store=store;self.jobs={};self.commands={};self.cancelled={};self.lock=threading.RLock()
  self.test_origins=set(test_origins);self.headless=headless;self.cloud_mapping=cloud_mapping
  self.folder=store.directory/'browser';self.folder.mkdir(mode=0o700,exist_ok=True)
  for file in self.folder.glob('*.json'):
   if not re.fullmatch(r'[a-f0-9]{32}',file.stem):continue
   try:
    job=json.loads(file.read_text());job['approval_token']=None
    if job.get('status') not in {'Submitted','Unconfirmed','Cancelled','Expired'}:job.update(status='Interrupted',message='Browser session ended. Start a new preparation; saved drafts and screenshots remain.')
    self.jobs[file.stem]=job
   except (OSError,ValueError):pass
 def update(self,ident,**values):
  with self.lock:
   self.jobs[ident].update(values,updated=now());job=dict(self.jobs[ident])
   target=self.folder/(ident+'.json');temp=target.with_suffix('.tmp')
   temp.write_text(json.dumps(job,ensure_ascii=False));temp.chmod(0o600);temp.replace(target)
  self.store.log('Browser application · '+str(values.get('status','updated')))
 def list(self):
  with self.lock:return sorted([dict(j,active=key in self.commands) for key,j in self.jobs.items()]+self.gmail.list(),key=lambda j:j.get('updated',''),reverse=True)[:30]
 def control(self,ident,action,token=None):
  if ident in self.gmail.jobs:return self.gmail.control(ident,action,token)
  with self.lock:
   if ident not in self.jobs or ident not in self.commands:raise ValueError('This browser session is closed. Start preparation again.')
   job=self.jobs[ident]
   if action=='cancel':self.cancelled[ident].set();return
   if action=='approve':
    if job.get('status')!='Awaiting approval' or job.get('missing') or not token or not secrets.compare_digest(job.get('approval_token') or '',token):raise ValueError('Review the current complete preview before submitting')
    job['approval_token']=None # Consume approval immediately, including on double-click.
   elif action!='refresh':raise ValueError('Unknown browser action')
   self.commands[ident].put(action)
 def cancel_all(self):
  self.gmail.cancel_all()
  with self.lock:
   for event in self.cancelled.values():event.set()
 def start(self,ident,cancel=None,use_browser=False):
  if cancel and cancel.is_set():raise InterruptedError()
  with self.store.db() as db:
   row=db.execute('SELECT a.payload,a.status,o.payload AS listing,o.source,o.checked,o.state FROM applications a JOIN opportunities o ON o.id=a.opportunity WHERE a.opportunity=?',(ident,)).fetchone()
  if not row:raise ValueError('Prepare an application package first')
  app=json.loads(row['payload']);item=json.loads(row['listing']);item.update(id=ident,source=row['source'])
  from datetime import datetime,timedelta,timezone
  from .evaluation import evaluate
  from .extraction import expired
  if row['state']!='Listed' or datetime.fromisoformat(row['checked'])<datetime.now(timezone.utc)-timedelta(days=7) or expired(item):raise ValueError('Recheck this opportunity with Prepare application before opening the browser')
  assessment=evaluate(item,self.store.facts(),self.store.settings()['weights'])
  if assessment['eligibility']=='Ineligible':raise ValueError('This opportunity conflicts with your verified profile: '+assessment['reason'])
  if row['status'] not in {'Awaiting review','Ready'}:raise ValueError('This application has already progressed; duplicate submission is blocked')
  if app.get('browser_attempt',{}).get('status')=='unconfirmed':raise ValueError('A previous submission outcome is unconfirmed. Check the portal before retrying.')
  if any(re.search(r'eligibility appears unmet|not eligible|graduation.*(?:unmet|conflict)',v,re.I) for v in app.get('missing',[])):
   raise ValueError('Resolve the eligibility conflict in the prepared package before opening an application')
  url=item.get('application_link') or item.get('url');origin='://'.join(urlsplit(url)[:2])
  email=bool(app.get('email_to'))
  if email:
   if item['source'] not in self.store.settings().get('source_allowlist',[]) and self.store.settings().get('browser_permission:'+ident)!=destination(url):
    raise ValueError('Review the email destination and allow this source before preparing its Gmail draft')
   if not use_browser:return self.gmail.start(ident)
  if not email:
   if not public_url(url) and origin not in self.test_origins:raise ValueError('Only public HTTPS application portals are supported')
   official=(item['source'] in BOARDS and urlsplit(url).hostname in {'jobs.ashbyhq.com','boards.greenhouse.io','job-boards.greenhouse.io','job-boards.eu.greenhouse.io'})
   if not official and item['source'] not in self.store.settings().get('source_allowlist',[]) and origin not in self.test_origins and self.store.settings().get('browser_permission:'+ident)!=destination(url):
    raise ValueError('Review the destination and allow this source for browser preparation in Settings first')
  if not _BROWSER.acquire(blocking=False):raise ValueError('Finish or close the current browser preparation before starting another')
  job_id=secrets.token_hex(16)
  with self.lock:
   self.jobs[job_id]={'id':job_id,'opportunity':ident,'kind':'email' if email else 'form','status':'Opening','message':'Opening your isolated application browser','updated':now(),'missing':[]}
   self.commands[job_id]=queue.Queue();self.cancelled[job_id]=cancel or threading.Event()
  self.update(job_id)
  threading.Thread(target=self.run,args=(job_id,item,app,url,email),daemon=True,name='browser-application').start()
  return job_id
 def connect_gmail(self):
  if not _BROWSER.acquire(blocking=False):raise ValueError('Close the current browser task before connecting Gmail')
  ident=secrets.token_hex(16);event=threading.Event()
  with self.lock:
   self.jobs[ident]={'id':ident,'opportunity':None,'kind':'gmail-login','status':'Needs login','message':'Sign in to Google in the opened browser. Connection is detected automatically; the agent never enters your password.','missing':[],'updated':now()}
   self.commands[ident]=queue.Queue();self.cancelled[ident]=event
  self.update(ident)
  def login():
   try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
     profile=self.folder/'profiles'/'gmail';profile.mkdir(mode=0o700,parents=True,exist_ok=True)
     chrome=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
     context=p.chromium.launch_persistent_context(str(profile),headless=self.headless,executable_path=str(chrome) if chrome.exists() else None,viewport={'width':1280,'height':900})
     try:
      page=context.pages[0] if context.pages else context.new_page()
      page.goto('https://mail.google.com/mail/u/0/#inbox',wait_until='domcontentloaded',timeout=45000)
      until=time.monotonic()+600
      while not event.is_set() and not page.is_closed() and time.monotonic()<until:
       if urlsplit(page.url).hostname=='mail.google.com' and page.locator('[gh="cm"]').count():
        with self.store.db() as db:db.execute("INSERT OR REPLACE INTO settings VALUES ('gmail_browser_connected', 'true')")
        self.update(ident,status='Connected',message='Gmail connected in the private application browser. Future email drafts can use this session.');return
       page.wait_for_timeout(500)
      self.update(ident,status='Cancelled' if event.is_set() else 'Expired',message='Gmail connection was not completed. You can retry in Settings.')
     finally:context.close()
   except Exception as error:self.update(ident,status='Needs attention',message='Gmail connection needs attention ('+type(error).__name__+'). Retry in Settings.')
   finally:
    with self.lock:self.commands.pop(ident,None)
    _BROWSER.release()
  threading.Thread(target=login,daemon=True,name='gmail-connect').start()
  return ident
 def _snapshot(self,ident,page,app,email):
  if email:
   recipients=page.locator('input[name="subjectbox"]').evaluate('el=>{const root=el.closest("[role=dialog]");return root?Array.from(root.querySelectorAll("[email],[data-hovercard-id]")).map(e=>e.getAttribute("email")||e.getAttribute("data-hovercard-id")).filter(v=>v&&v.includes("@")):[];}')
   recipients=list(dict.fromkeys(recipients))
   preview={'fields':[{'label':'To','value':', '.join(recipients)},{'label':'Subject','value':page.locator('input[name="subjectbox"]').input_value()},{'label':'Email body','value':page.locator('[contenteditable="true"][role="textbox"]').last.inner_text()}], 'missing':[], 'uploads':[]}
   if set(recipients)!={app['email_to']}:preview['missing'].append('Recipient list changed or could not be verified. Check Gmail before sending.')
   for doc_id in app.get('document_ids',[]):
    doc,_=documents.document_bytes(self.store,doc_id)
    if not page.get_by_text(doc['name'],exact=True).count():preview['missing'].append('Confirm the CV is attached: '+doc['name'])
    preview['fields'].append({'label':'Attachment','value':doc['name']})
   return preview
  return engine.review(page,app)
 def _email(self,page,app):
  if 'mail.google.com' not in urlsplit(page.url).netloc or page.locator('input[type="password"]:visible').count():return False
  # Never create a second Gmail draft after a restart or retry.
  with self.store.db() as db:current=json.loads(db.execute('SELECT payload FROM applications WHERE opportunity=?',(app['_opportunity'],)).fetchone()[0])
  if current.get('gmail_draft_saved'):raise ValueError('A Gmail draft was already saved. Open Gmail Drafts to review it; another draft was not created.')
  compose=page.get_by_role('button',name=re.compile(r'^(Compose|Написать)$',re.I));compose.first.click(timeout=20000)
  with self.store.db() as db:
   current=json.loads(db.execute('SELECT payload FROM applications WHERE opportunity=?',(app['_opportunity'],)).fetchone()[0]);current.update(gmail_draft_saved=True,gmail_draft_saved_at=now())
   db.execute('UPDATE applications SET payload=? WHERE opportunity=?',(json.dumps(current),app['_opportunity']))
  recipient=page.locator('input[aria-label="To recipients"],input[name="to"],input[peoplekit-id]').first
  recipient.fill(app['email_to']);recipient.press('Enter')
  page.locator('input[name="subjectbox"]').fill(app.get('email_subject','Application'))
  page.locator('[contenteditable="true"][role="textbox"]').last.fill(app.get('email_body') or app['draft'])
  for doc_id in app.get('document_ids',[]):
   doc,_=documents.document_bytes(self.store,doc_id);path=str(self.store.directory/'documents'/doc_id)
   files=page.locator('input[type="file"]')
   if files.count():files.first.set_input_files({'name':doc['name'],'mimeType':'application/pdf' if doc['name'].lower().endswith('.pdf') else 'application/octet-stream','buffer':Path(path).read_bytes()})
   else:
    with page.expect_file_chooser() as chooser:page.get_by_role('button',name=re.compile('Attach files|Прикрепить файлы',re.I)).click()
    chooser.value.set_files({'name':doc['name'],'mimeType':'application/pdf' if doc['name'].lower().endswith('.pdf') else 'application/octet-stream','buffer':Path(path).read_bytes()})
   page.get_by_text(doc['name'],exact=True).last.wait_for(timeout=45000)
  page.wait_for_timeout(1800)
  with self.store.db() as db:
   current=json.loads(db.execute('SELECT payload FROM applications WHERE opportunity=?',(app['_opportunity'],)).fetchone()[0]);current.update(gmail_draft_saved=True,gmail_draft_saved_at=now())
   db.execute('UPDATE applications SET payload=? WHERE opportunity=?',(json.dumps(current),app['_opportunity']))
  return True
 def run(self,ident,item,app,url,email):
  context=None;page=None;event=self.cancelled[ident];app=dict(app,_opportunity=item['id']);approved={'value':False};prepared=False
  try:
   from playwright.sync_api import sync_playwright
   with sync_playwright() as playwright:
    profile=self.folder/'profiles'/('gmail' if email else hashlib.sha256((urlsplit(url).hostname or 'test').encode()).hexdigest()[:20]);profile.mkdir(parents=True,mode=0o700,exist_ok=True)
    chrome=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    context=playwright.chromium.launch_persistent_context(str(profile),headless=self.headless,executable_path=str(chrome) if chrome.exists() else None,viewport={'width':1280,'height':900},service_workers='block')
    page=context.pages[0] if context.pages else context.new_page()
    allowed_host=urlsplit(url).hostname
    def guard(route):
     request=route.request;parsed=urlsplit(request.url);origin=parsed.scheme+'://'+parsed.netloc;host=parsed.hostname or ''
     if not public_url(request.url) and origin not in self.test_origins and parsed.scheme not in {'data','blob'}:return route.abort()
     if request.method in {'GET','HEAD'} or engine.read_only_request(request.url,request.post_data):return route.continue_()
     if email and (host=='mail.google.com' or host=='accounts.google.com'):return route.continue_()
     same_family=host==allowed_host or any(allowed_host and allowed_host.endswith(root) and host.endswith(root) for root in ('.greenhouse.io','.ashbyhq.com','.google.com'))
     login=self.jobs[ident].get('status')=='Needs login' and same_family and not re.search(r'formResponse|/submit|/applications?(?:/|$)',parsed.path,re.I)
     if same_family and (approved['value'] or login):return route.continue_()
     return route.abort()
    context.route('**/*',guard)
    page.goto('https://mail.google.com/mail/u/0/#inbox' if email else url,wait_until='domcontentloaded',timeout=45000)
    if not email:
     try:page.wait_for_load_state('networkidle',timeout=10000)
     except Exception:pass
    deadline=time.monotonic()+600
    while not event.is_set() and not page.is_closed() and time.monotonic()<deadline:
     action='prepare' if not prepared else None
     if not action:
      try:action=self.commands[ident].get_nowait()
      except queue.Empty:page.wait_for_timeout(250);continue
     if action in {'prepare','refresh'}:
      prepared=True;approved['value']=False
      if email:
       if not page.locator('input[name="subjectbox"]').count():
        if not self._email(page,app):
         self.update(ident,status='Needs login',message='Sign in to Gmail in the opened browser, then click Refresh review. Your password stays in Google’s browser flow.',missing=['Gmail sign-in required']);continue
      else:
       if page.locator('input[type="password"]:visible').count() or urlsplit(page.url).hostname=='accounts.google.com':
        self.update(ident,status='Needs login',message='Sign in in the browser, then click Refresh review. The agent never enters passwords.',missing=['Portal sign-in required']);continue
       self.update(ident,status='Filling',message='Mapping application fields to your verified facts and prepared answers')
       if not engine.inspect(page):
        opener=page.get_by_role('button',name=re.compile(r'^Apply(?: now| for this job)?$',re.I))
        if opener.count()==1:
         opener.click(timeout=10000);page.wait_for_timeout(600)
       engine.fill(page,self.store,app,cancel=event,use_cloud=self.cloud_mapping)
      preview=self._snapshot(ident,page,app,email)
      page.screenshot(path=str(self.folder/(ident+'.png')),full_page=True)
      self.update(ident,status='Awaiting approval' if not preview['missing'] else 'Needs attention',message='Review the exact content and attachments before submitting' if not preview['missing'] else 'Complete the listed questions in the browser, then refresh the review',fields=preview['fields'],missing=preview['missing'],url=page.url,preview_hash=engine.fingerprint(preview),application_hash=application_hash(self.store,item['id']),approval_token=secrets.token_urlsafe(24) if not preview['missing'] else None)
     elif action=='approve':
      job=self.jobs[ident]
      preview=self._snapshot(ident,page,app,email)
      if preview['missing'] or engine.fingerprint(preview)!=job.get('preview_hash') or application_hash(self.store,item['id'])!=job.get('application_hash'):
       self.update(ident,status='Needs attention',approval_token=None,message='The form, profile or draft changed after review. Refresh and approve the new preview.',missing=['Refresh the review']);continue
      before=page.locator('body').inner_text();approved['value']=True
      self.update(ident,status='Submitting',message='Submitting the application you explicitly approved')
      attempted=False
      try:
       if email:
        final_button=page.get_by_role('button',name=re.compile(r'^Send(?: \(.*\))?$|^Отправить$',re.I)).first
       else:
        engine.commit_reviewed_values(page)
        for field in engine.inspect(page):
         if field['type']=='file' and re.search(r'resume|\bcv\b|curriculum',field['label'],re.I) and not engine.SENSITIVE.search(field['label']) and app.get('document_ids'):
          doc,data=documents.document_bytes(self.store,app['document_ids'][0]);field['locator'].set_input_files({'name':doc['name'],'mimeType':'application/pdf' if doc['name'].lower().endswith('.pdf') else 'application/octet-stream','buffer':data})
        remaining=engine.review(page,app)['missing']
        if remaining:raise ValueError('New requirements appeared after attaching the CV. Check the portal before retrying.')
        final_button=engine.submit_button(page)
       if event.is_set():raise InterruptedError()
       with self.store.db() as db:
        payload=json.loads(db.execute('SELECT payload FROM applications WHERE opportunity=?',(item['id'],)).fetchone()[0]);payload['browser_attempt']={'at':now(),'status':'unconfirmed','job':ident}
        db.execute('UPDATE applications SET payload=? WHERE opportunity=?',(json.dumps(payload),item['id']))
       attempted=True
       final_button.click(timeout=15000)
       receipt=None
       for _ in range(60):
        if event.is_set():break
        text=page.locator('body').inner_text()
        match=re.search(r'Message sent|Письмо отправлено',text,re.I) if email else engine.CONFIRMATION.search(text)
        if match and match[0] not in before:receipt=match[0];break
        if self.test_origins and 'LOCAL-TEST-' in text:receipt=re.search(r'LOCAL-TEST-[^\s]+',text)[0];break
        page.wait_for_timeout(250)
       if not receipt:raise ValueError('The portal did not provide clear confirmation. Check the browser before retrying; this application was not marked submitted.')
       page.screenshot(path=str(self.folder/(ident+'.png')),full_page=True)
       with self.store.db() as db:
        payload=json.loads(db.execute('SELECT payload FROM applications WHERE opportunity=?',(item['id'],)).fetchone()[0])
        payload.update(evidence=receipt+' · '+page.url,submitted_at=now(),browser_attempt={'at':now(),'status':'confirmed','job':ident})
        db.execute("UPDATE applications SET payload=?,status='Submitted',updated=? WHERE opportunity=?",(json.dumps(payload),now(),item['id']))
       self.update(ident,status='Submitted',message='Submission confirmed by the destination',receipt=receipt,approval_token=None);break
      except Exception as error:
       if attempted:
        self.update(ident,status='Unconfirmed',message=str(error) if isinstance(error,ValueError) else 'Submission confirmation was unavailable. Check the destination before retrying.',approval_token=None);break
       approved['value']=False
       self.update(ident,status='Needs attention',message=str(error) if isinstance(error,ValueError) else 'Preparation changed before submission. Refresh the review.',approval_token=None,missing=['Refresh and review the application before submitting'])
    if self.jobs[ident]['status'] not in {'Submitted','Unconfirmed'}:
     self.update(ident,status='Cancelled' if event.is_set() else 'Expired',message='Browser session closed. Saved application text remains available.',approval_token=None)
  except Exception as error:
   self.update(ident,status='Needs attention',message=str(error)[:400] if isinstance(error,ValueError) else 'Browser step failed ('+type(error).__name__+'). Check the browser and retry.',approval_token=None)
  finally:
   if context:
    try:context.close()
    except Exception:pass
   with self.lock:self.commands.pop(ident,None)
   _BROWSER.release()
