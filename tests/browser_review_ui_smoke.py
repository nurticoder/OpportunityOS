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
  for device,width,height in [('desktop',1440,1000),('mobile',390,844)]:
   page=browser.new_page(viewport={'width':width,'height':height});errors=[]
   page.on('pageerror',lambda error:errors.append(str(error)))
   job['status']='Awaiting approval';job['active']=True;job['updated']='2026-11-26T00:00:00Z';job['approval_token']='ui-test-token'
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
   page.get_by_role('button',name='Approve and submit',exact=True).click()
   expect(page.locator('.browser-job')).to_contain_text('Submitted',timeout=10000)
   assert not errors,errors
   page.close()
  assert len(commands)==2
  print('PASS: desktop/mobile browser review fields, refresh/close/approval controls, correct one-use token request, and confirmation rendering. All submit requests were intercepted; no real action was submitted.')
 finally:browser.close()
