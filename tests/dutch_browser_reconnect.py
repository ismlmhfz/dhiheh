"""Force WebSocket outage; verify HTTP fallback and expired private draw on reload."""
import asyncio
from playwright.async_api import async_playwright
from dutch_browser import BASE, wait, state, choose_reveal, peek
CAPTURE = """const originalFetch=window.fetch;window.fetch=async(...args)=>{const response=await originalFetch(...args);response.clone().json().then(s=>{if(s.game_type==='dutch')window.__dutch=s;}).catch(()=>{});return response;};"""


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(); pages = []; errors = []
        for i in range(2):
            c = await browser.new_context(viewport={'width': 390, 'height': 844}); await c.add_init_script(CAPTURE)
            async def block(ws): await ws.close()
            await c.route_web_socket('**/ws/dutch/**', block)
            p = await c.new_page(); p.on('pageerror', lambda e: errors.append(str(e))); pages.append(p); await p.goto(BASE + '/dutch/')
        a, b = pages
        await a.locator('[data-open=create-dialog]').click(); await a.locator('#create-form [name=name]').fill('Fallback A'); await a.locator('#create-form select').select_option('2'); await a.locator('#create-form [type=submit]').click(); await a.wait_for_url('**/dutch/room/*/')
        await b.goto(a.url); await b.locator('#join-form [name=name]').fill('Fallback B'); await b.locator('#join-form [type=submit]').click(); await wait(b, 'window.__dutch.seat===1')
        for p in pages:
            await p.locator('[data-action=ready]').click()
        await a.locator('[data-action=start]').click()
        await choose_reveal(pages); await asyncio.gather(*(peek(p) for p in pages)); await wait(a, "window.__dutch.status==='playing'")
        s = await state(a); p = pages[s['turn']]; await wait(p, "window.__dutch.phase==='normal_choice'")
        await p.locator('#draw-pile').click(); await wait(p, 'window.__dutch.drawn')
        before = (await state(p))['draw_count']
        await asyncio.sleep(3.2); await p.reload()                       # 3 s private preview expires
        await wait(p, 'window.__dutch.drawn && window.__dutch.drawn.face===null')
        await p.locator('#hand [data-slot]').nth(1).click()              # keep the draw, discard an original
        await wait(p, '!window.__dutch.drawn'); assert (await state(p))['draw_count'] == before
        await a.locator('#chat-open').click(); await a.locator('#chat-input').fill('Fallback chat works'); await a.locator('#chat-form button').click(); await a.wait_for_selector('#chat-dialog[open]', state='hidden')
        await b.locator('#chat-open').click(); await b.get_by_text('Fallback chat works', exact=True).wait_for(); assert not errors, errors
        print('HTTP fallback: ready, start, choose, synchronized peek, draw, expired reconnect, swap and chat passed', flush=True)
        await browser.close()

asyncio.run(main())
