(()=>{
 const $=s=>document.querySelector(s),code=$('#spectator').dataset.code;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const suits={S:'♠',H:'♥',D:'♦',C:'♣'},suitNames={S:'Spades',H:'Hearts',D:'Diamonds',C:'Clubs'},avatars={fox:'🦊',panda:'🐼',frog:'🐸',cat:'🐱',lion:'🦁',owl:'🦉',koala:'🐨',dragon:'🐲'};
 const positions=['bottom','left','top','right'];let busy=false;
 function card(c){const suit=c.slice(-1);return `<span class="watch-card ${['H','D'].includes(suit)?'red':''}"><b>${esc(c.slice(0,-1))}</b><i>${suits[suit]||''}</i></span>`}
 function draw(data){
  const s=data.state,teams=s.team_names||['Fern','Amber'];
  $('#watch-status').textContent=s.paused?'Match paused · waiting for a player to reconnect':'Live · spectator mode';
  $('#watch-scores').innerHTML=teams.map((name,i)=>`<div><span>${esc(name)}</span><strong>${s.scores?.[i]||0}</strong><small>${s.stacks?.[i]||0} stacks · ${s.tens?.[i]?.length||0} tens</small></div>`).join('');
  $('#watch-trump').textContent=`Deal ${s.deal||'—'} · ${s.trump?`${suits[s.trump]} ${suitNames[s.trump]} is trump`:'Trump not set'}`;
  $('#watch-players').innerHTML=s.players.map((p,i)=>`<div class="watch-player ${positions[i]} ${s.status==='playing'&&s.turn===i?'active':''}"><span class="watch-avatar">${p?(avatars[p.avatar]||'🦊'):'＋'}</span><strong>${esc(p?.name||'Open seat')}</strong><small>${p?`${esc(teams[p.team??i%2])} · ${s.status==='lobby'?(p.ready?'Ready':'Not ready'):`${s.counts[i]} cards`}`:'Waiting for a player'}</small></div>`).join('');
  const cards=s.trick?.length?s.trick:s.last?.cards||[];
  $('#watch-cards').innerHTML=cards.map(c=>`<div class="watch-play ${positions[c.seat]}">${card(c.card)}<small>${esc(s.players[c.seat]?.name||'Player')}</small></div>`).join('');
  $('#watch-table-message').textContent=s.status==='lobby'?'Waiting for four players':s.status==='abandoned'?'Match ended':s.status==='match_results'?(s.winner===null?'Match tied':`${teams[s.winner]} wins the match!`):s.status==='deal_results'?`${teams[s.result.team]} takes the deal` : '';
  if(s.status==='lobby'||s.status==='abandoned')$('#watch-cards').replaceChildren();
  $('#watch-turn').textContent=s.paused?'Play will resume when everyone reconnects.':s.status==='playing'?`${s.players[s.turn]?.name||'A player'} is playing${!s.trick?.length&&s.last?' · Previous stack shown':''}`:s.status==='chase_decision'?`${s.players[s.decision.seat]?.name} is deciding whether to bank or chase four 10s.`:s.status==='lobby'?`${s.players.filter(Boolean).length}/4 seats filled · The host starts when all four players are ready.`:'Waiting for the next deal or match.';
  $('#watch-history').innerHTML=s.history?.length?s.history.slice().reverse().map(t=>`<div><strong>Stack ${t.number} · ${esc(s.players[t.winner]?.name)} won</strong><span>${t.cards.map(c=>`${esc(c.card.slice(0,-1))}${suits[c.card.slice(-1)]}`).join(' · ')}</span></div>`).join(''):'<p class="muted">Completed stacks will appear here.</p>';
  $('#watch-join').hidden=!(data.can_join&&s.status==='lobby'&&s.players.some(p=>!p));
  $('#watch-group').hidden=!data.group_id;if(data.group_id)$('#watch-group').href='/friends/?chat='+data.group_id;
 }
 async function update(){if(busy||document.visibilityState!=='visible')return;busy=true;try{const response=await fetch(`/spectate/api/${code}/`,{cache:'no-store'});if(!response.ok)throw Error(response.status===404?'This table is no longer available.':'Connection interrupted. Retrying…');draw(await response.json())}catch(error){$('#watch-status').textContent=error.message}finally{busy=false}}
 $('#copy-watch-link').onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/watch/'+code+'/');$('#watch-status').textContent='Spectator link copied.'}catch{$('#watch-status').textContent=location.origin+'/watch/'+code+'/'}};
 setInterval(update,1500);document.addEventListener('visibilitychange',update);update();
})();
