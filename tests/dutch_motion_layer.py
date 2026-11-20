"""Browser checks for the presentation layer: clipping, cleanup and private flights."""
import asyncio,json,statistics
from playwright.async_api import async_playwright
from dutch_browser import BASE
async def main():
 async with async_playwright() as pw:
  for engine in ['chromium','webkit','firefox']:
   browser=await getattr(pw,engine).launch();p=await browser.new_page(viewport={'width':320,'height':800});errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   await p.goto(BASE+'/dutch/');await p.bring_to_front();await p.screenshot()
   result=await p.evaluate('''async()=>{
    document.getElementById('landing').hidden=true;document.getElementById('room').hidden=false;document.getElementById('play').hidden=false;
    const hand=document.getElementById('hand');hand.innerHTML='<button data-slot="motion-test"><span class="card back">✦</span></button>';
    const old={round:1,turn:0,hands:[[{slot:'motion-test',face:null}]],reveals:{},event:{id:1,kind:'round.started'}};
    const next={...old,seat:0,event:{id:2,kind:'draw.preview',slot:'motion-test'},reveals:{'motion-test':{face:{rank:'K',suit:'H'},until:Date.now()/1000+3}}};
    const frame=DutchMotion.capture(old,next);frame.draw={x:1200,y:100,width:52,height:72};
    let frames=[],last=performance.now(),finish=false;function raf(t){frames.push(t-last);last=t;if(!finish)requestAnimationFrame(raf);}requestAnimationFrame(raf);
    DutchMotion.play(old,next,frame);
    const privateFlights=document.querySelectorAll('.motion-card:not(.back)').length;
    const widthDuring=document.documentElement.scrollWidth;
    await new Promise(r=>setTimeout(r,800));finish=true;
    const clean=DutchMotion.activeCount===0;
    const lobby={...next,event:null};DutchMotion.capture(next,lobby);DutchMotion.play(next,lobby,frame);
    return {frames:frames.slice(2),privateFlights,widthDuring,clean};
   }''')
   assert result['privateFlights']==0 and result['widthDuring']<=320 and result['clean'] and not errors,(result,errors)
   print(json.dumps({'engine':engine,'median_frame_ms':round(statistics.median(result['frames']),2) if result['frames'] else None,'clipping':True,'cleanup':True,'private_faces_copied':False}),flush=True)
   await browser.close()
asyncio.run(main())
