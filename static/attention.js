(()=>{
    const notice=document.createElement('div');notice.id='game-announcement';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');notice.hidden=true;document.body.append(notice);
    const cue=document.createElement('div');cue.id='action-cue';cue.setAttribute('role','status');cue.hidden=true;document.body.append(cue);
    const decision=document.createElement('dialog');decision.id='chase-choice';decision.setAttribute('aria-labelledby','chase-title');
    decision.innerHTML='<div class="choice-eyebrow">YOUR DECISION</div><div class="choice-tens" aria-hidden="true">10♠ 10♥ 10♦ 10♣</div><h2 id="chase-title">Chase all four 10s?</h2><p id="chase-explanation"></p><div id="chase-countdown" role="timer"></div><div class="choice-progress"><i></i></div><div class="choice-buttons"><button type="button" class="primary" data-choice="chase">Chase all four 10s <small>Keep playing for 5 points</small></button><button type="button" class="secondary" data-choice="bank"></button></div><p id="chase-help">Choose now. Your points are banked automatically when time runs out.</p>';
    decision.addEventListener('cancel',e=>e.preventDefault());document.body.append(decision);
    let last=null,room='',announcementTimer,choiceKey='',choiceDuration=15,pendingUntil=0,remaining=0;
    let pendingTrump=null;
    const seen=new Set();const originalTitle=document.title;
    function haptic(pattern){if(document.visibilityState==='visible'&&navigator.vibrate){try{navigator.vibrate(pattern)}catch{}}}
    function announce(key,symbol,title,detail,kind){
        if(seen.has(key))return;seen.add(key);
        if(kind==='win')haptic([120,100,120]);
        clearTimeout(announcementTimer);notice.replaceChildren();
        for(const [tag,cls,text] of [['span','announcement-symbol',symbol],['strong','announcement-title',title],['span','announcement-detail',detail]]){const node=document.createElement(tag);node.className=cls;node.textContent=text;notice.append(node)}
        notice.className=kind;notice.hidden=false;
        notice.getAnimations().forEach(a=>a.cancel());
        if(!matchMedia('(prefers-reduced-motion: reduce)').matches)notice.animate([{opacity:0,transform:'translate(-50%,-50%) scale(.75)'},{opacity:1,transform:'translate(-50%,-50%) scale(1.04)'},{opacity:1,transform:'translate(-50%,-50%) scale(1)'}],{duration:500,easing:'ease-out'});
        announcementTimer=setTimeout(()=>notice.hidden=true,kind==='win'?4500:2800);
    }
    function countdown(){
        if(!decision.open||!last?.decision)return;
        if(!last.paused)remaining=Math.max(0,last.decision.deadline-Date.now()/1000);
        decision.querySelector('#chase-countdown').textContent=last.paused?'Paused · waiting for reconnection':`${Math.ceil(remaining)} seconds to choose`;
        decision.querySelector('.choice-progress i').style.width=`${Math.min(100,remaining/choiceDuration*100)}%`;
        decision.classList.toggle('urgent',remaining<=5&&!last.paused);
        decision.querySelectorAll('[data-choice]').forEach(b=>b.disabled=last.paused||remaining<=0||Date.now()<pendingUntil||socket?.readyState!==1);
    }
    decision.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>{
        if(last?.status!=='chase_decision'||last.decision?.seat!==last.seat||last.paused)return;
        if(send(button.dataset.choice)){pendingUntil=Date.now()+2500;countdown()}
    });
    setInterval(countdown,250);
    window.clubAttention={update(s){
        if(room!==roomCode){room=roomCode;last=null;pendingTrump=null;seen.clear();choiceKey='';notice.hidden=true}
        const previous=last;last=s;
        if(previous&&['match_results','abandoned'].includes(previous.status)&&s.status==='playing'){seen.clear();notice.hidden=true}
        if(s.status==='lobby'){pendingTrump=null;seen.clear();notice.hidden=true}
        const ownTurn=s.status==='playing'&&!s.paused&&s.turn===s.seat;
        const wasOwnTurn=previous?.status==='playing'&&!previous.paused&&previous.turn===previous.seat;
        if(ownTurn&&!wasOwnTurn)haptic(90);
        const collecting=Boolean(window.clubCapture?.pending&&window.clubCapture.deal===s.deal&&window.clubCapture.number===s.last?.number);
        const deciding=s.status==='chase_decision'&&s.decision&&!collecting;
        document.body.classList.toggle('resolving-decision',Boolean(collecting&&s.status==='chase_decision')); 
        document.body.classList.toggle('needs-play',ownTurn);
        document.body.classList.toggle('needs-decision',Boolean(deciding&&s.decision.seat===s.seat));
        cue.hidden=!ownTurn&&!deciding;
        cue.textContent=ownTurn?'YOUR TURN · Play a glowing card':deciding?(s.decision.seat===s.seat?'YOUR DECISION · Bank points or chase four 10s':`${s.players[s.decision.seat]?.name||'Your opponent'} is deciding: bank or chase four 10s`):'';
        document.title=ownTurn?'Your turn! · 10':deciding&&s.decision.seat===s.seat?'Choose: bank or chase · 10':originalTitle;
        if(ownTurn){document.querySelector('#turn-bar').textContent='YOUR TURN — tap a glowing card below';document.querySelector('.seat.bottom')?.classList.add('your-action')}
        if(s.trump&&previous&&previous.deal===s.deal&&!previous.trump){
            const token=pendingTrump={room:roomCode,deal:s.deal,suit:s.trump};
            const movements=[...document.querySelectorAll('#center-cards,.flying-capture')].flatMap(node=>node.getAnimations({subtree:true}));
            Promise.all(movements.map(animation=>animation.finished.catch(()=>{}))).then(()=>{
                if(pendingTrump!==token||roomCode!==token.room||last?.deal!==token.deal||last?.trump!==token.suit||['lobby','abandoned'].includes(last.status)){if(pendingTrump===token)pendingTrump=null;return}
                announce(`${token.deal}:trump:${token.suit}`,suits[token.suit],`${suitNames[token.suit]} is trump!`,'This suit now beats the other suits.','trump');
                setTimeout(()=>{if(pendingTrump===token){pendingTrump=null;if(last)window.clubAttention.update(last)}},2850);
            });
        }
        if(['deal_results','match_results'].includes(s.status)&&!pendingTrump&&!document.body.classList.contains('resolving-win')){
            const match=s.status==='match_results',winner=match?s.winner:s.result?.team;
            announce(`${s.deal}:${s.status}`,'🏆',winner===null?'The match is a tie!':`${teamName(s,winner)} wins ${match?'the match':'the deal'}!`,match?`Final score · ${s.scores[0]} – ${s.scores[1]}`:`${s.result.points} points banked · ${s.scores[0]} – ${s.scores[1]}`,'win');
        }
        if(deciding&&s.decision.seat===s.seat){
            const key=`${s.deal}:${s.last?.number}:${s.decision.seat}`;
            if(choiceKey!==key){choiceKey=key;pendingUntil=0;remaining=Math.max(0,s.decision.deadline-Date.now()/1000);choiceDuration=Math.max(1,remaining)}
            decision.querySelector('#chase-explanation').textContent=`${teamName(s,s.decision.team)} has secured ${s.decision.points} points. Bank them now, or chase all four 10s for 5 points. Your secured points stay locked in.`;
            const bank=decision.querySelector('[data-choice=bank]');bank.replaceChildren(document.createTextNode(`Bank ${s.decision.points} points`));const small=document.createElement('small');small.textContent='Finish this deal now';bank.append(small);
            if(!decision.open)decision.showModal();countdown();
        }else{if(decision.open)decision.close();choiceKey='';pendingUntil=0}
        if(s.status==='abandoned'||s.status==='lobby')notice.hidden=true;
    }};
    if(state)window.clubAttention.update(state);
})();
