/* Appearance and room audio are independent of the game engine. */
(()=>{
    const appearance=JSON.parse(document.getElementById('appearance-config').textContent);
    const authenticated=Boolean(appearance.nickname);
    if(authenticated){localStorage.setItem('ten-name',appearance.nickname);localStorage.setItem('ten-avatar',appearance.avatar);localStorage.setItem('ten-deck',appearance.deck)}
    const deckPicker=$('#deck-picker');
    const applyDeck=deck=>{document.body.dataset.deck=deck;localStorage.setItem('ten-deck',deck);deckPicker.value=deck};
    const savePreferences=async changes=>{
        if(!authenticated)return;
        try{await api('preferences',changes)}catch(error){toast(error.message)}
    };
    function pickAvatar(avatar){
        localStorage.setItem('ten-avatar',avatar);
        $('#avatar-picker').querySelectorAll('button').forEach(b=>{const selected=b.dataset.avatar===avatar;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected))});
        if(state&&socket?.readyState===1)send('appearance',{avatar});
    }
    $('#avatar-picker').innerHTML=Object.entries(avatarIcons).map(([key,icon])=>`<button class="avatar-choice" data-avatar="${key}" title="${key}" aria-label="Choose ${key} avatar" aria-pressed="false">${icon}</button>`).join('');
    $('#avatar-picker').querySelectorAll('button').forEach(b=>b.onclick=()=>{pickAvatar(b.dataset.avatar);savePreferences({avatar:b.dataset.avatar})});
    pickAvatar(localStorage.getItem('ten-avatar')||'fox');
    applyDeck(localStorage.getItem('ten-deck')||'cosmic');
    deckPicker.onchange=()=>{applyDeck(deckPicker.value);savePreferences({deck:deckPicker.value})};
    const details=$('.table-drawer');
    if(innerWidth>1150)details.open=true;
    matchMedia('(min-width:1151px)').addEventListener('change',event=>{details.open=event.matches});
    const phoneScores=document.createElement('section');phoneScores.className='phone-scores';phoneScores.setAttribute('aria-label','Match scores');$('.play-area').before(phoneScores);
    const teamPicker=document.createElement('section');teamPicker.className='team-picker';teamPicker.setAttribute('aria-label','Choose your team');$('#table').before(teamPicker);
    teamPicker.addEventListener('click',event=>{const button=event.target.closest('[data-team]');if(button)send('team',{team:Number(button.dataset.team)})});
    const handHint=document.createElement('span');handHint.className='hand-swipe-hint';handHint.textContent='Swipe to see all cards ↔';$('#hand').after(handHint);
    $('#hand').setAttribute('aria-label','Your cards. Swipe horizontally to see more.');$('#hand').tabIndex=0;
    const tools=document.createElement('div');tools.className='phone-tools';tools.innerHTML='<button type="button" data-panel="voice">🎙 Voice <span id="phone-voice-count"></span></button><button type="button" data-panel="history">▤ Stacks &amp; history</button>';
    $('.hand-dock').after(tools);
    const sheet=document.createElement('dialog');sheet.id='room-sheet';sheet.innerHTML='<div class="sheet-handle"></div><div class="sheet-heading"><h2 id="sheet-title"></h2><button type="button" class="sheet-close" aria-label="Close panel">×</button></div><div id="sheet-content"></div>';
    document.body.append(sheet);
    let movedPanel=null,placeholder=null,previousDrawerOpen=false;
    function closeSheet(){sheet.close()}
    sheet.querySelector('.sheet-close').onclick=closeSheet;
    sheet.addEventListener('click',event=>{if(event.target===sheet){const r=sheet.getBoundingClientRect();if(event.clientY<r.top||event.clientY>r.bottom||event.clientX<r.left||event.clientX>r.right)closeSheet()}});
    sheet.addEventListener('close',()=>{if(movedPanel&&placeholder){placeholder.replaceWith(movedPanel);details.open=previousDrawerOpen}movedPanel=placeholder=null});
    tools.querySelectorAll('button').forEach(button=>button.onclick=()=>{
        if(sheet.open)return;
        movedPanel=button.dataset.panel==='voice'?$('.voice-panel'):$('.activity');
        placeholder=document.createComment('Mobile panel location');movedPanel.before(placeholder);
        previousDrawerOpen=details.open;if(button.dataset.panel==='history')details.open=true;
        $('#sheet-title').textContent=button.dataset.panel==='voice'?'Party voice':'Stacks & history';
        $('#sheet-content').append(movedPanel);sheet.showModal();
    });
    matchMedia('(min-width:721px)').addEventListener('change',event=>{if(event.matches&&sheet.open)closeSheet()});
    const updateHandHint=()=>{handHint.hidden=$('#hand').scrollWidth<=$('#hand').clientWidth+2};
    new ResizeObserver(updateHandHint).observe($('#hand'));
    let celebrationKey='';
    window.clubSocial={update(s){
        document.body.dataset.inGame=String(s.status!=='lobby');
        teamPicker.hidden=s.status!=='lobby';
        if(s.status==='lobby'){
            const counts=[0,1].map(team=>s.players.filter((p,i)=>p&&(p.team??i%2)===team).length);
            const selected=s.players[s.seat]?.team??s.seat%2;
            morph(teamPicker,`<h3>Who’s on your team?</h3><p>Switch teams until everyone agrees. Teammates sit opposite when the match starts.</p><div class="team-options">${[0,1].map(team=>`<section class="team-option ${selected===team?'chosen':''} ${team?'amber-team':'fern-team'}"><div class="team-option-title"><strong>Team ${esc(teamName(s,team))}</strong><span>${counts[team]} / 2 players</span></div><div class="team-members">${s.players.map((p,i)=>p&&(p.team??i%2)===team?`<span class="lobby-player" data-ready-seat="${i}"><span class="lobby-player-name">${avatarIcons[p.avatar]||Object.values(avatarIcons)[i]} ${esc(p.name)}${i===s.seat?' · You':''}</span><b class="ready-state ${p.connected&&p.ready?'is-ready':''}">${!p.connected?'Reconnecting':p.ready?'✓ Ready':'Not ready'}</b></span>`:'').join('')||'<small>No players yet</small>'}</div><button type="button" data-team="${team}" aria-pressed="${selected===team}" ${selected===team?'disabled':''}>${selected===team?'✓ Your team':`Join ${esc(teamName(s,team))}`}</button></section>`).join('')}</div><div class="team-balance-note" role="status">${counts[0]===2&&counts[1]===2?'Teams balanced! Everyone can ready up.':'Need exactly 2 players on each team to start.'} Changing teams clears everyone’s ready status.</div>`);
            const start=$('[data-action="start"]');
            if(start){start.disabled=counts.some(n=>n!==2)||!s.players.every(p=>p&&p.ready&&p.connected);start.title=start.disabled?'Two players per team, all connected and ready.':'Start the match'}
        }
        const target={quick:8,standard:12,long:18}[s.mode];
        morph(phoneScores,`<div class="phone-match-meta"><span>DEAL ${s.deal||'—'} <span class="phone-mode">· ${s.mode}</span></span><span>First to ${target}</span></div><div class="phone-team-row">${[0,1].map(team=>`<div class="phone-team ${team===s.seat%2?'my-team':''}"><div><strong><i class="dot ${team?'b':'a'}"></i>${esc(teamName(s,team))}${team===s.seat%2?' · You':''}</strong><small>${s.stacks?.[team]||0} stacks · ${s.tens?.[team]?.length||0} tens <span>${(s.tens?.[team]||[]).map(suit=>suits[suit]).join(' ')}</span></small></div><b>${s.scores?.[team]||0}</b></div>`).join('')}</div>`);
        $('#phone-voice-count').textContent=s.players.filter(p=>p?.voice).length||'';
        updateHandHint();
        const key=`${roomCode}:${s.deal}:${s.status}`;
        if(['deal_results','match_results'].includes(s.status)&&key!==celebrationKey){
            celebrationKey=key;
            if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
            const confetti=document.createElement('div');confetti.className='celebration';confetti.setAttribute('aria-hidden','true');
            confetti.innerHTML=Array.from({length:35},(_,i)=>`<i class="confetti" style="--confetti-left:${Math.random()*100}%;--confetti-color:${['#ffdb70','#9b7bfa','#8be7cf','#ff8fbe'][i%4]};--confetti-delay:${Math.random()*.4}s"></i>`).join('');
            document.body.append(confetti);setTimeout(()=>confetti.remove(),2800);
        }
    }};

    const voice={ready:false,session:null,joinTimer:null,recovering:false,stream:null,peers:new Map(),meters:new Map(),speaking:new Set(),muted:false,deafened:false,joining:false,audioContext:null,timer:null,epoch:0,previousAudioType:null,outputStream:null,effects:null,effectBusy:false,effectFailed:false};
    let config=JSON.parse($('#voice-config').textContent);
    const recovery=document.createElement('button');recovery.id='voice-recover';recovery.className='secondary';recovery.hidden=true;recovery.textContent='Tap to resume voice audio';$('.hand-dock').after(recovery);
    const showResume=show=>{$('#voice-play').hidden=!show;recovery.hidden=!show};
    const effectControl=document.createElement('label');effectControl.className='voice-effect-control';effectControl.innerHTML='<span>Voice effect</span><select id="voice-effect" aria-describedby="voice-effect-status"><option value="normal">Normal voice</option><option value="high">High pitch</option><option value="low">Low pitch</option><option value="scary">Scary</option><option value="robot">Robot</option></select><small id="voice-effect-status" role="status">Choose an effect while connected. Everyone in voice hears it.</small>';$('#voice-controls').after(effectControl);effectControl.hidden=true;
    const effectSelect=effectControl.querySelector('select'),effectStatus=effectControl.querySelector('small');
    async function changeEffect(effect){
        if(!voice.stream||voice.effectBusy)return;
        voice.effectBusy=true;effectSelect.disabled=true;const epoch=voice.epoch;
        try{
            voice.effects??=new PartyVoiceEffects(voice.audioContext,voice.stream,()=>{voice.effectFailed=true;if(!voice.effectBusy){voice.effectFailed=false;changeEffect('normal')}});
            const output=await voice.effects.select(effect);
            if(epoch!==voice.epoch)return;
            const track=output.getAudioTracks()[0];track.enabled=!(voice.muted||voice.deafened);
            voice.outputStream=output;
            await Promise.all([...voice.peers.values()].flatMap(peer=>peer.pc.getSenders().filter(s=>s.track?.kind==='audio').map(s=>s.replaceTrack(track))));
            if(epoch!==voice.epoch)return;
            effectSelect.value=effect;meter(state.seat,output);
            if(effect==='normal'){voice.effects?.close();voice.effects=null}
            effectStatus.textContent=effect==='normal'?'Your normal voice is on.':'Live: '+effectSelect.selectedOptions[0].textContent+'. Everyone in voice hears this effect.';
        }catch(error){
            if(epoch!==voice.epoch)return;
            voice.outputStream=voice.stream;const track=voice.stream.getAudioTracks()[0];track.enabled=!(voice.muted||voice.deafened);
            await Promise.allSettled([...voice.peers.values()].flatMap(peer=>peer.pc.getSenders().filter(s=>s.track?.kind==='audio').map(s=>s.replaceTrack(track))));
            if(epoch!==voice.epoch)return;
            voice.effects?.close();voice.effects=null;
            effectSelect.value='normal';effectStatus.textContent=error.message;meter(state.seat,voice.stream);
        }finally{if(epoch===voice.epoch){voice.effectBusy=false;effectSelect.disabled=false;if(voice.effectFailed){voice.effectFailed=false;changeEffect('normal')}}}
    }
    effectSelect.onchange=()=>changeEffect(effectSelect.value);
    const status=text=>{$('#voice-status').textContent=text};
    const transmit=(action,data={})=>{if(socket?.readyState===1)socket.send(JSON.stringify({action,session:voice.session,revision:state?.seating_revision||0,...data}))};
    function markSpeaking(){
        document.querySelectorAll('[data-seat-index]').forEach(node=>{
            const seat=Number(node.dataset.seatIndex),p=state?.players[seat];
            node.classList.toggle('speaking',voice.speaking.has(seat));
            let badge=node.querySelector('.voice-badge');
            if(p?.voice){if(!badge){badge=document.createElement('span');badge.className='voice-badge';node.querySelector('.name')?.append(badge)}badge.textContent=p.voice_muted?' 🔇':' 🎙';badge.title=p.voice_muted?'Microphone muted':'In room voice'}else badge?.remove();
        });
        document.querySelectorAll('[data-voice-seat]').forEach(node=>node.classList.toggle('speaking',voice.speaking.has(Number(node.dataset.voiceSeat))));
    }
    function meter(seat,stream){
        if(!voice.audioContext)return;
        voice.meters.get(seat)?.source.disconnect();
        try{const source=voice.audioContext.createMediaStreamSource(stream),analyser=voice.audioContext.createAnalyser();analyser.fftSize=256;source.connect(analyser);voice.meters.set(seat,{source,analyser,data:new Uint8Array(256)})}catch{}
    }
    function dropPeer(seat){
        const peer=voice.peers.get(seat);
        if(peer){clearTimeout(peer.reconnectTimer);clearTimeout(peer.connectTimer);peer.pc.onconnectionstatechange=null;peer.pc.onicecandidate=null;peer.pc.onnegotiationneeded=null;peer.pc.ontrack=null;voice.peers.delete(seat);peer.pc.close();if(peer.audio){peer.audio.onpause=null;peer.audio.srcObject=null;peer.audio.remove()}}
        voice.meters.get(seat)?.source.disconnect();voice.meters.delete(seat);voice.speaking.delete(seat);
    }
    const current=peer=>voice.ready&&voice.epoch===peer.epoch&&voice.peers.get(peer.seat)===peer;
    function signalPeer(peer,signal){if(current(peer))transmit('voice.signal',{target:peer.seat,target_session:peer.session,signal})}
    function connectionStatus(){
        if(!voice.ready)return;
        const expected=state.players.filter((p,i)=>p?.voice&&i!==state.seat).length;
        const connected=[...voice.peers.values()].filter(p=>p.pc.connectionState==='connected').length;
        if(connected<expected||[...voice.peers.values()].some(p=>p.pc.connectionState!=='connected'))status(`Connecting voice (${connected}/${Math.max(expected,voice.peers.size)})…`);
        else if(!voice.deafened&&[...voice.peers.values()].some(p=>p.audio?.paused)){showResume(true);status('Tap to resume voice audio.')}
        else status(voice.deafened?'Incoming audio and microphone are off.':voice.muted?'Microphone muted. You can still listen.':connected?'Voice connected to everyone.':'Voice connected. Waiting for friends to join.');
    }
    function restartPeer(peer){
        if(!current(peer))return;
        if(state.seat<peer.seat)peer.pc.restartIce();else signalPeer(peer,{restart:true});
    }
    function peerFor(seat,session=null){
        const existing=voice.peers.get(seat);
        if(existing?.session===session)return existing;
        if(existing)dropPeer(seat);
        const pc=new RTCPeerConnection(config),peer={pc,seat,session,epoch:voice.epoch,candidates:[],queue:Promise.resolve(),retries:0};
        voice.peers.set(seat,peer);
        const outgoing=voice.outputStream||voice.stream;outgoing.getTracks().forEach(track=>pc.addTrack(track,outgoing));
        pc.onicecandidate=e=>{if(e.candidate)signalPeer(peer,{candidate:e.candidate.toJSON()})};
        // One designated offerer per pair avoids simultaneous offers, including ICE recovery.
        pc.onnegotiationneeded=()=>{
            if(state.seat>=peer.seat)return;
            peer.queue=peer.queue.then(async()=>{
                if(!current(peer)||pc.signalingState!=='stable')return;
                await pc.setLocalDescription();
                if(current(peer))signalPeer(peer,{description:{type:pc.localDescription.type,sdp:pc.localDescription.sdp}});
            }).catch(error=>{if(current(peer))console.warn('Voice negotiation',error.message)});
        };
        pc.ontrack=event=>{
            if(!current(peer))return;
            const stream=event.streams[0]||new MediaStream([event.track]);
            if(!peer.audio){peer.audio=document.createElement('audio');peer.audio.autoplay=true;peer.audio.setAttribute('playsinline','');peer.audio.setAttribute('webkit-playsinline','');peer.audio.onpause=()=>{if(current(peer)&&!voice.deafened)showResume(true)};document.body.append(peer.audio)}
            peer.audio.srcObject=stream;peer.audio.muted=voice.deafened;
            peer.audio.play().catch(()=>{if(current(peer))showResume(true)});meter(peer.seat,stream);
        };
        peer.connectTimer=setTimeout(()=>{if(current(peer)&&pc.connectionState!=='connected')restartPeer(peer)},12000);
        pc.onconnectionstatechange=()=>{
            if(!current(peer))return;
            if(pc.connectionState==='disconnected'){clearTimeout(peer.reconnectTimer);peer.reconnectTimer=setTimeout(()=>restartPeer(peer),3000)}
            if(pc.connectionState==='failed'&&peer.retries++<2)restartPeer(peer);
            if(pc.connectionState==='connected'){clearTimeout(peer.reconnectTimer);clearTimeout(peer.connectTimer);peer.retries=0}
            connectionStatus();update(state);
        };
        return peer;
    }
    function receive(message){
        if(message.type==='voice.error'){
            if(message.session!==voice.session)return;
            leave();status(message.error+' Tap Join voice to reconnect.');return;
        }
        if(message.revision!==undefined&&message.revision!==(state?.seating_revision||0))return;
        if(!voice.stream)return;
        if(message.type==='voice.peers'){
            if(message.session!==voice.session)return;
            voice.ready=true;clearTimeout(voice.joinTimer);
            for(const seat of message.peers)peerFor(seat,message.sessions?.[seat]??null);
            applyMute();connectionStatus();return;
        }
        if(!voice.ready)return;
        if(message.type==='voice.joined'){
            if(message.seat!==state.seat)peerFor(message.seat,message.session??null);
            connectionStatus();return;
        }
        if(message.type==='voice.left'){
            if(voice.peers.get(message.seat)?.session===(message.session??null))dropPeer(message.seat);
            connectionStatus();return;
        }
        if(message.type!=='voice.signal'||message.target_session!==voice.session)return;
        const peer=voice.peers.get(message.seat);
        // A join/peers acknowledgement must introduce a peer before it may signal.
        if(!peer||peer.session!==(message.session??null))return;
        peer.queue=peer.queue.then(async()=>{
            if(!current(peer))return;
            const pc=peer.pc,signal=message.signal;
            if(signal.restart){if(state.seat<peer.seat)pc.restartIce();return}
            if(signal.description){
                const description=signal.description;
                // Legacy clients can still send competing offers; the lower seat wins.
                if(description.type==='offer'&&state.seat<peer.seat)return;
                await pc.setRemoteDescription(description);
                if(!current(peer))return;
                for(const candidate of peer.candidates)await pc.addIceCandidate(candidate);
                peer.candidates=[];
                if(description.type==='offer'){
                    await pc.setLocalDescription();
                    if(current(peer))signalPeer(peer,{description:{type:pc.localDescription.type,sdp:pc.localDescription.sdp}});
                }
            }else if(signal.candidate){
                if(pc.remoteDescription)await pc.addIceCandidate(signal.candidate);else peer.candidates.push(signal.candidate);
            }
        }).catch(error=>{if(current(peer)){console.warn('Voice signaling',error.message);connectionStatus()}});
        return peer.queue;
    }
    async function join(){
        if(voice.joining||voice.stream)return;
        if(!state||socket?.readyState!==1){toast('Connect to a room first.');return}
        if(!navigator.mediaDevices?.getUserMedia){status('Voice needs HTTPS or localhost and a microphone-capable browser.');return}
        const epoch=++voice.epoch;
        voice.session=crypto.randomUUID();voice.ready=false;voice.joining=true;$('#voice-join').disabled=true;status('Allow microphone access to join your room.');
        try{
            try{if(navigator.audioSession){voice.previousAudioType=navigator.audioSession.type;navigator.audioSession.type='play-and-record'}}catch{}
            // Request capture directly in the join gesture, before network awaits.
            const capture=navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
            try{voice.audioContext=new (window.AudioContext||window.webkitAudioContext)();voice.audioContext.resume().catch(()=>{});voice.audioContext.onstatechange=()=>{if(voice.stream&&voice.audioContext?.state!=='running')showResume(true)}}catch{}
            const stream=await capture;
            if(epoch!==voice.epoch){stream.getTracks().forEach(t=>t.stop());return}
            voice.stream=stream;
            config=await api('voice_config');
            if(epoch!==voice.epoch)return;
            if(socket?.readyState!==1){stream.getTracks().forEach(t=>t.stop());throw Error('Room disconnected. Please reconnect first.')}
            voice.stream=stream;
            stream.getAudioTracks().forEach(t=>t.enabled=!(voice.muted||voice.deafened));
            voice.audioContext?.resume().catch(()=>{});
            meter(state.seat,stream);
            stream.getAudioTracks()[0].onmute=()=>{showResume(true);status('Your device paused the microphone. Return to the call or tap Repair voice.')};
            stream.getAudioTracks()[0].onunmute=()=>{resumeAudio()};
            stream.getAudioTracks()[0].onended=()=>{leave();status('Microphone disconnected. Connect a microphone and rejoin.')};
            voice.timer=setInterval(()=>{
                voice.speaking.clear();
                for(const [seat,m] of voice.meters){m.analyser.getByteTimeDomainData(m.data);let sum=0;for(const value of m.data)sum+=(value-128)**2;if(Math.sqrt(sum/m.data.length)>3)voice.speaking.add(seat)}
                markSpeaking();
            },150);
            transmit('voice.join');
            voice.joinTimer=setTimeout(()=>{if(epoch===voice.epoch&&!voice.ready){leave();status('Voice could not reconnect. Tap Join voice to retry.')}},15000);update(state);
        }catch(error){leave(false);status(error.name==='NotAllowedError'?'Microphone access was denied. Allow it in your browser, then try again.':error.name==='NotFoundError'?'No microphone found. Connect one and try again.':error.message||'Unable to start voice.');}
        finally{voice.joining=false;$('#voice-join').disabled=false}
    }
    function leave(notify=true){
        voice.ready=false;clearTimeout(voice.joinTimer);voice.epoch++;voice.effects?.close();voice.effects=null;voice.outputStream=null;voice.effectBusy=false;voice.effectFailed=false;effectSelect.value='normal';effectSelect.disabled=false;effectStatus.textContent='Choose an effect while connected. Everyone in voice hears it.';
        try{if(navigator.audioSession&&voice.previousAudioType!==null)navigator.audioSession.type=voice.previousAudioType}catch{}
        voice.previousAudioType=null;
        if(notify&&voice.stream)transmit('voice.leave');
        for(const track of voice.stream?.getTracks()||[]){track.onended=null;track.onmute=null;track.onunmute=null;track.stop()}
        voice.stream=null;
        for(const seat of [...voice.peers.keys()])dropPeer(seat);
        for(const m of voice.meters.values())m.source.disconnect();voice.meters.clear();
        voice.audioContext?.close().catch(()=>{});voice.audioContext=null;clearInterval(voice.timer);voice.speaking.clear();
        voice.muted=false;voice.deafened=false;showResume(false);update(state);status('Voice disconnected. Join whenever you’re ready.');
    }
    function applyMute(){
        const muted=voice.muted||voice.deafened;
        voice.stream?.getAudioTracks().forEach(track=>track.enabled=!muted);
        voice.outputStream?.getAudioTracks().forEach(track=>track.enabled=!muted);
        for(const peer of voice.peers.values())if(peer.audio)peer.audio.muted=voice.deafened;
        transmit('voice.mute',{muted});
        status(voice.deafened?'Deafened. Your microphone and incoming audio are off.':voice.muted?'Microphone muted. You can still listen.':'Voice connected. Say hello!');update(state);
    }
    const inlineControls=document.createElement('div');inlineControls.id='voice-inline';inlineControls.hidden=true;inlineControls.setAttribute('role','group');inlineControls.setAttribute('aria-label','Voice controls');
    const voiceIcons={mute:'<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',deafen:'<path d="m11 5-6 4H2v6h3l6 4ZM15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14"/>',leave:'<path d="M5 16v4H2v-5c0-8 20-8 20 0v5h-3v-4l-4-2H9Z"/>'};
    for(const [name,icon] of Object.entries(voiceIcons)){const b=document.createElement('button');b.type='button';b.id='inline-voice-'+name;b.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+icon+'<path class="voice-slash" d="M3 3 21 21"/></svg>';b.onclick=()=>$('#voice-'+name).click();inlineControls.append(b)}
    $('.voice-panel').append(inlineControls);
    let voiceSeatingRevision=null;
    function update(s){
        if(!s)return;
        const revision=s.seating_revision||0;
        if(voiceSeatingRevision!==null&&voiceSeatingRevision!==revision&&voice.stream){
            // The people and audio streams stay the same; only their seats move.
            const moved=seat=>Number(s.seating_map?.[seat]??seat);
            voice.peers=new Map([...voice.peers].map(([seat,peer])=>{peer.seat=moved(seat);return [peer.seat,peer]}));
            voice.meters=new Map([...voice.meters].map(([seat,meter])=>[moved(seat),meter]));
            voice.speaking=new Set([...voice.speaking].map(moved));
        }
        voiceSeatingRevision=revision;
        inlineControls.hidden=!voice.stream||s.status==='lobby';
        for(const [name,label,pressed] of [['mute',voice.muted?'Unmute microphone':'Mute microphone',voice.muted||voice.deafened],['deafen',voice.deafened?'Enable incoming audio':'Mute incoming audio',voice.deafened],['leave','Disconnect voice',false]]){
            const b=inlineControls.querySelector('#inline-voice-'+name);b.setAttribute('aria-label',label);b.title=label;b.classList.toggle('is-off',pressed);if(name!=='leave')b.setAttribute('aria-pressed',String(pressed));
        }
        effectControl.hidden=!voice.stream;
        $('#voice-join').hidden=Boolean(voice.stream);$('#voice-controls').hidden=!voice.stream;
        $('#voice-mute').textContent=voice.muted?'Unmute mic':'Mute mic';$('#voice-mute').setAttribute('aria-pressed',String(voice.muted||voice.deafened));
        $('#voice-deafen').textContent=voice.deafened?'Undeafen':'Deafen';$('#voice-deafen').setAttribute('aria-pressed',String(voice.deafened));
        const participants=s.players.map((p,seat)=>p?.voice?{p,seat}:null).filter(Boolean);
        morph($('#voice-roster'),participants.map(({p,seat})=>`<span data-voice-seat="${seat}" class="voice-person ${seat===s.seat||voice.peers.get(seat)?.pc.connectionState==='connected'?'connected':''}">${avatarIcons[p.avatar]||'🐾'} ${esc(p.name)}<small>${p.voice_muted?'🔇 muted':seat===s.seat?'you':voice.stream?(voice.peers.get(seat)?.pc.connectionState==='connected'?'connected':'connecting'):'in voice'}</small></span>`).join(''));
        markSpeaking();connectionStatus();
    }
    $('#voice-join').onclick=join;$('#voice-leave').onclick=()=>leave();
    $('#voice-mute').onclick=()=>{voice.muted=!voice.muted;applyMute()};
    $('#voice-deafen').onclick=()=>{voice.deafened=!voice.deafened;applyMute()};
    function resumeAudio(){
        if(!voice.stream)return;
        // Start all playback calls inside the gesture. An interrupted Safari
        // AudioContext may leave resume() pending; it must not block HTML audio.
        try{voice.audioContext?.resume().catch(()=>showResume(true))}catch{}
        const attempts=[...voice.peers.values()].filter(p=>p.audio).map(p=>p.audio.play());
        const epoch=voice.epoch;
        Promise.allSettled(attempts).then(results=>{
            if(!voice.stream||epoch!==voice.epoch)return;
            showResume(results.some(r=>r.status==='rejected')||voice.stream.getAudioTracks().some(t=>t.muted));connectionStatus();
        });
    }
    $('#voice-play').onclick=resumeAudio;recovery.onclick=resumeAudio;
    const repair=document.createElement('button');repair.id='voice-repair';repair.className='secondary';repair.textContent='Reconnect voice';$('#voice-controls').append(repair);
    async function reconnect(){
        if(voice.recovering||voice.joining)return;
        voice.recovering=true;repair.disabled=true;
        const muted=voice.muted,deafened=voice.deafened;
        leave();voice.muted=muted;voice.deafened=deafened;
        try{await join()}finally{voice.recovering=false;repair.disabled=false}
    }
    repair.onclick=reconnect;
    document.addEventListener('pointerup',()=>{if(!recovery.hidden||['suspended','interrupted'].includes(voice.audioContext?.state))resumeAudio()});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')resumeAudio()});
    window.addEventListener('pageshow',resumeAudio);
    window.addEventListener('pagehide',()=>leave(false));
    window.clubVoice={receive,update,leave,lost(){leave(false);status('Room connection lost. Rejoin voice after reconnecting.')},get active(){return Boolean(voice.stream)},get peers(){return voice.peers}};
})();
