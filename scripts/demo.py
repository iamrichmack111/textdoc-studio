from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path('media/demo/raw');R.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);c=b.new_context(viewport={'width':1600,'height':900},record_video_dir=str(R),record_video_size={'width':1600,'height':900});q=c.new_page();q.goto('http://127.0.0.1:8014/',wait_until='networkidle');q.wait_for_timeout(3000)
 links=q.locator('a[href^="/project/"]')
 if links.count():
  links.first.click();q.wait_for_load_state('networkidle');q.wait_for_timeout(3000)
  s=q.locator('.scene');s.first.click() if s.count() else None;q.wait_for_timeout(2500)
  g=q.get_by_text('Scene Guide',exact=False)
  if g.count(): g.first.click();q.wait_for_timeout(4000);x=q.locator('#guideModal .modal-x');x.click() if x.count() else None
  e=q.get_by_text('Export',exact=False)
  if e.count(): e.first.click();q.wait_for_timeout(4000)
 q.wait_for_timeout(1500);c.close();b.close()
v=sorted(R.glob('*.webm'),key=lambda x:x.stat().st_mtime);assert v,'No recording';t=Path('media/demo/browser-demo.webm');t.unlink(missing_ok=True);v[-1].replace(t);print(t)
