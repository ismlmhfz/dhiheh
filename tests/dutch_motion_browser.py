"""Deterministic UI edge checks for the new mechanics. Requires the isolated fixture DB.
Needs DUTCH_DJANGO_PYTHON and DUTCH_FIXTURE_DATABASE_URL (isolated dutch-browser.sqlite3)."""
import asyncio, os
from pathlib import Path
from playwright.async_api import async_playwright
from dutch_browser import BASE, INIT, wait, state, choose_reveal, peek
ROOT = Path(__file__).resolve().parents[1]


async def fixture(code, kind):
    env = {**os.environ, 'DATABASE_URL': os.environ['DUTCH_FIXTURE_DATABASE_URL']}
    proc = await asyncio.create_subprocess_exec(os.environ['DUTCH_DJANGO_PYTHON'], str(ROOT / 'tests/dutch_fixture.py'), code, kind, env=env)
    assert await proc.wait() == 0


async def main():
    async with async_playwright() as pw:
        browser = await pw.firefox.launch(); pages = []; errors = []
        for i in range(2):
            c = await browser.new_context(viewport={'width': 390 if i == 0 else 1440, 'height': 900}); await c.add_init_script(INIT)
            p = await c.new_page(); p.on('pageerror', lambda e: errors.append(str(e))); pages.append(p); await p.goto(BASE + '/dutch/')
        a, b = pages
        await a.locator('[data-open=create-dialog]').click(); await a.locator('#create-form [name=name]').fill('Alice'); await a.locator('#create-form select').select_option('2'); await a.locator('#create-form [type=submit]').click(); await a.wait_for_url('**/dutch/room/*/'); code = a.url.rstrip('/').split('/')[-1]
        await b.goto(a.url); await b.locator('#join-form [name=name]').fill('Bob'); await b.locator('#join-form [type=submit]').click(); await wait(b, "window.__dutch.seat===1")
        for p in pages:
            await p.locator('[data-action=ready]').click()
        await a.locator('[data-action=start]').click()
        await choose_reveal(pages); await asyncio.gather(*(peek(p) for p in pages)); await wait(a, "window.__dutch.status==='playing'")
        for kind in ['cut', 'bad', 'king', 'queen', 'jack', 'empty']:
            await fixture(code, kind); await wait(a, f"window.__dutch.event.kind==='fixture.{kind}'")
            if kind == 'cut':                       # double-tap a matching card -> success, cutter takes the turn
                await a.locator('#hand [data-slot]').first.dblclick()
                await wait(a, "window.__dutch.counts[0]===3 && window.__dutch.turn===0")
            elif kind == 'bad':                     # double-tap a wrong rank -> one penalty, turn unchanged
                await a.locator('#hand [data-slot]').first.dblclick()
                await wait(a, "window.__dutch.counts[0]===5 && window.__dutch.turn===1")
            elif kind == 'empty':                   # double-tap the last card -> round ends, cutter scores 0
                await a.locator('#hand [data-slot]').first.dblclick()
                await wait(a, "window.__dutch.status==='round_results'"); s = await state(a)
                assert s['scores'][0] == 0 and s['round_result']['reason'] == 'empty_cut'
            elif kind in ('queen','jack'):
                await a.locator('#draw-pile').click(); await wait(a,'window.__dutch.drawn')
                await a.locator('#hand [data-slot]').first.click(); await wait(a, f"window.__dutch.power?.kind==='{kind}'")
                await a.locator('#hand [data-slot]').first.click()
                if kind=='queen':
                    await a.locator('#opponents [data-slot]').first.click(); await wait(a, "window.__dutch.event.kind==='power.used'")
                else:
                    await wait(a, 'Object.keys(window.__dutch.reveals).length===1')
                    assert not (await state(b))['reveals']
                    await asyncio.sleep(1.2)
                    assert await a.locator('#hand .card:not(.back):not(.locked)').count()==0
            else:                                   # draw a King, discard it, use the lock power
                await a.locator('#draw-pile').click(); await wait(a, 'window.__dutch.drawn')
                await a.locator('#hand [data-slot]').first.click()   # discard the drawn King (leftmost) -> power
                await wait(a, "window.__dutch.power && window.__dutch.power.kind==='king'")
                await a.locator('#hand [data-slot]').nth(1).click()  # lock one of your cards
                await wait(a, 'window.__dutch.hands[0].some(c=>c.locked)')
                await wait(b, 'window.__dutch.hands[0].some(c=>c.locked && c.face)')
                assert any(card['locked'] and card['face'] for card in (await state(b))['hands'][0])  # locked face is public
            await asyncio.sleep(.85)
            assert await a.evaluate('window.gsap.version')=='3.13.0'
            assert await a.evaluate('window.DutchMotion.activeCount')==0
            assert await a.locator('.motion-card').count()==0
            assert await a.evaluate('document.documentElement.scrollWidth<=innerWidth')
            if kind=='queen':await a.screenshot(path='/var/www/whyzainab/checks/dutch-motion-mobile.png',full_page=True)
            if kind=='empty':assert await a.locator('#results').is_visible()
            print('Firefox GSAP edge passed:', kind, flush=True)
        await a.emulate_media(reduced_motion='reduce')
        await fixture(code,'cut'); await wait(a, "window.__dutch.event.kind==='fixture.cut'")
        await a.locator('#hand [data-slot]').first.dblclick(); await wait(a, "window.__dutch.event.kind==='cut.accepted'")
        assert await a.locator('.motion-card').count()==0
        await asyncio.sleep(.3);assert await a.evaluate('window.DutchMotion.activeCount')==0
        assert not errors, errors
        await browser.close()

asyncio.run(main())
