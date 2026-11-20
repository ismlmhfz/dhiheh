/* Dutch-only presentation. Snapshots/timers remain authoritative; flights never hold private faces.
 * GSAP timeline/cleanup guidance: https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/ */
(() => {
'use strict';
const g=window.gsap, $=id=>document.getElementById(id), reduce=matchMedia('(prefers-reduced-motion: reduce)');
const layers=new Set(), tweens=new Set(), expiry=new Map();let resultTimer=null,holding=false,layer=null;
function mount(el){if(!layer){layer=document.createElement('div');layer.className='motion-layer';layer.setAttribute('aria-hidden','true');document.body.append(layer);}layer.append(el);}
const selector=slot=>`#room [data-slot="${CSS.escape(slot)}"] .card`;
const card=slot=>slot?document.querySelector(selector(slot)):null;
const box=el=>el?.getBoundingClientRect();
function retire(t,el){clearTimeout(expiry.get(t));expiry.delete(t);t.kill();tweens.delete(t);if(el){el.remove();layers.delete(el);}else{const targets=t.targets?.()||[];if(targets.length)g.set(targets,{clearProps:'transform,opacity'});}}
function bound(t,el,seconds){expiry.set(t,setTimeout(()=>retire(t,el),seconds*1000));}
function track(t){tweens.add(t);t.eventCallback('onComplete',()=>retire(t));bound(t,null,t.totalDuration()+.15);return t;}
function release(){clearTimeout(resultTimer);if(holding){holding=false;$('play').hidden=true;$('play').inert=false;$('results').hidden=false;}}
function clear(){for(const timer of expiry.values())clearTimeout(timer);expiry.clear();for(const t of tweens){const targets=t.targets?.()||[];t.kill();if(targets.length)g.set(targets,{clearProps:'transform,opacity'});}tweens.clear();for(const el of layers)el.remove();layers.clear();release();}
function capture(prev,next){
 const rects={};document.querySelectorAll('#room [data-slot]').forEach(el=>{rects[el.dataset.slot]=box(el.querySelector('.card'));});
 const frame={rects,discard:box($('discard-face')),draw:box($('draw-pile').querySelector('.card')),top:prev?.discard};
 // Interrupt obsolete visuals on a new event, resize, reconnect, or hidden tab.
 if(prev?.event?.id!==next.event?.id||prev?.round!==next.round)clear();
 if(prev&&next.event?.id!==prev.event?.id&&next.event?.kind==='round.finished'&&!reduce.matches&&!document.hidden&&g)holding=true;
 return frame;
}
function ghost(rect,face){if(!rect||!rect.width||!rect.height)return null;
 const el=document.createElement('span');el.className='card motion-card '+(face?(['D','H'].includes(face.suit)?'red':''):'back');
 el.setAttribute('aria-hidden','true');
 if(face){el.append(document.createTextNode(face.rank));const suit=document.createElement('span');suit.className='suit';suit.textContent={C:'♣',D:'♦',H:'♥',S:'♠'}[face.suit];el.append(suit);}else el.textContent='✦';
 Object.assign(el.style,{left:rect.x+'px',top:rect.y+'px',width:rect.width+'px',height:rect.height+'px'});mount(el);layers.add(el);return el;
}
function flight(from,to,face=null,delay=0,duration=.44){if(!g||reduce.matches||document.hidden||!from||!to)return;
 const el=ghost(from,face);if(!el)return;
 const tl=g.timeline({onComplete:()=>retire(tl,el)});tweens.add(tl);
 tl.to(el,{x:to.x-from.x,y:to.y-from.y,scaleX:to.width/from.width,scaleY:to.height/from.height,rotation:0,ease:'power2.inOut',duration},delay)
   .to(el,{opacity:0,duration:.08});bound(tl,el,delay+duration+.18);
}
function accent(el,kind='gold'){if(!g||!el||document.hidden)return;const mark=document.createElement('span'),r=box(el);if(!r?.width)return;
 mark.className='motion-accent '+kind;mark.setAttribute('aria-hidden','true');Object.assign(mark.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});mount(mark);layers.add(mark);
 const t=g.fromTo(mark,{opacity:.9,scale:1},{opacity:0,scale:reduce.matches?1:1.08,duration:reduce.matches?.15:.6,onComplete:()=>retire(t,mark)});tweens.add(t);bound(t,mark,reduce.matches?.25:.75);
}
function flips(prev,next){if(!g||reduce.matches||document.hidden)return;
 for(const [seat,hand] of next.hands.entries())for(const entry of hand){
  const old=prev?.hands?.[seat]?.find(c=>c.slot===entry.slot),before=prev?.reveals?.[entry.slot]?.face||old?.face,after=next.reveals?.[entry.slot]?.face||entry.face;
  if(JSON.stringify(before||null)!==JSON.stringify(after||null)){const el=card(entry.slot);if(el)track(g.fromTo(el,{rotationY:70,opacity:.55},{rotationY:0,opacity:1,duration:.18,ease:'power2.out',clearProps:'transform,opacity'}));}
 }
}
function play(prev,next,frame){if(!g||!prev||document.hidden){release();return;}
 flips(prev,next);
 if(prev.turn!==next.turn){accent($('turn-status'));if(next.turn===next.seat)accent(document.querySelector('.hand-zone'));}
 if(!next.event||next.event.id===prev.event?.id)return;
 const end=next.event.kind==='round.finished',e=end?(next.event.last_move||next.event):next.event;
 const at=slot=>box(card(slot)),disc=frame.discard,deck=frame.draw;
 if(e.kind==='round.started'){
  next.hands.forEach((hand,seat)=>hand.forEach((entry,i)=>flight(deck,at(entry.slot),null,Math.min(.42,(seat+i)*.045),.32)));
 }else if(e.kind==='draw.preview'){
  flight(deck,at(e.slot));accent(card(e.slot));
 }else if(e.kind==='card.discarded'){
  // Only public pile faces travel; a private draw/peek is never copied into an overlay.
  if(e.source==='discard')flight(disc,at(e.slot),frame.top,0,.34);
  flight(frame.rects[e.slot]||deck,disc,next.discard,e.source==='discard'?.12:0);accent($('discard-face'));
 }else if(e.kind==='cut.accepted'){
  flight(frame.rects[e.slot],disc,next.discard,0,.4);accent($('discard-face'),'success');
 }else if(e.kind==='cut.penalty'){
  accent(card(e.slot),'danger');
  // Shake the authorized on-board reveal, never a retained face clone.
  if(!reduce.matches&&card(e.slot))track(g.fromTo(card(e.slot),{x:-5},{x:5,duration:.065,repeat:3,yoyo:true,clearProps:'transform'}));
  if(e.penalty)flight(deck,at(e.penalty),null,.18,.4);
 }else if(e.kind==='power.used'){
  if(e.power==='queen'){
   flight(frame.rects[e.slot],at(e.target_slot),null,0,.48);flight(frame.rects[e.target_slot],at(e.slot),null,.06,.48);
   accent(card(e.slot));accent(card(e.target_slot));
  }else accent(card(e.target_slot||e.slot),e.power==='king'?'gold':'success');
 }else if(e.kind==='dutch.called')accent($('turn-status'));
 if(end){
  const reveal=()=>{release();const targets=$('results').querySelectorAll('h2,.result-hand,.score-table');
   if(!reduce.matches)track(g.fromTo(targets,{y:10,opacity:0},{y:0,opacity:1,duration:.3,stagger:.035,ease:'power2.out',clearProps:'transform,opacity'}));else accent($('results'));
  };
  if(holding){$('play').hidden=false;$('play').inert=true;$('results').hidden=true;resultTimer=setTimeout(reveal,560);}else reveal();
 }
}
reduce.addEventListener('change',clear);window.addEventListener('resize',clear);window.addEventListener('pagehide',clear);document.addEventListener('visibilitychange',()=>{if(document.hidden)clear();});
window.DutchMotion={capture,play,clear,get holding(){return holding;},get activeCount(){return layers.size;}};
})();
