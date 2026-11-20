/* Dutch owns its UI and protocol. No 10 engine state is consumed here. */
(() => {
'use strict';
const config=JSON.parse(document.getElementById('dutch-config').textContent);
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const suits={C:'♣',D:'♦',H:'♥',S:'♠'};
let state=null,socket=null,offset=null,retry=0,stopped=false,lastTurn=null,lastRound=null,lastEvent=null,noticeTimer;
let selection=new Set(),queenSource=null,takeDiscard=false;
const pending=new Map(),messages=new Map();
const now=()=>Date.now()/1000+(offset??0);
function html(id,value){if($(id).innerHTML!==value)$(id).innerHTML=value;}
function show(id,on){$(id).hidden=!on;}
function notice(text){$('notice').textContent=text;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').textContent='',5000);}
function open(id){if(!$(id).open)$(id).showModal();}
function close(id){if($(id).open)$(id).close();}
function face(card){return card?`${esc(card.rank)}<span class="suit">${suits[card.suit]||''}</span>`:'<span>✦</span>';}
function color(card){return card&&'DH'.includes(card.suit)?' red':card?'':' back';}
function button(action,label,disabled=false,cls=''){return `<button data-action="${action}" class="${cls}" ${disabled?'disabled':''}>${label}</button>`;}
function player(i){return state?.players[i]?.name||'Waiting';}
// A single slot button, used for the own hand and every opponent hand. Faces appear only when allowed by the server.
function slotCard(entry,seat,{selectable=false,selected=false,small=false,n=null,drawn=false}={}){
 const reveal=seat===state.seat?state.reveals[entry.slot]:null;
 const f=(reveal&&reveal.until>now())?reveal.face:entry.face;
 const cls=['card'+color(f),entry.locked?'locked':'',f?'revealed':''].join(' ');
 return `<button class="hand-slot ${small?'opp-slot':''} ${selectable?'pickable':''} ${selected?'is-selected':''} ${drawn?'is-drawn':''}" data-seat="${seat}" data-slot="${entry.slot}" ${selectable?'':'tabindex="-1"'} aria-pressed="${selected}" aria-label="${seat===state.seat?'Your card':player(seat)+'’s card'}${n?` ${n}`:''}${drawn?' (just drawn)':''}${entry.locked?' (locked)':''}"><span class="${cls}">${face(f)}${entry.locked?'<i class="lock">🔒</i>':''}${drawn?'<i class="drawn-badge">NEW</i>':''}</span>${n?`<small>${n}</small>`:''}</button>`;
}
function syncClock(server,local){if(Number.isFinite(server)){const estimate=server-local;offset=offset===null?estimate:Math.max(offset,estimate);}}
async function api(action,data={}){const started=Date.now()/1000;const csrf=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.slice(10);const response=await fetch(`/dutch/api/${action}/`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf||''},body:JSON.stringify({code:config.code,...data})});const result=await response.json();syncClock(result.server_now,(started+Date.now()/1000)/2);if(!response.ok)throw Error(result.error||'Request failed.');return result;}
function command(action,data={}){
 const packet={action:action==='chat.send'?action:`dutch.${action}`,command:crypto.randomUUID(),turn_id:state?.turn_id,...data};
 return new Promise((resolve,reject)=>{pending.set(packet.command,{packet,resolve,reject});if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(packet));else fallback(pending.get(packet.command));});
}
async function fallback(item){if(!item||item.sending)return;item.sending=true;try{const packet=item.packet;const result=await api(packet.action==='chat.send'?'chat':packet.action.slice(6),packet);if(result.game_type)accept(result);pending.delete(packet.command);item.resolve(result);}catch(e){pending.delete(item.packet.command);item.reject(e);}finally{item.sending=false;}}
let polling=false;setInterval(async()=>{if(!config.code||stopped||socket?.readyState===WebSocket.OPEN||polling)return;polling=true;try{const s=await api('poll',{watch:config.watch});if(config.watch||s.seat!==null){accept(s);$('connection').textContent='Connected through backup polling · retrying live connection';for(const item of pending.values())fallback(item);if(!config.watch)(await api('chat_history')).messages.forEach(addMessage);}}catch(e){$('connection').textContent=e.message;}finally{polling=false;}},2000);
function act(action,data={}){return command(action,data).catch(e=>notice(e.message));}
function accept(next){if(!next||next.deleted){end('This table has closed.');return;}if(state&&next.revision<state.revision)return;syncClock(next.server_now,Date.now()/1000);
 const prev=state;
 // Nothing actually changed server-side (idle tick): keep the view, only refresh countdowns.
 if(prev&&next.revision===prev.revision&&next.event?.id===prev.event?.id){state=next;refresh();return;}
 const rects={};document.querySelectorAll('#room [data-slot]').forEach(el=>{const c=el.querySelector('.card');if(c)rects[el.dataset.slot]=c.getBoundingClientRect();});
 if(next.turn_id!==lastTurn){takeDiscard=false;queenSource=null;lastTurn=next.turn_id;}
 if(next.round!==lastRound){selection.clear();lastRound=next.round;}
 state=next;render();
 if(prev&&next.event&&next.event.id!==prev.event?.id)animate(next.event,rects);
}
// Lightweight per-frame update: timers tick here; a full render only happens on real state changes.
function refresh(){const s=state;if(!s)return;
 const playing=['playing','dutch_final'].includes(s.status);
 const left=playing&&s.turn_deadline?Math.max(0,s.turn_deadline-now()):(s.status==='choose_reveal'||s.phase==='select')&&s.setup_deadline?Math.max(0,s.setup_deadline-now()):null;
 $('turn-timer').textContent=left==null?'':`${Math.ceil(left)}s`;$('turn-timer').className=left!=null&&left<=6?'urgent':'';show('turn-timer',left!=null);
 let changed=false;for(const k of Object.keys(s.reveals)){if(s.reveals[k].until<=now()){delete s.reveals[k];changed=true;}}
 if(changed)render();  // a reveal just expired -> flip those faces back, once
}
function animate(e,rects){const disc=$('discard-face')?.getBoundingClientRect();const at=s=>document.querySelector(`#room [data-slot="${s}"] .card`)?.getBoundingClientRect();const top=state.discard;
 if(e.kind==='draw.preview'&&e.slot)fly($('draw-pile').getBoundingClientRect(),at(e.slot));            // deck -> leftmost
 else if(e.kind==='card.discarded'&&e.slot){if(e.source==='discard')fly(disc,at(e.slot));             // taken card -> slot
  fly(rects[e.slot]||at(e.slot),disc,top);if(e.seat!==state.seat)pulse(e.slot);}                       // the discarded card's FACE flies to the pile (+ highlight whose slot)
 else if(e.kind==='card.discarded')fly($('draw-pile').getBoundingClientRect(),disc,top);               // timeout auto-discard (no slot)
 else if(e.kind==='cut.accepted'&&e.slot)fly(rects[e.slot],disc,top);
 else if(e.kind==='power.used'&&e.power==='queen')fly(rects[e.slot],at(e.target_slot));                 // blind swap
}
function fly(from,to,card){if(matchMedia('(prefers-reduced-motion: reduce)').matches||!from||!to)return;const el=document.createElement('span');el.className='card flying-card'+(card?color(card):' back');el.innerHTML=card?face(card):'✦';Object.assign(el.style,{position:'fixed',pointerEvents:'none',zIndex:30,left:from.x+'px',top:from.y+'px',width:from.width+'px',height:from.height+'px'});document.body.append(el);el.animate([{transform:'translate(0,0) scale(1)',opacity:1},{transform:`translate(${to.x-from.x}px,${to.y-from.y}px) scale(.92)`,opacity:.25}],{duration:480,easing:'ease-in-out'}).finished.finally(()=>el.remove());}
function pulse(handle){const el=document.querySelector(`#room [data-slot="${handle}"]`);if(el&&!matchMedia('(prefers-reduced-motion: reduce)').matches)el.animate([{filter:'brightness(2)'},{filter:'brightness(1)'}],{duration:550});}
function end(message){stopped=true;socket?.close();$('connection').textContent=message+' ';const back=document.createElement('a');back.href='/dutch/';back.textContent='Back to Dutch';$('connection').append(back);notice(message);for(const item of pending.values())item.reject(Error(message));pending.clear();document.querySelectorAll('#room button').forEach(b=>b.disabled=true);}
function connect(){if(stopped)return;socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/dutch/${config.watch?'watch/':''}${config.code}/`);
 socket.onopen=()=>{retry=0;$('connection').textContent=config.watch?'Watching live · hidden cards stay private':'Connected · your private table';for(const item of pending.values())socket.send(JSON.stringify(item.packet));};
 socket.onmessage=e=>{let m;try{m=JSON.parse(e.data);}catch{return;}
  if(m.type==='dutch.state')accept(m.state);
  if(m.type==='dutch.ack'||m.type==='chat.sent'){const item=pending.get(m.command);pending.delete(m.command);if(m.state)accept(m.state);item?.resolve(m.state);}
  if(m.type==='dutch.error'){const item=pending.get(m.command);pending.delete(m.command);if(item)item.reject(Error(m.error));else notice(m.error);}
  if(m.type==='dutch.deleted')end('This table has closed. Return to Dutch to create another.');
  if(m.type==='chat.history'){m.messages.forEach(addMessage);}
  if(m.type==='chat.message')addMessage(m.message);
 };
 socket.onclose=e=>{if(stopped)return;if(e.code===4403||e.code===4404){end('This table is unavailable for your session.');return;}$('connection').textContent='Connection lost · reconnecting automatically…';setTimeout(connect,Math.min(8000,500*2**retry++));};
 socket.onerror=()=>socket.close();
}
function addMessage(m){messages.set(m.id,m);while(messages.size>100)messages.delete(messages.keys().next().value);const box=$('messages'),bottom=box.scrollHeight-box.scrollTop-box.clientHeight<60;html('messages',[...messages.values()].map(m=>`<article><strong>${esc(m.name)}</strong><p>${esc(m.text)}</p></article>`).join(''));if(bottom)box.scrollTop=box.scrollHeight;}
function scoreTable(){const order=state.players.map((p,i)=>i).sort((a,b)=>state.scores[a]-state.scores[b]);return `<table class="score-table"><thead><tr><th>Player</th><th>Total</th></tr></thead><tbody>${order.map(i=>`<tr class="${state.winner_seats.includes(i)?'winner':''}"><td>${esc(player(i))}${state.winner_seats.includes(i)?' · Winner':''}</td><td>${state.scores[i]}</td></tr>`).join('')}</tbody></table>`;}
function roundDetails(r){return `<p>${esc(player(r.actor))}: ${r.reason==='empty_cut'?'empty hand · 0 points':r.success?'successful Dutch · 0 points':'failed Dutch · double hand value'}</p>${r.hands.map((cards,i)=>`<div><strong>${esc(player(i))}</strong> · ${r.totals[i]} in hand → <strong>+${r.earned[i]}</strong><div class="result-hand">${cards.map(c=>`<span class="card${color(c)}">${face(c)}</span>`).join('')||'No cards'}</div></div>`).join('')}`;}
function render(){if(!state)return;const s=state,own=s.seat!==null,host=s.seat===s.host;
 const active=['choose_reveal','initial_peek','playing','dutch_final'].includes(s.status),results=['round_results','match_results','abandoned'].includes(s.status);
 show('landing',false);show('room',true);$('room-code').textContent=s.code;$('room-title').textContent=s.status==='lobby'?'Take your seat.':s.status==='match_results'?'Ten rounds. One story.':'Trust your memory.';
 show('lobby',s.status==='lobby');show('play',active);show('results',results);show('delete',host);show('chat-open',own);$('leave').textContent=own?'Leave':'Back to Dutch';$('invite').textContent=s.invite_open?'Copy invite':'Copy spectator link';
 html('lobby-seats',s.players.map((p,i)=>`<div class="lobby-seat ${p?.ready?'ready':''}"><span class="avatar">${p?esc(p.name.slice(0,1).toUpperCase()):'+'}</span><strong>${p?esc(p.name):`Open seat ${i+1}`}${i===s.host?' · Host':''}</strong><small>${p?`${p.ready?'Ready':'Not ready'} · ${p.connected?'online':'offline'}`:'Waiting for a player'}</small></div>`).join(''));
 html('lobby-actions',own?button('ready',s.players[s.seat]?.ready?'Cancel ready':'I’m ready',false,'gold')+(host?button('start','Start Dutch',!s.players.every(p=>p?.ready&&p.connected)):''):'<p>You are spectating.</p>');
 if(active)renderPlay(s,own);
 html('score-content',scoreTable()+s.round_history.map(r=>`<details><summary>Round ${r.round} · ${r.reason==='empty_cut'?'Empty hand':'Dutch'}</summary>${roundDetails(r)}</details>`).join(''));
 if(results)renderResults(s,host);
 if(s.event&&lastEvent!==s.event.id){if(lastEvent!==null)eventFeedback(s);lastEvent=s.event.id;}
}
function renderPlay(s,own){
 $('round-label').textContent=`ROUND ${s.round} / ${s.max_rounds}`;
 $('peek-label').textContent=own?(s.reveal_count==null?'Reveal count pending':`Reveal count: ${s.reveal_count}`):'Spectator';
 const yourTurn=own&&s.turn===s.seat,choice=yourTurn&&s.phase==='normal_choice';
 // turn status + 30s timer
 let status=`${player(s.turn)}’s turn`;
 if(s.status==='choose_reveal')status=own&&s.seat===s.chooser?'Your choice: how many cards may everyone peek?':`${player(s.chooser)} is choosing how many cards to peek…`;
 else if(s.status==='initial_peek')status=s.phase==='reveal'?'Memorize your cards!':own&&!s.initial_selected?`Choose ${s.reveal_count} card${s.reveal_count===1?'':'s'} to peek — revealed once everyone’s ready.`:'Chosen. Waiting for everyone…';
 else if(s.cut&&!yourTurn)status=`Cut window open — double-tap your ${s.cut.rank} before ${player(s.turn)} plays.`;
 else if(yourTurn)status=s.drawn?'Tap the drawn card to discard it, or another card to keep the draw.':'Your turn — draw, take the discard, or call Dutch.';
 if(s.status==='dutch_final')status=`DUTCH called by ${player(s.dutch_caller)} · ${s.final_turn_order.length-s.final_turn_index} final turn${s.final_turn_order.length-s.final_turn_index===1?'':'s'} left. ${yourTurn?'Your final swap.':`${player(s.turn)} to swap.`}`;
 $('turn-status').textContent=status;$('turn-status').className=(yourTurn?'your-turn ':'')+(s.status==='dutch_final'?'final':'');
 const playing=['playing','dutch_final'].includes(s.status);
 const left=playing&&s.turn_deadline?Math.max(0,s.turn_deadline-now()):(s.status==='choose_reveal'||s.phase==='select')&&s.setup_deadline?Math.max(0,s.setup_deadline-now()):null;
 $('turn-timer').textContent=left==null?'':`${Math.ceil(left)}s`;$('turn-timer').className=left!=null&&left<=6?'urgent':'';show('turn-timer',left!=null);
 // reveal-count chooser
 if(s.status==='choose_reveal'&&own&&s.seat===s.chooser){const r=s.rules;let picks='';for(let n=r.reveal_min;n<=r.reveal_max;n++)picks+=`<button data-action="choose_reveal" data-count="${n}" class="pick">${n===0?'Blind':n}</button>`;html('reveal-chooser',`<strong>How many cards may everyone peek?</strong><div class="pick-row">${picks}</div>`);show('reveal-chooser',true);}else show('reveal-chooser',false);
 // power bar
 show('power-bar',!!(own&&s.power));
 if(own&&s.power){const k=s.power.kind;let msg=k==='jack'?'Jack — tap one of your cards to peek for 1 second.':k==='queen'?(queenSource?'Queen — now tap an opponent’s card to swap it in, blind.':'Queen — tap one of your cards to give away, blind.'):'King — tap any card to lock it face-up, or a locked card to unlock it.';html('power-bar',`<strong>${msg}</strong>${button('power_skip','Skip power','','outline')}`);}
 // opponents (bigger, clickable cards)
 const seats=own?Array.from({length:s.player_limit-1},(_,k)=>(s.seat+k+1)%s.player_limit):s.players.map((p,i)=>i);
 html('opponents',seats.map((i,k)=>{const count=seats.length;const angle=Math.PI/2+(own?(k+1):k)*2*Math.PI/(own?s.player_limit:count);const x=50+46*Math.cos(angle),y=50+50*Math.sin(angle);
  const cards=s.hands[i].map(e=>slotCard(e,i,{small:true})).join('');
  return `<div class="opponent ${s.turn===i?'active':''} ${s.dutch_caller===i?'caller':''}" style="--x:${x}%;--y:${y}%"><strong>${esc(player(i))}${s.players[i]?.connected?'':' · offline'}</strong><div class="opp-hand">${cards}</div><small>${s.counts[i]} cards · ${s.scores[i]} pts</small></div>`;}).join(''));
 $('draw-count').textContent=`${s.draw_count} cards`;$('draw-pile').disabled=!choice||!s.can_draw;$('discard-pile').disabled=!choice||!s.discard;$('discard-pile').classList.toggle('selected',takeDiscard);$('discard-face').className='card'+color(s.discard);html('discard-face',face(s.discard));
 // failed-cut public reveal
 if(s.cut_reveal&&s.cut_reveal.until>now()){$('cut-reveal').className='card'+color(s.cut_reveal.face);html('cut-reveal',`<span class="card${color(s.cut_reveal.face)}">${face(s.cut_reveal.face)}</span><em>${esc(player(s.cut_reveal.seat))} missed the cut</em>`);show('cut-reveal',true);}else show('cut-reveal',false);
 // own hand
 document.querySelector('.hand-zone').hidden=!own;
 if(own){
  const picking=s.status==='initial_peek'&&s.phase==='select'&&!s.initial_selected;
  const canTarget=picking||!!s.drawn||takeDiscard||!!s.power;
  html('hand',s.hands[s.seat].map((e,i)=>slotCard(e,s.seat,{selectable:canTarget,selected:selection.has(e.slot),n:i+1,drawn:!!(s.drawn&&e.slot===s.drawn.slot)})).join(''));
  $('hand-help').textContent=picking?`${selection.size} / ${s.reveal_count} selected`:s.status==='initial_peek'?'Revealing…':s.power?.kind==='jack'?'Tap a card to peek':s.power?.kind==='queen'?(queenSource?'Now tap an opponent’s card':'Tap your card to give away'):s.power?.kind==='king'?'Tap a card to lock/unlock':s.drawn?'Tap the glowing drawn card to discard it, or another card to keep it':takeDiscard?'Tap the card to replace':s.cut&&s.unlocked?`Double-tap your ${s.cut.rank} to cut`:'Double-tap a card to cut when a window is open';
  // hints only — no PEEK button (picks auto-save and reveal on the timer); no CUT button (double-tap); Dutch is the fab
  let actions='';
  if(picking)actions=`<small class="muted">Tap ${s.reveal_count} card${s.reveal_count===1?'':'s'}${s.reveal_count?' — they reveal when the timer ends':''}.</small>`;
  else if(s.status==='initial_peek')actions='<small class="muted">Get ready…</small>';
  else if(s.status==='playing'&&!s.unlocked)actions='<small class="muted">Cuts and Dutch unlock after everyone’s first turn.</small>';
  else if(s.status==='playing'&&s.cut&&!s.drawn&&!s.power)actions=`<small class="muted">Double-tap a ${s.cut.rank} to cut.</small>`;
  html('game-actions',actions);
  show('dutch-call',s.status==='playing'&&s.unlocked);$('dutch-call').disabled=!s.can_call;
 }else show('dutch-call',false);
}
function renderResults(s,host){
 const title=s.status==='abandoned'?'Round abandoned.':s.status==='match_results'?`${s.winner_seats.map(player).map(esc).join(' & ')} ${s.winner_seats.length===1?'wins':'win'}!`:`Round ${s.round} complete.`;
 html('results',`<span class="eyebrow">${s.status==='abandoned'?'NO ONE WAS CONNECTED':'LOWEST TOTAL WINS'}</span><h2>${title}</h2>${s.round_result?roundDetails(s.round_result):'<p>No points were awarded for the unfinished round.</p>'}${scoreTable()}<div class="action-row">${host?(s.status==='round_results'?button('next_round','Deal next round',false,'gold'):button('rematch','Back to ready screen',false,'gold')):'<p>Waiting for the host.</p>'}<a href="/dutch/">Back to Dutch</a></div>`);
}
function eventFeedback(s){const e=s.event,mine=e.seat===s.seat;
 if(e.kind==='dutch.called')notice(`${player(e.seat)} called Dutch! Everyone else gets one last turn.`);
 if(e.kind==='cut.penalty')notice(`${player(e.seat)} missed the cut: one hidden penalty card.`);
 if(e.kind==='cut.accepted')notice(`${player(e.seat)} cut a card and takes the turn.`);
 if(e.kind==='power.used'&&e.power==='queen'&&!mine)notice(`${player(e.seat)} used a Queen to swap a card, blind.`);
 if(e.kind==='power.used'&&e.power==='king')notice(`${player(e.seat)} ${e.mode==='lock'?'locked':'unlocked'} a card.`);
 if(e.kind==='turn.skipped')notice(`${player(e.seat)} ran out of time and was skipped.`);
 const t=$('table');if(t&&!matchMedia('(prefers-reduced-motion: reduce)').matches)t.animate([{opacity:.7},{opacity:1}],{duration:300});
}
// --- a single click router for every slot (own hand + opponents) ---
function onSlot(seat,slot,locked){const s=state;if(!s||s.seat===null)return;
 if(s.status==='initial_peek'&&s.phase==='select'&&seat===s.seat){if(selection.has(slot))selection.delete(slot);else if(selection.size<s.reveal_count)selection.add(slot);act('initial_peek',{slots:[...selection]});render();return;}
 if(s.power){const k=s.power.kind;
  if(k==='jack'&&seat===s.seat){act('jack_peek',{slot});return;}
  if(k==='queen'){if(queenSource===null){if(seat===s.seat&&!locked){queenSource=slot;render();}else notice('Tap one of your own unlocked cards first.');}
   else if(seat!==s.seat&&!locked){act('queen_swap',{own_slot:queenSource,target_seat:seat,target_slot:slot});queenSource=null;}
   else notice('Tap an opponent’s unlocked card.');return;}
  if(k==='king'){act('king_lock',{target_seat:seat,target_slot:slot,mode:locked?'unlock':'lock'});return;}
  return;}
 if(seat!==s.seat)return;
 if(s.drawn){if(slot===s.drawn.slot)act('discard_drawn');else act('swap_drawn',{slot});return;}  // tap drawn = discard; tap other = keep draw, discard that
 if(takeDiscard){act('take_discard',{slot});return;}
 notice('Pick the draw or discard pile — or double-tap a card to cut.');
}
document.addEventListener('click',event=>{
 const opener=event.target.closest('[data-open]');if(opener){open(opener.dataset.open);if(opener.dataset.open==='chat-dialog')$('messages').scrollTop=$('messages').scrollHeight;}
 if(event.target.closest('[data-close]'))event.target.closest('dialog').close();
 const slotBtn=event.target.closest('[data-slot]');if(slotBtn){onSlot(Number(slotBtn.dataset.seat),slotBtn.dataset.slot,slotBtn.querySelector('.locked')!=null);return;}
 const el=event.target.closest('[data-action]');if(!el)return;const action=el.dataset.action;
 if(action==='choose_reveal')act('choose_reveal',{count:Number(el.dataset.count)});
 else if(action==='initial_peek')act('initial_peek',{slots:[...selection]});
 else act(action);
});
// Cutting is a double-tap on one of your own cards while a cut window is open.
document.addEventListener('dblclick',event=>{const b=event.target.closest('[data-slot]');if(!b)return;const s=state;
 if(s&&s.seat!==null&&s.cut&&s.status==='playing'&&Number(b.dataset.seat)===s.seat)act('cut',{slot:b.dataset.slot,event_id:s.cut.event_id});});
$('dutch-call').onclick=()=>act('call');
$('draw-pile').onclick=()=>act('draw');
$('discard-pile').onclick=()=>{takeDiscard=!takeDiscard;render();};
$('invite').onclick=async()=>{const link=`${location.origin}/dutch/${state.invite_open?'room':'watch'}/${config.code}/`;try{await navigator.clipboard.writeText(link);notice('Link copied.');}catch{notice(link);}};
$('leave').onclick=async()=>{if(config.watch){location.href='/dutch/';return;}if(state.status!=='lobby'&&!confirm('Leave this table? An unfinished match will be abandoned.'))return;try{await command('leave');location.href='/dutch/';}catch(e){notice(e.message);}};
$('delete').onclick=async()=>{if(!confirm('Delete this Dutch table for everyone?'))return;try{await command('delete');location.href='/dutch/';}catch(e){notice(e.message);}};
$('chat-form').onsubmit=async e=>{e.preventDefault();const input=$('chat-input'),text=input.value.trim();if(!text)return;const submit=e.target.querySelector('button');submit.disabled=true;try{await command('chat.send',{text});input.value='';$('chat-status').textContent='';close('chat-dialog');}catch(error){$('chat-status').textContent=error.message;}finally{submit.disabled=false;}};
for(const kind of ['create','join']){$(`${kind}-form`).onsubmit=async e=>{e.preventDefault();const form=e.target,values=Object.fromEntries(new FormData(form)),submit=form.querySelector('[type=submit]');submit.disabled=true;try{if(kind==='create')values.limit=Number(values.limit);else{values.code=values.code.toUpperCase();values.command=crypto.randomUUID();}const s=await api(kind,values);location.href=`/dutch/room/${s.code}/`;}catch(error){form.querySelector('.form-error').textContent=error.message;}finally{submit.disabled=false;}};}
$('watch-link').onclick=()=>{const code=$('join-form').elements.code.value.toUpperCase();if(/^[A-Z0-9]{6}$/.test(code))location.href=`/dutch/watch/${code}/`;};
function showRules(r){const vals=Object.entries(r.card_values).map(([k,v])=>`${esc(k)}=${v}`).join(' · ');
 html('rule-defaults',`<p><strong>Card values:</strong> ${vals}</p>
 <p><strong>Reveal count:</strong> a rotating chooser picks ${r.reveal_min}–${r.reveal_max} each round (0 = blind, 4 = whole hand). Visible ${r.starting_peek_seconds}s. Choose within ${r.setup_choice_seconds}s or the server picks for you.</p>
 <p><strong>Turns:</strong> ${r.turn_seconds}s each. Draw preview ${r.draw_preview_seconds}s; you may ${r.allow_discard_drawn?'swap it in or discard it straight away':'only swap it in'}. ${r.first_player==='chooser'?'The chooser takes the first turn.':'A random player starts.'}</p>
 <p><strong>Powers (drawn &amp; discarded):</strong> ${['jack','queen','king'].filter(k=>r.powers[k]).join(', ')||'none'}. Jack peeks one of your cards (${r.jack_peek_seconds}s); Queen blind-swaps with an opponent; King locks a card face-up or unlocks one${r.king_target==='any'?' in any hand':''}.</p>
 <p><strong>Cuts:</strong> one matching-rank card, open until the next player plays. Wrong cut = ${r.failed_cut_penalty_cards} unseen penalty card, shown ${r.failed_cut_reveal_seconds}s. ${r.cutter_takes_next_turn?'A successful cutter takes the next turn.':''} ${r.failed_cutter_takes_next_turn?'A failed cutter takes the next turn.':'A failed cut leaves turn order unchanged.'}</p>
 <p><strong>Dutch:</strong> strictly-lowest caller scores 0; a tie ${r.dutch_tie_counts_as_win?'counts as a win':'fails'} (${r.failed_dutch_multiplier}× their total). ${r.rounds} rounds; lowest cumulative wins, ties share it.</p>
 <p><strong>Disconnects:</strong> ${r.pause_on_disconnect?'play pauses':'play does not pause — turns time out and skip'}. ${r.abandon_when_all_idle?'If no one is connected for a full turn, the round is abandoned.':''}</p>`);}
function viewport(){const v=window.visualViewport;document.documentElement.style.setProperty('--visible-height',`${v?.height||innerHeight}px`);document.documentElement.style.setProperty('--visible-top',`${v?.offsetTop||0}px`);}
window.visualViewport?.addEventListener('resize',viewport);window.visualViewport?.addEventListener('scroll',viewport);viewport();
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state)render();});
setInterval(()=>{if(state)refresh();},250);
showRules(config.rules);for(const form of [$('create-form'),$('join-form')])form.elements.name.value=config.nickname||'';
if(config.code){show('landing',false);show('room',true);api('resync',{watch:config.watch}).then(s=>{if(!config.watch&&s.seat===null){$('join-form').elements.code.value=config.code;open('join-dialog');$('connection').textContent='Join this table or watch instead.';}else{accept(s);showRules(s.rules);connect();}}).catch(e=>notice(e.message));}
})();
