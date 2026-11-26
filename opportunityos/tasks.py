"""Persisted, cancellable application jobs. All work is explicitly user-triggered."""
import json,re,secrets,threading
from .store import now

class Tasks:
    def __init__(self,store):
        self.store=store;self.lock=threading.RLock();self.jobs={};self.events={}
        self.folder=store.directory/'tasks';self.folder.mkdir(mode=0o700,exist_ok=True)
        for path in self.folder.glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{32}',path.stem):continue
            try:
                job=json.loads(path.read_text())
                if job.get('status') in {'Queued','Running'}:job.update(status='Interrupted',message='Interrupted by restart. Click Prepare again to retry.')
                self.jobs[path.stem]=job
            except (ValueError,OSError):pass
    def update(self,ident,**values):
        with self.lock:
            self.jobs[ident].update(values,updated=now())
            path=self.folder/(ident+'.json');temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.jobs[ident],ensure_ascii=False));temporary.chmod(0o600);temporary.replace(path)
        self.store.log('Application preparation · '+str(values.get('message',values.get('status','updated')))[:120])
    def list(self):
        with self.lock:return sorted((dict(v) for v in self.jobs.values()),key=lambda v:v.get('updated',''),reverse=True)[:30]
    def start(self,opportunity,work):
        with self.lock:
            active=next((j for j in self.jobs.values() if j['opportunity']==opportunity and j['status'] in {'Queued','Running'}),None)
            if active:return active['id']
            ident=secrets.token_hex(16);event=threading.Event();self.events[ident]=event
            self.jobs[ident]={'id':ident,'opportunity':opportunity,'status':'Queued','message':'Waiting for cloud preparation','updated':now()}
            self.update(ident)
        def run():
            try:
                self.update(ident,status='Running',message='Reading requirements and your verified profile')
                result=work(event,lambda message:self.update(ident,message=message))
                if event.is_set():raise InterruptedError()
                self.update(ident,status='Complete',message='Application package ready for review',result=result)
            except InterruptedError:self.update(ident,status='Cancelled',message='Preparation cancelled')
            except Exception as error:self.update(ident,status='Needs attention',message=str(error)[:400] if isinstance(error,ValueError) else 'Preparation failed ('+type(error).__name__+'). Retry or check the connection.')
        threading.Thread(target=run,daemon=True,name='application-preparation').start()
        return ident
    def cancel(self,ident=None):
        with self.lock:
            for key,event in self.events.items():
                if ident is None or key==ident:event.set()
