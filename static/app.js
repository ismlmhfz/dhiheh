const teamName=(s,t)=>s.team_names?.[t]||['Fern','Amber'][t];
const $=s=>document.querySelector(s), suits={S:'♠',H:'♥',D:'♦',C:'♣'}, suitNames={S:'Spades',H:'Hearts',D:'Diamonds',C:'Clubs'};
let state=null,roomCode='',socket=null,joinMode=false,muted=localStorage.getItem('ten-muted')!=='false',reconnectTimer,previous='',lastTrick=0;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('show'),3500)}
function csrf(){return document.cookie.split('; ').find(s=>s.startsWith('csrftoken='))?.split('=')[1]}
async function api(action,data={}){const res=await fetch(`/api/${action}/`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({code:roomCode,avatar:localStorage.getItem('ten-avatar')||'fox',...data})});const body=await res.json();if(!res.ok)throw Error(body.error||'Something went wrong.');return body}
function send(action,data={}){if(action==='seat'&&window.clubVoice?.active)window.clubVoice.leave();if(socket?.readyState===1){socket.send(JSON.stringify({action,command:crypto.randomUUID(),...data}));return true}toast('Reconnecting to the table. Please wait.');return false;}
function sound(){if(muted)return;try{const a=new (window.AudioContext||window.webkitAudioContext)(),o=a.createOscillator(),g=a.createGain();o.connect(g);g.connect(a.destination);o.frequency.setValueAtTime(540,a.currentTime);o.frequency.exponentialRampToValueAtTime(320,a.currentTime+.12);g.gain.setValueAtTime(.035,a.currentTime);g.gain.exponentialRampToValueAtTime(.001,a.currentTime+.18);o.start();o.stop(a.currentTime+.2);o.onended=()=>a.close()}catch{}}
function openSetup(join){joinMode=join;$('#setup-title').textContent=join?'Your people are waiting.':'Start something good.';$('#setup-submit').textContent=join?'Join the table →':'Create room ↗';$('#code-label').hidden=!join;$('#mode-field').hidden=join;$('#code').required=join;$('#name').value=localStorage.getItem('ten-name')||'';$('#setup').showModal()}
$('#open-create').onclick=()=>openSetup(false);$('#open-join').onclick=()=>openSetup(true);
const soloButton=document.createElement('button');soloButton.className='secondary';soloButton.id='solo-practice';soloButton.textContent='Play solo · 3 bots';$('.hero-actions').after(soloButton);
soloButton.onclick=async()=>{soloButton.disabled=true;try{const result=await api('practice',{name:localStorage.getItem('ten-name')||'You',mode:'quick'});roomCode=result.code;history.replaceState({},'',`/room/${roomCode}/`);enter(result.state)}catch(error){toast(error.message)}finally{soloButton.disabled=false}};
for(const el of [$('#rules-button'),$('#strip-rules')])el.onclick=e=>{e.preventDefault();$('#rules').showModal()};
document.querySelectorAll('.close').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('#sound').onclick=()=>{muted=!muted;localStorage.setItem('ten-muted',muted);$('#sound').textContent=muted?'♫̸':'♫';if(!muted)sound()};$('#sound').textContent=muted?'♫̸':'♫';
$('#fullscreen').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen?.()};
$('#setup-form').onsubmit=async e=>{e.preventDefault();const b=$('#setup-submit');b.disabled=true;try{localStorage.setItem('ten-name',$('#name').value);roomCode=$('#code').value.trim().toUpperCase();const result=await api(joinMode?'join':'create',{name:$('#name').value,mode:$('#mode').value});roomCode=result.code;history.replaceState({},'',`/room/${roomCode}/`);$('#setup').close();enter(result.state)}catch(e){toast(e.message)}finally{b.disabled=false}};
function enter(s){document.body.classList.add('in-room');$('#home').hidden=true;$('#room').hidden=false;render(s);connect()}
function connect(){clearTimeout(reconnectTimer);socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/room/${roomCode}/`);socket.onmessage=e=>{const s=JSON.parse(e.data);if(s.type==='table.deleted'){roomCode='';clearTimeout(reconnectTimer);window.clubVoice?.leave(false);socket?.close();location.href='/?table=deleted';return}if(s.type?.startsWith('chat.')){window.clubChat?.receive(s);return}if(s.type?.startsWith('voice.')){window.clubVoice?.receive(s);return}if(s.error){toast(s.error);previous='';if(state)render(state)}else render(s)};socket.onclose=()=>{previous='';if(state)render(state);window.clubVoice?.lost();if(roomCode){$('#turn-bar').textContent='Connection lost. Rejoining your table…';reconnectTimer=setTimeout(connect,1800)}};}
$('#invite').onclick=async()=>{if(!state?.invitation?.open){toast(state?.invitation?.reason||'Invitation closed');return}try{await navigator.clipboard.writeText(`${location.origin}/room/${roomCode}/`);toast('Invitation link copied. Bring your people.')}catch{toast(`Room code: ${roomCode}`)}};
$('#leave').onclick=async()=>{if(state.status==='lobby'){try{await api('leave');roomCode='';socket?.close();location.href='/'}catch(e){toast(e.message)}}else if(['abandoned','match_results'].includes(state.status)){roomCode='';socket?.close();location.href='/'}else if(confirm('Quit this match? The match will end for all four players.'))send('quit')};
function card(c,disabled=false,extra=''){const r=c.slice(0,-1),s=c.slice(-1);return `<button class="card ${s==='H'||s==='D'?'red':''} ${r==='10'?'ten':''} ${extra}" ${disabled?'disabled':''} data-card="${c}" aria-label="${r} of ${suitNames[s]}"><span class="rank">${r}<small>${suits[s]}</small></span><span class="suit">${suits[s]}</span><span class="corner">${r}</span></button>`}
function action(text,name,primary=false){return `<button class="${primary?'primary':'secondary'}" data-action="${name}">${text}</button>`}
const avatarIcons={fox:'🦊',panda:'🐼',frog:'🐸',cat:'🐱',lion:'🦁',owl:'🦉',koala:'🐨',dragon:'🐲'};
const positions=['bottom','left','top','right'];
// Reconcile existing nodes so updates don't restart animations or lose focus.
function morph(parent,markup){
    const template=document.createElement('template');template.innerHTML=markup;
    const key=n=>n.nodeType===1?(n.getAttribute('data-player-seat')??n.getAttribute('data-card')??n.getAttribute('data-winner-seat')):null;
    function reconcile(target,source){
        let cursor=target.firstChild;
        for(const desired of [...source.childNodes]){
            const k=key(desired);
            let actual=k!==null?[...target.childNodes].find(n=>key(n)===k&&n.nodeName===desired.nodeName):cursor;
            if(!actual||actual.nodeType!==desired.nodeType||actual.nodeName!==desired.nodeName){actual=desired.cloneNode(true);target.insertBefore(actual,cursor)}
            else{
                if(actual!==cursor)target.insertBefore(actual,cursor);
                if(actual.nodeType===3){if(actual.nodeValue!==desired.nodeValue)actual.nodeValue=desired.nodeValue}
                else{
                    for(const a of [...actual.attributes])if(!desired.hasAttribute(a.name))actual.removeAttribute(a.name);
                    for(const a of [...desired.attributes])if(actual.getAttribute(a.name)!==a.value)actual.setAttribute(a.name,a.value);
                    reconcile(actual,desired);
                }
            }
            cursor=actual.nextSibling;
        }
        while(cursor){const next=cursor.nextSibling;cursor.remove();cursor=next}
    }
    reconcile(parent,template.content);
}
function view(selector){return {set innerHTML(markup){morph($(selector),markup)}}}
let captureGeneration=0;
const captureAnimations=new Set();
const piles=document.createElement('div');piles.id='captured-piles';$('#table').append(piles);
const trumpBanner=document.createElement('div');trumpBanner.id='table-trump';trumpBanner.setAttribute('role','status');trumpBanner.setAttribute('aria-live','polite');$('#table').before(trumpBanner);
let displayedTrump=null;
function renderTrump(s){
    const suit=s.trump||'',active=Boolean(suit);
    const signature=`${s.deal||0}:${suit}:${s.status==='lobby'}`;
    trumpBanner.hidden=s.status==='lobby';
    if(displayedTrump===signature)return;
    const changed=displayedTrump!==null&&active;
    displayedTrump=signature;
    trumpBanner.className=`table-trump ${active?'is-set':'not-set'} ${suit==='H'||suit==='D'?'red-trump':''}`;
    morph(trumpBanner,`<span class="trump-symbol" aria-hidden="true">${suits[suit]||'—'}</span><div><span class="trump-caption">${active?'TRUMP SUIT':'TRUMP NOT SET'}</span><strong>${active?suitNames[suit]:'Waiting for the first cut'}</strong><small>${active?'Beats every other suit · Locked for this deal':'The first off-suit card will establish trump'}</small></div>${active?'<span class="trump-lock">LOCKED</span>':''}`);
    $('#trump').classList.toggle('active-trump',active);
    if(changed&&!matchMedia('(prefers-reduced-motion: reduce)').matches)trumpBanner.animate([{boxShadow:'0 0 0 0 #d7af5e00'},{boxShadow:'0 0 0 7px #d7af5e66'},{boxShadow:'0 0 0 0 #d7af5e00'}],{duration:1100});
}
function tableCard(x,s,winner=null){const pos=positions[(x.seat-s.seat+4)%4],name=s.players[x.seat]?.name||'Player';return `<div class="played-card ${pos}" data-player-seat="${x.seat}">${card(x.card,true,x.seat===winner?'winning':'')}<span class="played-by">${esc(name)}${x.seat===s.seat?' · You':''}</span></div>`}
function renderTableCards(s){
    const center=$('#center-cards');
    center.className='center-cards positioned-cards';
    morph(center,(s.trick||[]).map(x=>tableCard(x,s)).join(''));
}
function clearCaptures(){window.clubCapture=null;document.body.classList.remove('resolving-win');captureGeneration++;for(const item of captureAnimations){item.animation?.cancel();item.node.remove()}captureAnimations.clear();$('.capture-announcement')?.remove()}
function animateCapture(s){
    const center=$('#center-cards'),trick=s.last;
    morph(center,trick.cards.map(x=>tableCard(x,s,trick.winner)).join(''));
    const target=$(`[data-winner-seat="${trick.winner}"] .pile-cards`);
    if(!target)return;
    const destination=target.getBoundingClientRect(),table=$('#table').getBoundingClientRect();
    const generation=captureGeneration,reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    $('.capture-announcement')?.remove();
    const capture=window.clubCapture={pending:true,deal:s.deal,number:trick.number};
    const animations=[];
    center.querySelectorAll('.played-card .card').forEach((cardNode,i)=>{
        // Finish entrance motion before measuring; never clone a scaled frame.
        cardNode.getAnimations().forEach(animation=>animation.finish());
        cardNode.parentElement.getAnimations().forEach(animation=>animation.finish());
        const rect=cardNode.getBoundingClientRect(),clone=cardNode.cloneNode(true);
        clone.classList.add('flying-capture');clone.style.cssText=`position:fixed;left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px;margin:0;z-index:${80+i};pointer-events:none;animation:none;opacity:1`;
        document.body.append(clone);
        const cx=table.left+table.width/2-rect.width/2-rect.left,cy=table.top+table.height/2-rect.height/2-rect.top;
        const dx=destination.left+destination.width/2-rect.width/2-rect.left,dy=destination.top+destination.height/2-rect.height/2-rect.top;
        const item={node:clone};captureAnimations.add(item);
        const stack=`translate(${cx+i*3}px,${cy+i*2}px) rotate(${i*4-6}deg)`;
        item.animation=clone.animate(reduced?[
            {opacity:1,offset:0},{opacity:1,offset:.9},{opacity:0,offset:1}
        ]:[
            {transform:'translate(0,0)',opacity:1,offset:0},
            {transform:'translate(0,0)',opacity:1,offset:.45},
            {transform:stack,opacity:1,offset:.60},
            {transform:stack,opacity:1,offset:.68},
            {transform:`translate(${dx}px,${dy}px) rotate(10deg)`,opacity:1,offset:.94},
            {transform:`translate(${dx}px,${dy}px) rotate(10deg)`,opacity:0,offset:1}
        ],{duration:reduced?2000:3800,easing:'ease-in-out',fill:'forwards'});
        animations.push(item.animation.finished.catch(()=>{}).then(()=>{clone.remove();captureAnimations.delete(item)}));
    });
    Promise.all(animations).then(()=>{if(generation!==captureGeneration)return;capture.pending=false;if(window.clubCapture===capture&&state?.deal===capture.deal&&state?.last?.number===capture.number)render(state);const pile=$(`[data-winner-seat="${trick.winner}"]`);pile?.animate([{filter:'brightness(1)'},{filter:'brightness(1.8)',transform:'scale(1.12)'},{filter:'brightness(1)',transform:'scale(1)'}],{duration:600})});
}
function renderCapturedPiles(s){
    morph(piles,positions.map((pos,relative)=>{
        const seat=(s.seat+relative)%4,won=(s.history||[]).filter(t=>t.winner===seat);
        if(!won.length)return '';
        const latest=won[won.length-1],name=s.players[seat]?.name||'Player';
        const tens=won.flatMap(trick=>trick.cards.filter(x=>x.card.slice(0,-1)==='10').map(x=>({suit:x.card.slice(-1),stack:trick.number})));
        const layers=Array.from({length:Math.min(3+won.length,12)},(_,i)=>`<i class="pile-back" style="--layer:${i}"></i>`).join('');
        const faces=tens.map((ten,i)=>`<span class="pile-ten ${ten.suit==='H'||ten.suit==='D'?'red':''}" data-ten-suit="${ten.suit}" style="--ten:${i}" title="10 of ${suitNames[ten.suit]} · Stack ${ten.stack}" aria-label="10 of ${suitNames[ten.suit]}, captured in stack ${ten.stack}"><b>10<small>${suits[ten.suit]}</small></b><strong>${suits[ten.suit]}</strong><em>10</em></span>`).join('');
        return `<div class="captured-pile ${pos} ${s.last?.winner===seat?'latest-capture':''} ${tens.length?'holds-tens':''}" data-winner-seat="${seat}" title="${esc(name)} · ${won.length} stacks · ${tens.length} tens"><div class="pile-cards" style="--depth:${Math.min(won.length,8)}">${layers}<div class="pile-tens">${faces}</div></div><span class="pile-count">${won.length} stack${won.length===1?'':'s'}</span><small>${tens.length?`${tens.length} ten${tens.length===1?'':'s'} captured`:s.last?.winner===seat?'Last winner':'Captured'}</small></div>`;
    }).join(''));
}
function render(s){if(!s.last)lastTrick=0;state=s;const lobby=s.status==='lobby',me=s.seat,host=s.host===me;$('#delete-table').hidden=!host;$('#invite').disabled=!s.invitation?.open;$('#invite').textContent=s.invitation?.open?'Copy invite ↗':s.invitation?.reason||'Invitation closed';$('#invite').title=s.invitation?.open?'Expires '+new Date(s.invitation.expires_at).toLocaleTimeString():s.invitation?.reason||'';const team=s.players[me]?.team??me%2;document.querySelectorAll('.team-score>span').forEach((node,t)=>{node.innerHTML=`<i class="dot ${t?'b':'a'}"></i> ${esc(teamName(s,t))}`});const names=s.players.map((p,i)=>p?.name||`Seat ${i+1}`);const target={quick:[8,5],standard:[12,7],long:[18,11]}[s.mode];$('#room-label').textContent=`PRIVATE TABLE · ${roomCode}`;$('#room-title').textContent=lobby?'Take your seat.':s.status==='abandoned'?'Until next time.':`A good hand is a team effort.`;$('#mode-label').textContent=s.mode.toUpperCase();$('#score-a').textContent=s.scores?.[0]||0;$('#score-b').textContent=s.scores?.[1]||0;$('#match-progress').textContent=`First to ${target[0]} · Maximum ${target[1]} deals`;$('#deal-number').textContent=s.deal?`${s.deal} / ${target[1]}`:'WAITING';view('#deal-stats').innerHTML=[0,1].map(t=>`<div class="stat-line"><span>${esc(teamName(s,t))} · ${s.stacks?.[t]||0} stacks</span><span class="ten-marks">${Object.keys(suits).map(su=>`<span class="${s.tens?.[t]?.includes(su)?'':'faded'}">${suits[su]}</span>`).join('')}</span></div>`).join('');const tr=s.trump||'';view('#trump').innerHTML=`${suits[tr]||'♧'} <span>TRUMP<small>${suitNames[tr]||'Not set yet'}</small></span>`;view('#details').innerHTML=lobby?'Opposite seats are teammates.<br>All four players must be ready.':`Stack leader <b>${esc(names[s.starter])}</b><br>Stack winner leads next<br>Your team <b>${esc(teamName(s,team))}</b>`;
view('#seats').innerHTML=[0,1,2,3].map(i=>{const p=s.players[i],relative=(i-me+4)%4,pos=['bottom','left','top','right'][relative];return `<div data-seat-index="${i}" class="seat ${pos} ${(lobby?(p?.team??i%2):i%2)?'amber':''} ${!lobby&&s.turn===i&&s.status==='playing'?'active':''} ${p&&!p.connected?'offline':''} ${p?'':'empty'}">${p?`<div class="avatar">${avatarIcons[p.avatar]||Object.values(avatarIcons)[i]}</div><span class="name">${esc(p.name)}${i===me?' · You':''}</span><small>${lobby?(p.ready?'✓ Ready':'Not ready'):!p.connected?'Reconnecting…':`Team ${esc(teamName(s,p?.team??i%2))}`}${!lobby&&relative===2?' · Teammate':''}</small>`:`<button data-seat="${i}">＋ Take seat</button><small>${esc(teamName(s,p?.team??i%2))}</small>`}</div>`}).join('');document.querySelectorAll('[data-seat]').forEach(b=>b.onclick=()=>send('seat',{seat:+b.dataset.seat}));
let message='',buttons='',turn='';if(lobby){message=`<h3>The table is yours.</h3><p>${s.players.filter(Boolean).length} of 4 players · Invite your favourite people.</p>`;buttons=action(s.players[me].ready?'✓ Ready · Undo':'I’m ready','ready',true);if(host)buttons+=action('Start match →','start');turn='Choose your teams above, then everyone ready up.'}else if(s.status==='playing'){turn=s.paused?'Table paused · A player has 90 seconds to reconnect.':s.turn===me?'Your turn. Pick a highlighted card.':`${names[s.turn]} is thinking…`;if(s.chase)turn+=` · ${teamName(s,s.chase.team)} chasing four · ${s.chase.locked} points locked`;}else if(s.status==='chase_decision'){const d=s.decision,seconds=Math.max(0,Math.ceil(d.deadline-Date.now()/1000));message=`<h3>Bank it. Or chase it.</h3><p>${esc(names[d.seat])} secured ${d.points} points.</p><p>${seconds}s to choose · Bank is automatic</p>`;turn=`${teamName(s,d.team)} can chase all four tens.`;if(d.seat===me)buttons=action(`Bank ${d.points} points`,'bank')+action('Chase four ↗','chase',true);}else if(['deal_results','match_results'].includes(s.status)){const match=s.status==='match_results';message=`<h3>${match?(s.winner===null?'A perfectly matched table.':`${esc(teamName(s,s.winner))} wins the match!`):`${esc(teamName(s,s.result.team))} takes the deal.`}</h3><p>${s.result.points} points banked · ${s.scores[0]} : ${s.scores[1]}</p>`;turn=match?'Good cards. Better company. Play again?':'A fresh deal. A new chance.';if(host)buttons=action(match?'Play a rematch ↻':'Deal the next hand →',match?'rematch':'next',true);else turn+=' Waiting for the host.';}else if(s.status==='abandoned'){message='<h3>Match abandoned.</h3><p>A player left or could not reconnect.<br>No match victory has been awarded.</p>';if(host)buttons=action('Start a new match ↻','rematch',true);turn='You can rematch or leave the table.';}
if(host&&['abandoned','match_results'].includes(s.status))buttons+=action('Return to lobby','lobby');
if(lobby&&host&&s.players.some(p=>!p))buttons+=action('Fill empty seats with bots','bots');
if(s.practice)$('#room-label').textContent=`PRACTICE TABLE · ${roomCode}`;
view('#table-message').innerHTML=message;view('#table-actions').innerHTML=buttons;$('#table-actions').querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>send(b.dataset.action));$('#turn-bar').textContent=turn;$('#turn-bar').classList.toggle('your-turn',!s.paused&&s.turn===me&&s.status==='playing');
const handSignature=JSON.stringify([s.hand,s.legal]);if(previous!==handSignature){view('#hand').innerHTML=s.hand.map(c=>card(c,!s.legal.includes(c))).join('');$('#hand').querySelectorAll('[data-card]').forEach(b=>b.onclick=()=>{if(send('play',{card:b.dataset.card})){b.disabled=true;previous='';sound()}});previous=handSignature;}
if(!s.last)clearCaptures();
renderCapturedPiles(s);
if(s.last&&s.last.number!==lastTrick){lastTrick=s.last.number;animateCapture(s)}
const waitingForWin=Boolean(window.clubCapture?.pending&&window.clubCapture.deal===s.deal&&window.clubCapture.number===s.last?.number&&['deal_results','match_results'].includes(s.status));document.body.classList.toggle('resolving-win',waitingForWin);
renderTableCards(s);renderTrump(s);window.clubVoice?.update(s);if(!waitingForWin)window.clubSocial?.update(s);window.clubChat?.update(s);window.clubAttention?.update(s);window.clubHand?.update();
view('#history').innerHTML=s.history?.length?s.history.slice(-5).reverse().map(t=>`<div class="history-row">${String(t.number).padStart(2,'0')} · ${esc(names[t.winner])} won<small>${t.cards.map(x=>`${esc(x.card.slice(0,-1))}${suits[x.card.slice(-1)]}`).join(' ')}</small></div>`).join(''):'<p>The story starts with the first card.</p>';$('#context-note').textContent=lobby?'Share the invitation link, settle into your teams, and ready up.':s.last?`${names[s.last.winner]} captured the last stack. Keep an eye on those tens.`:'The opening suit isn’t trump. Wait for the first off-suit play.';}
// Rejoin with the same session, preserving the private hand and seat.
(async()=>{const code=location.pathname.match(/^\/room\/([a-z0-9]{6})\/?$/i)?.[1];if(code){roomCode=code.toUpperCase();try{const r=await api('resync');enter(r.state)}catch(error){console.warn(error);$('#code').value=roomCode;openSetup(true)}}})();

$('#delete-table').onclick=async()=>{
    if(!confirm('Delete this table for everyone? The match and room chat will be removed.'))return;
    const button=$('#delete-table');button.disabled=true;
    try{await api('delete');roomCode='';clearTimeout(reconnectTimer);window.clubVoice?.leave(false);socket?.close();location.href='/?table=deleted'}catch(error){toast(error.message);button.disabled=false}
};
if(new URLSearchParams(location.search).get('table')==='deleted')toast('The host deleted this table.');
