"""Two-size browser verification against a disposable copy of the local database."""
import argparse,json,sqlite3,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
from opportunityos.store import Store
from opportunityos.agent import Agent
from opportunityos.__main__ import handler_for

parser=argparse.ArgumentParser();parser.add_argument('--pass-name',default='light-ui');parser.add_argument('--data',type=Path,default=Path.home()/'Library/Application Support/OpportunityOS/data');args=parser.parse_args()
output=Path('outputs')/args.pass_name;output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
 store=Store(directory)
 with sqlite3.connect(args.data/'opportunity.sqlite') as original:
  with store.db() as db:
   original.backup(db)
   db.execute("INSERT OR REPLACE INTO settings VALUES ('discovery_schedule_mode', '\"manual\"')")
 agent=Agent(store)
 server=ThreadingHTTPServer(('127.0.0.1',0),None)
 server.RequestHandlerClass=handler_for(store,agent,server.server_port)
 threading.Thread(target=server.serve_forever,daemon=True).start()
 address=f'http://127.0.0.1:{server.server_port}'
 errors=[];reports=[];failed_responses=[];resource_errors=[]
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
   try:
    for device,width,height in [('desktop',1440,1000),('mobile',390,844)]:
     page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
     page.on('pageerror',lambda error:errors.append(str(error)))
     page.on('console',lambda message:(resource_errors if 'Failed to load resource:' in message.text else errors).append(message.text) if message.type=='error' else None)
     page.on('response',lambda response:failed_responses.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
     page.goto(address);page.wait_for_load_state('networkidle');page.evaluate('window.fontsReady')
     expect(page.locator('.briefing-landscape svg')).to_be_visible()
     expect(page.locator('.briefing-tools')).to_contain_text('Search is manual')
     assert page.evaluate("getComputedStyle(document.documentElement).colorScheme")=='light'
     names=['Today','Inbox','Applications','Timeline','Review Center','Profile','Agent Activity','Sources','Settings']
     for name in names:
      page.locator('nav').get_by_role('button',name=name,exact=False).click()
      expect(page.locator('body')).to_have_attribute('data-page',{'Today':'today','Inbox':'inbox','Applications':'applications','Timeline':'timeline','Review Center':'review','Profile':'profile','Agent Activity':'activity','Sources':'sources','Settings':'settings'}[name])
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(device,name,'page overflow')
      page.screenshot(path=str(output/(device+'-'+name.lower().replace(' ','-')+'.png')),full_page=True,animations='disabled')
      reports.append({'device':device,'page':name,'overflow':False})
     expect(page.locator('[name="discovery_schedule_mode"]')).to_have_value('manual')
     page.locator('nav').get_by_role('button',name='Inbox',exact=True).click()
     search=page.get_by_role('searchbox');search.fill('Waymo')
     expect(page.locator('.triage-item')).to_contain_text('Waymo')
     page.locator('.title-button').click()
     expect(page.locator('#detail')).to_be_visible()
     expect(page.locator('.original-post')).to_be_visible()
     page.screenshot(path=str(output/(device+'-evidence.png')),full_page=True,animations='disabled')
     page.get_by_role('button',name='Close opportunity').click()
     search.fill('')
     page.locator('.paste-inbox summary').click()
     expect(page.get_by_role('button',name='Extract & save post')).to_be_visible()
     page.locator('nav').get_by_role('button',name='Sources',exact=True).click()
     expect(page.get_by_role('button',name='Save source',exact=True)).to_be_visible()
     page.locator('nav').get_by_role('button',name='Profile',exact=True).click()
     page.locator('summary').filter(has_text='university').click()
     expect(page.locator('[data-fact="university"] textarea')).to_be_visible()
     page.close()
   finally:browser.close()
  assert not errors,errors
  assert all(r['url'].endswith('/favicon.ico') and r['status']==404 for r in failed_responses),failed_responses
  assert agent.worker is None,'Unexpected discovery started'
  (output/'results.json').write_text(json.dumps({'pages':reports,'errors':errors,'discovery_started':False,'known_missing_favicon':failed_responses},indent=2))
  print('PASS: all nine pages at desktop and mobile; no page overflow or JavaScript/CSP errors (existing favicon 404 recorded); local landscape, manual mode, inbox filtering, evidence drawer, paste controls, profile expansion, and source controls')
 finally:server.shutdown();server.server_close()
