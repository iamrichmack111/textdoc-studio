from pathlib import Path
from playwright.sync_api import sync_playwright
O=Path('media/screenshots');O.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);q=b.new_page(viewport={'width':1600,'height':1000});q.goto('http://127.0.0.1:8014/',wait_until='networkidle');q.screenshot(path=str(O/'01-dashboard.png'),full_page=True)
 links=q.locator('a[href^="/project/"]')
 if links.count():
  links.first.click();q.wait_for_load_state('networkidle');q.screenshot(path=str(O/'02-editor.png'),full_page=True)
  scenes=q.locator('.scene')
  if scenes.count(): scenes.first.click();q.wait_for_timeout(300);q.screenshot(path=str(O/'03-scene-inspector.png'),full_page=True)
  g=q.get_by_text('Scene Guide',exact=False)
  if g.count(): g.first.click();q.wait_for_timeout(300);q.screenshot(path=str(O/'04-scene-guide.png'),full_page=True);x=q.locator('#guideModal .modal-x');x.click() if x.count() else None
  e=q.get_by_text('Export',exact=False)
  if e.count(): e.first.click();q.wait_for_timeout(300);q.screenshot(path=str(O/'05-export.png'),full_page=True)
 b.close()
print(O)
