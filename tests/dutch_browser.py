"""Run against an isolated development server: DUTCH_BASE_URL=http://127.0.0.1:8097.
Requires Playwright browsers. Never point this at a production database.
"""
import asyncio,json,os,time
from playwright.async_api import async_playwright
BASE=os.environ.get('DUTCH_BASE_URL','http://127.0.0.1:8097')
INIT="""window.__dutch=null;const Original=window.WebSocket;window.WebSocket=class extends Original{constructor(...args){super(...args);this.addEventListener('message',e=>{let m=JSON.parse(e.data);if(m.state?.game_type==='dutch')window.__dutch=m.state;});}};"""
async def wait(p,expression,timeout=20000):await p.wait_for_function('window.__dutch && ('+expression+')',timeout=timeout)
async def state(p):return await p.evaluate('window.__dutch')
async def jack(p):
 if await p.locator('#jack-dialog').is_visible():
  await p.locator('#jack-hand [data-slot]').first.click();await asyncio.sleep(1.1)
async def peek(p):
 await wait(p,"window.__dutch.status==='initial_peek'")
 s=await state(p)
 for i in range(s['peek_count']):await p.locator('#hand [data-slot]').nth(i).click()
 await p.locator('[data-action=initial_peek]').click()
 await wait(p,'Object.keys(window.__dutch.reveals).length>0')
async def swap(p,hidden=False):
 await jack(p);s=await state(p);turn=s['turn_id']
 if hidden:
  await p.locator('#draw-pile').click();await p.wait_for_selector('#draw-dialog[open]')
  await p.wait_for_selector('#draw-dialog[open]',state='hidden',timeout=4000)
  assert not await p.locator('#draw-face').inner_text()
 else:await p.locator('#discard-pile').click()
 await p.locator('#hand [data-slot]').first.click()
 await wait(p,f'window.__dutch.turn_id>{turn} && !window.__dutch.drawn')
async def match(pw,engine,n):
 browser=await getattr(pw,engine).launch(headless=True);contexts=[];pages=[];errors=[]
 for i in range(n):
  c=await browser.new_context(viewport={'width':320 if i==0 else 1440,'height':900});contexts.append(c);await c.add_init_script(INIT)
  p=await c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));pages.append(p);await p.goto(BASE+'/dutch/')
 p=pages[0];await p.locator('[data-open=create-dialog]').click();await p.locator('#create-form [name=name]').fill('Player 1');await p.locator('#create-form select').select_option(str(n));await p.locator('#create-form [type=submit]').click();await p.wait_for_url('**/dutch/room/*/');code=p.url.rstrip('/').split('/')[-1]
 for i,p in enumerate(pages[1:],1):
  await p.locator('[data-open=join-dialog]').click();await p.locator('#join-form [name=name]').fill('Player '+str(i+1));await p.locator('#join-form [name=code]').fill(code);await p.locator('#join-form [type=submit]').click();await p.wait_for_url('**/dutch/room/*/')
 for p in pages:await p.locator('[data-action=ready]').click()
 await pages[0].locator('[data-action=start]').click()
 spectator=await browser.new_context();watch=await spectator.new_page();await watch.add_init_script(INIT);await watch.goto(BASE+f'/dutch/watch/{code}/');await wait(watch,'window.__dutch.seat===null');assert (await state(watch))['slots']==[]
 for rnd in range(1,11):
  await asyncio.gather(*(peek(p) for p in pages))
  await wait(pages[0],"window.__dutch.status==='playing'")
  for i in range(n):
   s=await state(pages[0]);p=pages[s['turn']];await wait(p,'window.__dutch.turn===window.__dutch.seat')
   await swap(p,hidden=rnd==1 and i==0)
   await wait(pages[0],f"window.__dutch.turn_id>{s['turn_id']}")
  for p in pages:await jack(p)
  await wait(pages[0],"!window.__dutch.cut_window && window.__dutch.phase==='normal_choice'")
  s=await state(pages[0]);caller=pages[s['turn']];await wait(caller,'window.__dutch.can_call');await caller.locator('[data-action=call]').click()
  await wait(pages[0],"window.__dutch.status==='dutch_final'");s=await state(pages[0]);assert len(s['final_turn_order'])==n-1
  for seat in s['final_turn_order']:
   p=pages[seat];await wait(p,'window.__dutch.turn===window.__dutch.seat');await swap(p)
  await wait(pages[0],"['round_results','match_results'].includes(window.__dutch.status)");s=await state(pages[0]);assert len(s['round_history'])==rnd
  for p in pages:
   assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Overflow {engine} {n}'
  print(f'{engine} {n} players: round {rnd}, scores {s["scores"]}',flush=True)
  if rnd==1:
   await pages[0].locator('#chat-open').click();await pages[0].locator('#chat-input').fill('Good game <script>');await pages[0].locator('#chat-form button').click();await pages[0].wait_for_selector('#chat-dialog[open]',state='hidden')
   await pages[1].locator('#chat-open').click();await pages[1].get_by_text('Good game <script>',exact=True).wait_for();await pages[1].locator('#chat-dialog [data-close]').click()
  if rnd<10:await pages[0].locator('[data-action=next_round]').click()
 assert s['status']=='match_results' and s['winner_seats'];assert not errors,errors
 await pages[0].locator('[data-action=rematch]').click();await wait(pages[0],"window.__dutch.status==='lobby'");assert (await state(pages[0]))['scores']==[0]*n
 await browser.close();return {'engine':engine,'players':n,'rounds':10,'errors':errors}
async def main():
 async with async_playwright() as pw:
  results=await asyncio.gather(match(pw,'chromium',6),match(pw,'webkit',2));print(json.dumps(results),flush=True)
if __name__=='__main__':asyncio.run(main())
