"""Optional deterministic UI edge checks. Requires the isolated fixture DB."""
import asyncio,os,sys
from pathlib import Path
from playwright.async_api import async_playwright
from dutch_browser import BASE,INIT,wait,state,peek
ROOT=Path(__file__).resolve().parents[1]
async def fixture(code,kind):
 env={**os.environ,'DATABASE_URL':os.environ['DUTCH_FIXTURE_DATABASE_URL']}
 proc=await asyncio.create_subprocess_exec(os.environ['DUTCH_DJANGO_PYTHON'],str(ROOT/'tests/dutch_fixture.py'),code,kind,env=env)
 assert await proc.wait()==0
async def main():
 async with async_playwright() as pw:
  browser=await pw.firefox.launch();pages=[];errors=[]
  for i in range(2):
   c=await browser.new_context(viewport={'width':390 if i==0 else 1440,'height':900});await c.add_init_script(INIT)
   p=await c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));pages.append(p);await p.goto(BASE+'/dutch/')
  a,b=pages;await a.locator('[data-open=create-dialog]').click();await a.locator('#create-form [name=name]').fill('Alice');await a.locator('#create-form select').select_option('2');await a.locator('#create-form [type=submit]').click();await a.wait_for_url('**/dutch/room/*/');code=a.url.rstrip('/').split('/')[-1]
  await b.goto(a.url);await b.locator('#join-form [name=name]').fill('Bob');await b.locator('#join-form [type=submit]').click();await wait(b,"window.__dutch.seat===1")
  for p in pages:await p.locator('[data-action=ready]').click()
  await a.locator('[data-action=start]').click();await asyncio.gather(*(peek(p) for p in pages));await wait(a,"window.__dutch.status==='playing'")
  for kind in ['multi','bad','jack','empty']:
   await fixture(code,kind);await wait(a,f"window.__dutch.event.kind==='fixture.{kind}'")
   if kind=='jack':
    await a.locator('#discard-pile').click();await a.locator('#hand [data-slot]').first.click();await a.locator('#jack-dialog[open]').wait_for();await a.locator('#jack-hand [data-slot]').nth(1).click();await wait(a,'Object.keys(window.__dutch.reveals).length===1')
    assert not (await state(b))['reveals'];await asyncio.sleep(1.2);assert await a.locator('#hand .revealed').count()==0
   else:
    await a.locator('[data-action=open_cut]').click()
    for i in range(3 if kind=='multi' else 2):await a.locator('#cut-hand [data-slot]').nth(i).click()
    await a.locator('#cut-submit').click()
    if kind=='multi':await wait(a,"window.__dutch.counts[0]===1 && window.__dutch.turn===0")
    elif kind=='bad':
     await wait(a,'window.__dutch.counts[0]===5');assert (await state(a))['reveals']=={};assert await a.locator('#hand .back').count()==5
    else:
     await wait(a,"window.__dutch.status==='round_results'");s=await state(a);assert s['scores'][0]==0 and s['round_result']['reason']=='empty_cut';assert not s['jack'] and not s['final_turn_order'];assert not await a.locator('#jack-dialog').is_visible()
   print('Firefox UI edge passed:',kind,flush=True)
  assert not errors,errors
  await browser.close()
asyncio.run(main())
