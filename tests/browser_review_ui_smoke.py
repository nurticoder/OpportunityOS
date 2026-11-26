"""UI-only approval wiring check; all submission responses are synthetic/intercepted."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

out=Path('outputs/browser-upgrade');out.mkdir(exist_ok=True,parents=True)
job={'id':'a'*32,'opportunity':'ui-fixture','kind':'form','active':True,'status':'Awaiting approval','message':'Synthetic UI preview only; no real application will be sent.','updated':'2026-11-26T00:00:00Z','missing':[],'fields':[{'label':'Full name','value':'UI Test Applicant'},{'label':'CV','value':'Synthetic test CV'}],'approval_token':'ui-test-token','url':'https://example.invalid/test'}
commands=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 try:
  for device,width,height,kind in [('desktop-form',1440,1000,'form'),('mobile-form',390,844,'form'),('desktop-email',1440,1000,'email'),('mobile-email',390,844,'email')]:
   page=browser.new_page(viewport={'width':width,'height':height});errors=[]
   page.on('pageerror',lambda error:errors.append(str(error)))
   job['status']='Awaiting approval';job['active']=True;job['updated']='2026-11-26T00:00:00Z';job['approval_token']='ui-test-token'
   job['kind']=kind;job['connector']='chatgpt' if kind=='email' else None
   page.route('**/api/browser/jobs',lambda route:route.fulfill(json={'jobs':[job]}))
   def control(route):
    data=route.request.post_data_json;assert data['action']=='approve' and data['approval_token']=='ui-test-token'
    commands.append(data);job.update(status='Submitted',active=False,updated='2026-11-26T00:01:00Z',message='Synthetic confirmation only')
    route.fulfill(json={'ok':True})
   page.route('**/api/browser/control',control)
   page.goto('http://127.0.0.1:8765/#review');page.wait_for_load_state('networkidle');page.evaluate('window.fontsReady')
   expect(page.locator('.browser-job')).to_contain_text('UI Test Applicant')
   expect(page.get_by_role('button',name='Refresh review',exact=True)).to_be_visible()
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   page.screenshot(path=str(out/(device+'-review-controls.png')),full_page=True)
   expect(page.get_by_role('button',name='Close review' if kind=='email' else 'Close browser',exact=True)).to_be_visible()
   page.get_by_role('button',name='Approve and send' if kind=='email' else 'Approve and submit',exact=True).click()
   expect(page.locator('.browser-job')).to_contain_text('Submitted',timeout=10000)
   assert not errors,errors
   page.close()
  assert len(commands)==4
  connections=[]
  page=browser.new_page(viewport={'width':390,'height':844})
  page.route('**/api/browser/jobs',lambda route:route.fulfill(json={'jobs':[]}))
  def connection(route):
   connections.append(route.request.post_data_json);route.fulfill(json={'job':'b'*32})
  page.route('**/api/browser/gmail-connect',connection)
  for selector,expected in [('#connect-gmail',False),('#connect-gmail-browser',True)]:
   page.goto('http://127.0.0.1:8765/#settings');page.wait_for_load_state('networkidle');page.locator(selector).click()
   expect(page.locator('body')).to_have_attribute('data-page','review');assert connections[-1]['browser'] is expected
  page.close()
  print('PASS: desktop/mobile form and Gmail review fields, refresh/close/approval controls, one-use token requests, confirmation rendering, native Gmail connection and browser fallback. All action requests were intercepted; no real message or application was sent.')
 finally:browser.close()
