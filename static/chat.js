(()=>{
    const button=document.createElement('button');button.type='button';button.className='secondary';button.id='open-chat';button.textContent='Chat';
    document.querySelector('.room-tools').prepend(button);
    const dialog=document.createElement('dialog');dialog.id='room-chat';
    dialog.innerHTML='<div class="chat-heading"><div><h2>Room chat</h2><small>Everyone at this table · Last 100 messages</small></div><button type="button" id="close-chat" aria-label="Close chat">×</button></div><div id="chat-messages" role="log" aria-label="Room messages" aria-live="polite"></div><p id="chat-status" role="status"></p><form id="chat-form"><label for="chat-input" class="chat-label">Message your table · 120 characters max</label><div class="chat-compose"><input id="chat-input" maxlength="120" autocomplete="off" placeholder="Say something…" required><button class="primary" type="submit">Send</button></div></form>';
    document.body.append(dialog);
    const rename=document.createElement('button');rename.type='button';rename.className='secondary';rename.id='rename-team';rename.textContent='Team name';
    document.querySelector('.room-tools').append(rename);
    const teamDialog=document.createElement('dialog');teamDialog.id='team-name-dialog';
    teamDialog.innerHTML='<form><h2>Name your team</h2><p>Choose your team name before starting. Names lock during the match.</p><label for="team-name-input">Team name · 18 characters max</label><input id="team-name-input" maxlength="18" required autocomplete="off"><div class="team-name-actions"><button type="button" class="secondary">Cancel</button><button type="submit" class="primary">Save name</button></div></form>';
    document.body.append(teamDialog);
    rename.onclick=()=>{if(!state||state.status!=='lobby')return;teamDialog.querySelector('input').value=teamName(state,state.players[state.seat]?.team??state.seat%2);teamDialog.showModal();teamDialog.querySelector('input').focus()};
    teamDialog.querySelector('[type=button]').onclick=()=>teamDialog.close();
    teamDialog.querySelector('form').onsubmit=e=>{e.preventDefault();const name=teamDialog.querySelector('input').value.trim();if(name&&send('team_name',{name}))teamDialog.close()};
    const list=dialog.querySelector('#chat-messages'),input=dialog.querySelector('#chat-input'),status=dialog.querySelector('#chat-status');
    const lobbyChat=document.createElement('section');lobbyChat.id='lobby-chat';lobbyChat.hidden=true;
    lobbyChat.innerHTML='<h3>Room chat</h3><div id="lobby-chat-messages" role="log" aria-live="polite" aria-label="Room messages"></div><form id="lobby-chat-form"><div class="chat-compose"><input id="lobby-chat-input" aria-label="Message the room" placeholder="Message the room…" maxlength="120" autocomplete="off" required><button class="primary" type="submit">Send</button></div><small id="lobby-chat-status" role="status"></small></form>';
    document.querySelector('.hand-dock').before(lobbyChat);
    const lobbyAnchor=document.createComment('Lobby chat location');lobbyChat.before(lobbyAnchor);
    const lobbyList=lobbyChat.querySelector('#lobby-chat-messages'),lobbyInput=lobbyChat.querySelector('input');
    const quick=document.createElement('form');quick.id='quick-chat';
    quick.innerHTML='<label for="quick-chat-input">Message the table</label><div class="chat-compose"><input id="quick-chat-input" maxlength="120" autocomplete="off" placeholder="Say something…" required><button class="primary" type="submit">Send</button></div><small id="quick-chat-status" role="status"></small>';
    document.querySelector('.hand-dock').after(quick);
    const bottomTools=document.createElement('nav');bottomTools.id='room-bottom-tools';bottomTools.setAttribute('aria-label','Room actions');
    document.querySelector('#room').append(bottomTools);
    const roomActions=['open-chat','invite','rename-team','leave','delete-table'].map(id=>document.getElementById(id));
    const mobileLayout=matchMedia('(max-width:720px)'),wideLayout=matchMedia('(min-width:1200px)');
    const voicePanel=document.querySelector('.voice-panel'),voiceAnchor=document.createComment('Voice panel location');voicePanel.before(voiceAnchor);
    const quickAnchor=document.createComment('Inline chat location');quick.before(quickAnchor);
    const sidebar=document.createElement('section');sidebar.id='desktop-room-social';sidebar.setAttribute('aria-label','Room conversation');document.querySelector('.activity').prepend(sidebar);
    const composer=document.createElement('dialog');composer.id='quick-message-dialog';composer.innerHTML='<div class="chat-heading"><div><h2>Room chat</h2><small>Last 100 messages · 120 characters max</small></div><button type="button" aria-label="Close message">×</button></div>';document.body.append(composer);
    const quickList=document.createElement('div');quickList.id='quick-chat-messages';quickList.setAttribute('role','log');quickList.setAttribute('aria-label','Room messages');quickList.setAttribute('aria-live','polite');composer.append(quickList);
    composer.querySelector('button').onclick=()=>composer.close();
    const messageButton=document.createElement('button');messageButton.id='quick-message-button';messageButton.type='button';messageButton.setAttribute('aria-label','Room chat and messages');messageButton.title='Room chat and messages';messageButton.innerHTML='<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 11a8 8 0 0 1-8 8H5l-4 3 1.5-6A8 8 0 1 1 20 11Z"/><path d="M6 9h10M6 13h7"/></svg>';
    const toolbar=document.createElement('div');toolbar.id='table-toolbar';const trump=document.querySelector('#table-trump');trump.before(toolbar);toolbar.append(trump,document.querySelector('#voice-inline'),messageButton);
    messageButton.onclick=()=>{if(quick.parentElement!==composer)composer.append(quick);composer.showModal();unread=0;button.textContent='Chat';quickList.scrollTop=quickList.scrollHeight;quick.querySelector('input').focus({preventScroll:true})};
    const phoneTools=document.querySelector('.phone-tools'),phoneAnchor=document.createComment('Phone controls');phoneTools.before(phoneAnchor);
    const groupLink=document.querySelector('.group-back');
    [...roomActions,phoneTools,groupLink].filter(Boolean).forEach(node=>node.classList.add('room-menu-control'));
    function placeLobby(){const parent=wideLayout.matches&&state?.status==='lobby'?sidebar:lobbyAnchor.parentElement;if(lobbyChat.parentElement!==parent){if(parent===sidebar)sidebar.prepend(lobbyChat);else lobbyAnchor.after(lobbyChat)}}
    function arrangeRoom(){
        placeLobby();
        const actions=mobileLayout.matches?document.querySelector('#site-nav'):document.querySelector('.room-tools');roomActions.forEach(node=>actions.append(node));if(groupLink)actions.append(groupLink);
        if(mobileLayout.matches){document.querySelector('#site-nav').append(phoneTools);composer.append(quick)}else{composer.close();phoneAnchor.after(phoneTools)}
        if(wideLayout.matches){sidebar.append(quick,voicePanel)}else{if(!mobileLayout.matches)quickAnchor.after(quick);voiceAnchor.after(voicePanel)}
        window.clubMenu?.arrange();
    }
    composer.addEventListener('close',arrangeRoom);
    mobileLayout.addEventListener('change',arrangeRoom);wideLayout.addEventListener('change',arrangeRoom);arrangeRoom();
    const quickInput=quick.querySelector('input'),quickStatus=quick.querySelector('small');
    const setStatus=text=>{status.textContent=text;quickStatus.textContent=text;lobbyChat.querySelector('small').textContent=text};
    let pendingInput=null;
    const bubbles=new Map();let seatingRevision=null;
    let messages=new Map(),unread=0,pending=null;
    function draw(){
        const nearBottom=list.scrollHeight-list.scrollTop-list.clientHeight<60;
        list.replaceChildren();
        for(const m of [...messages.values()].sort((a,b)=>a.id-b.id)){
            const row=document.createElement('article'),name=document.createElement('strong'),time=document.createElement('time'),text=document.createElement('p');
            name.textContent=m.name;time.dateTime=m.time;time.textContent=new Date(m.time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});text.textContent=m.text;
            row.append(name,time,text);list.append(row);
        }
        if(!messages.size){const empty=document.createElement('p');empty.className='chat-empty';empty.textContent='No messages yet. Say hello to your table!';list.append(empty)}
        if(nearBottom)list.scrollTop=list.scrollHeight;
        const quickBottom=quickList.scrollHeight-quickList.scrollTop-quickList.clientHeight<60;quickList.replaceChildren(...[...list.childNodes].map(node=>node.cloneNode(true)));if(quickBottom)quickList.scrollTop=quickList.scrollHeight;
        const lobbyBottom=lobbyList.scrollHeight-lobbyList.scrollTop-lobbyList.clientHeight<60;lobbyList.replaceChildren(...[...list.childNodes].map(node=>node.cloneNode(true)));if(lobbyBottom)lobbyList.scrollTop=lobbyList.scrollHeight;
    }
    function finish(){pending=null;pendingInput=null;dialog.querySelector('[type=submit]').disabled=false;quick.querySelector('button').disabled=false;lobbyChat.querySelector('button').disabled=false}
    button.onclick=()=>{dialog.showModal();unread=0;button.textContent='Chat';list.scrollTop=list.scrollHeight;dialog.querySelector('#close-chat').focus({preventScroll:true})};
    dialog.querySelector('#close-chat').onclick=()=>dialog.close();
    function submitMessage(event,source){
        event.preventDefault();if(pending)return;
        if(!source.value.trim())return;
        if(socket?.readyState!==1){setStatus('Reconnecting. Your draft is saved; try again when connected.');return}
        pending={text:source.value,command:crypto.randomUUID()};pendingInput=source;
        socket.send(JSON.stringify({action:'chat.send',...pending}));
        dialog.querySelector('[type=submit]').disabled=true;quick.querySelector('button').disabled=true;lobbyChat.querySelector('button').disabled=true;setStatus('Sending…');
    }
    dialog.querySelector('form').onsubmit=event=>submitMessage(event,input);
    quick.onsubmit=event=>submitMessage(event,quickInput);
    lobbyChat.querySelector('form').onsubmit=event=>submitMessage(event,lobbyInput);
    // Keep drafts on interruption. The next history snapshot confirms delivery.
    setInterval(()=>{if(pending&&socket?.readyState!==1){finish();setStatus('Connection interrupted. Check the chat before sending again.')}},500);
    window.clubChat={update(s){
        placeLobby();
        const wasHidden=lobbyChat.hidden;lobbyChat.hidden=s.status!=='lobby';if(!lobbyChat.hidden){unread=0;button.textContent='Chat';if(wasHidden)lobbyList.scrollTop=lobbyList.scrollHeight}
        rename.hidden=s.status!=='lobby';if(s.status!=='lobby'&&teamDialog.open)teamDialog.close();
        const revision=s.seating_revision||0;
        if(seatingRevision!==null&&seatingRevision!==revision){
            const moved=[...bubbles].map(([seat,b])=>[Number(s.seating_map?.[seat]??seat),b]);bubbles.clear();for(const [seat,b] of moved)bubbles.set(seat,b);
        }
        seatingRevision=revision;
        document.querySelectorAll('.avatar-chat-bubble').forEach(node=>node.remove());
        for(const [seat,b] of bubbles){
            if(Date.now()>b.until){bubbles.delete(seat);continue}
            const avatar=document.querySelector(`[data-seat-index="${seat}"] .avatar`);
            if(avatar){const bubble=document.createElement('span');bubble.className='avatar-chat-bubble';bubble.textContent=b.text;avatar.append(bubble)}
        }
    },receive(event){
        if(event.type==='chat.sent'){if(pending?.command===event.command){const source=pendingInput;if(source?.value===pending.text)source.value='';finish();setStatus('');if(source===quickInput&&composer.open){source.blur();composer.close()}else if(source===input&&dialog.open){source.blur();dialog.close()}}return}
        if(event.type==='chat.error'){finish();setStatus(event.error);return}
        if(event.type==='chat.history'){messages=new Map(event.messages.map(m=>[m.id,m]));finish();setStatus('');draw();return}
        if(event.type==='chat.message'){
            const m=event.message,isNew=!messages.has(m.id);messages.set(m.id,m);
            if(isNew&&Number.isInteger(m.seat)&&m.revision===(state?.seating_revision||0)){
                bubbles.set(m.seat,{text:m.text,until:Date.now()+6500});window.clubChat.update(state);
                setTimeout(()=>{if(state)window.clubChat.update(state)},6600);
            }
            while(messages.size>100)messages.delete(Math.min(...messages.keys()));
            if(isNew&&!dialog.open&&!composer.open&&lobbyChat.hidden){unread++;button.textContent=`Chat (${unread})`}
            draw();
        }
    }};
})();
