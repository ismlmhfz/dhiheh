(()=>{
    const hand=document.querySelector('#hand'),mobile=matchMedia('(max-width:720px)');
    const panel=document.createElement('div');panel.id='hand-selection';
    panel.innerHTML='<span id="selected-card-name" role="status" aria-live="polite"></span>';hand.after(panel);
    const label=panel.querySelector('span');
    let selected=null,pointer=null,pending=null;
    const cards=()=>[...hand.querySelectorAll('[data-card]')];
    function allowed(){return selected&&state?.status==='playing'&&!state.paused&&state.turn===state.seat&&state.legal.includes(selected)&&socket?.readyState===1&&!pending}
    function select(card){
        selected=card?.dataset.card||null;
        for(const c of cards()){const active=c===card;c.classList.toggle('touch-selected',active);c.setAttribute('aria-pressed',String(active))}
        label.textContent=card?`${card.getAttribute('aria-label')}${allowed()?' · Tap to play':pending?' · Sending…':state?.turn!==state?.seat?' · Wait for your turn':' · Not playable'}`:'Slide or tap to select a card';
    }
    function at(x){
        const list=cards();let chosen=list[0];
        for(const card of list){if(x>=card.getBoundingClientRect().left)chosen=card;else break}
        return chosen;
    }
    function commit(){
        if(!allowed())return;
        const card=selected;
        if(send('play',{card})){
            pending=card;select(cards().find(c=>c.dataset.card===selected));sound();
            setTimeout(()=>{if(pending===card){pending=null;refresh()}},2500);
        }
    }
    hand.addEventListener('pointerdown',e=>{
        if(!mobile.matches||!e.isPrimary||e.button>0)return;
        pointer={x:e.clientX,y:e.clientY,moved:false,id:e.pointerId,selected};
        // Capture immediately: raised cards and disabled cards must not break a swipe.
        hand.setPointerCapture(e.pointerId);
    });
    hand.addEventListener('pointermove',e=>{
        if(!pointer||e.pointerId!==pointer.id)return;
        if(Math.abs(e.clientX-pointer.x)>7)pointer.moved=true;
        if(pointer.moved)select(at(e.clientX));
    },{passive:true});
    hand.addEventListener('pointerup',e=>{
        if(!pointer||e.pointerId!==pointer.id)return;
        const gesture=pointer;pointer=null;
        const card=at(e.clientX);
        if(!card)return;
        const vertical=Math.abs(e.clientY-gesture.y)>10;
        if(vertical&&!gesture.moved)return;
        if(!gesture.moved&&card.dataset.card===gesture.selected)commit();else select(card);
    },{passive:true});
    hand.addEventListener('pointercancel',()=>{pointer=null},{passive:true});
    hand.addEventListener('lostpointercapture',()=>{pointer=null},{passive:true});
    // Pointerup owns touch/mouse activation on mobile; suppress the synthetic click.
    hand.addEventListener('click',e=>{
        if(!mobile.matches)return;e.preventDefault();e.stopImmediatePropagation();
        if(e.detail===0){const card=e.target.closest('[data-card]');if(card){if(card.dataset.card===selected)commit();else select(card)}}
    },true);
    function refresh(){
        if(!mobile.matches){for(const c of cards()){c.classList.remove('touch-selected');c.removeAttribute('aria-pressed')}hand.style.removeProperty('--hand-step');hand.style.removeProperty('--hand-width');return}
        const list=cards(),width=Math.max(0,hand.clientWidth-16),cardWidth=Math.min(48,width);
        hand.style.setProperty('--hand-width',`${cardWidth}px`);
        hand.style.setProperty('--hand-step',`${list.length>1?Math.min(cardWidth+5,(width-cardWidth)/(list.length-1)):cardWidth}px`);
        if(pending&&!state?.hand?.includes(pending))pending=null;
        hand.scrollLeft=0;select(list.find(c=>c.dataset.card===selected));
        const hint=document.querySelector('.hand-swipe-hint');if(hint){hint.hidden=false;hint.textContent='Slide to choose · Tap selected card to play'}
    }
    new MutationObserver(()=>requestAnimationFrame(refresh)).observe(hand,{childList:true});
    mobile.addEventListener('change',refresh);new ResizeObserver(refresh).observe(hand);
    window.clubHand={update:refresh};refresh();
})();
