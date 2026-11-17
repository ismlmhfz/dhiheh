(()=>{
 const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const icons={fox:'🦊',panda:'🐼',frog:'🐸',cat:'🐱',lion:'🦁',owl:'🦉',koala:'🐨',dragon:'🐲'};
 let overview=null,active=Number(new URLSearchParams(location.search).get('chat'))||null,current=null,busy=false,messageSignature='',lastRead=0,requestId=0;
 let sending=false;
 function fitKeyboard(){if(window.visualViewport&&visualViewport.scale===1)document.documentElement.style.setProperty('--messenger-height',visualViewport.height+'px')}
 window.visualViewport?.addEventListener('resize',fitKeyboard);window.addEventListener('resize',fitKeyboard);fitKeyboard();
 const drafts=new Map();let inboxFilter='all';
 $('#open-friends').onclick=()=>$('#friends-dialog').showModal();
 $('#back-to-inbox').onclick=()=>{if(active)drafts.set(active,$('#message-text').value);active=null;current=null;requestId++;lastRead=0;messageSignature='';$('#active-conversation').hidden=true;$('#conversation-empty').hidden=false;document.body.classList.remove('conversation-open');history.replaceState({},'','/friends/');drawOverview()};
 $('#chat-search').oninput=()=>drawOverview();
 document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{inboxFilter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(t=>t.setAttribute('aria-pressed',String(t===b)));drawOverview()});
 const csrf=()=>document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.split('=')[1];
 async function request(path,data){
  const res=await fetch('/social/api/'+path,{headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},...(data?{method:'POST',body:JSON.stringify(data)}:{})});
  if(res.redirected){location.href='/login/?next='+encodeURIComponent(location.pathname+location.search);throw Error('Please log in again.')}
  let result;try{result=await res.json()}catch{throw Error(res.status===404?'This conversation is no longer available.':'Unable to load. Please try again.')}
  if(!res.ok)throw Error(result.error||'Unable to complete that request.');return result;
 }
 const action=(name,data={})=>request('action/'+name+'/',data);
 let statusTimer;const status=text=>{$('#social-status').textContent=text;clearTimeout(statusTimer);statusTimer=setTimeout(()=>{$('#social-status').textContent=''},6500)};
 const person=p=>`<span class="person-avatar">${icons[p.avatar]||'🦊'}</span><span><strong>${esc(p.name)}</strong><small>@${esc(p.username)}</small></span>`;
 function drawOverview(){
  $('#request-count').textContent=overview.incoming.length||'';
  $('#my-username').textContent=`Your username: @${overview.me.username}`;
  $('#friend-list').innerHTML=overview.friends.length?overview.friends.map(f=>`<div class="person-row">${person(f.person)}<button data-dm="${f.person.id}" aria-label="Chat with ${esc(f.person.name)}">Chat</button><button class="quiet" data-remove="${f.id}" aria-label="Remove ${esc(f.person.name)} as a friend">×</button></div>`).join(''):'<p class="muted">Your accepted friends will appear here.</p>';
  $('#friend-requests').innerHTML=(overview.incoming.length?'<h3>Friend requests</h3>':'')+overview.incoming.map(f=>`<div class="request-row">${person(f.person)}<div><button data-accept="${f.id}">Accept</button><button data-decline="${f.id}" class="quiet">Decline</button></div></div>`).join('')+overview.outgoing.map(f=>`<div class="pending-row">Request sent to @${esc(f.person.username)}<button data-decline="${f.id}" class="quiet">Cancel</button></div>`).join('');
  $('#conversation-list').innerHTML=overview.conversations.filter(c=>(inboxFilter==='all'||c.kind===inboxFilter)&&c.title.toLowerCase().includes($('#chat-search').value.toLowerCase())).map(c=>`<button class="conversation-link ${c.id===active?'selected':''}" data-chat="${c.id}" aria-pressed="${c.id===active}"><span>${c.kind==='group'?'👥':'💬'} <strong>${esc(c.title)}</strong>${c.unread?`<b class="unread">${c.unread}</b>`:''}</span><small>${esc(c.preview)}</small></button>`).join('')||'<p class="muted">No conversations yet.</p>';
 }
 async function loadConversation(){
  if(!active)return;
  const id=active,serial=++requestId;
  const result=await request(`conversation/${id}/`);
  if(active!==id||serial!==requestId)return;
  current=result.conversation;
  if(new URLSearchParams(location.search).has('chat'))document.body.classList.add('conversation-open');
  $('#conversation-empty').hidden=true;$('#active-conversation').hidden=false;
  $('#conversation-title').textContent=current.title;
  $('#conversation-kind').textContent=current.kind==='group'?'GROUP CHAT':'PRIVATE CHAT';
  $('#conversation-members').textContent=current.kind==='group'?`${current.members.length} members · ${current.members.map(p=>p.name).join(', ')}`:'Only you and your friend can read this conversation.';
  $('#group-settings').hidden=current.kind!=='group';$('#start-group-match').hidden=current.kind!=='group';
  $('#message-text').disabled=!current.can_send;$('#send-message button').disabled=sending||!current.can_send;
  $('#conversation-status').textContent=current.can_send?'':'Add this player as a friend again to send messages.';
  const signature=JSON.stringify(result.messages);
  if(signature!==messageSignature){
   const list=$('#conversation-messages'),bottom=list.scrollHeight-list.scrollTop-list.clientHeight<80;
   const oldScroll=list.scrollTop;
   list.innerHTML=result.messages.map(m=>`<article class="message ${m.sender.id===overview.me.id?'mine':''}"><div class="message-meta"><strong>${esc(m.sender.name)}</strong><time datetime="${esc(m.time)}">${esc(new Date(m.time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))}</time></div><p>${esc(m.text)}</p>${m.match?`<div class="match-card"><span class="eyebrow">MATCH INVITATION</span><h3>Table ${esc(m.match.code)}</h3><p>${m.match.players}/4 seats · ${esc(m.match.status.replaceAll('_',' '))}</p><div class="match-links">${m.match.seated||m.match.invitation?.open?`<a class="primary" href="${esc(m.match.join_url)}" target="_blank" rel="noopener">${m.match.seated?'Open table':'Join match'} ↗</a>`:`<span class="muted">${esc(m.match.invitation?.reason||'Invitation closed')}</span>`}<a href="${esc(m.match.watch_url)}" target="_blank" rel="noopener">Watch live ↗</a></div><button class="copy-watch quiet" data-watch="${esc(m.match.watch_url)}">Copy spectator link</button><small>${m.match.invitation?.open?'Join before '+esc(new Date(m.match.invitation.expires_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))+'. ':''}Anyone with the spectator link can watch.</small></div>`:''}</article>`).join('')||'<p class="empty-messages">Your conversation starts here.</p>';
   if(bottom||!messageSignature)list.scrollTop=list.scrollHeight;else list.scrollTop=oldScroll;
   messageSignature=signature;
  }
  const newest=result.messages.at(-1)?.id||0;
  if(newest>lastRead&&document.visibilityState==='visible'){
   await action('read',{conversation_id:id,message_id:newest});if(active===id)lastRead=newest;
  }
 }
 async function refresh(){
  if(busy)return;busy=true;
  try{overview=await request('overview/');drawOverview();if(active)await loadConversation()}
  catch(error){status(error.message)}finally{busy=false}
 }
 async function choose(id){
  if(active)drafts.set(active,$('#message-text').value);
  $('#friends-dialog').close();document.body.classList.add('conversation-open');
  active=id;current=null;lastRead=0;messageSignature='';requestId++;
  $('#message-text').value=drafts.get(id)||'';
  $('#conversation-messages').replaceChildren();
  history.replaceState({},'',`/friends/?chat=${id}`);drawOverview();
  try{await loadConversation();$('#conversation-messages').scrollTop=$('#conversation-messages').scrollHeight}catch(error){status(error.message)}
 }
 document.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b)return;
  try{
   if(b.dataset.chat){await choose(Number(b.dataset.chat));return}
   if(b.dataset.dm){const result=await action('direct',{user_id:Number(b.dataset.dm)});await refresh();await choose(result.id);return}
   for(const [key,name] of [['accept','friend_accept'],['decline','friend_decline'],['remove','friend_remove']])if(b.dataset[key]){
    if(key==='remove'&&!confirm('Remove this friend? Existing messages remain, but private messaging stops until you are friends again.'))return;
    b.disabled=true;await action(name,{id:Number(b.dataset[key])});await refresh();return;
   }
   if(b.dataset.watch){await navigator.clipboard.writeText(location.origin+b.dataset.watch);status('Spectator link copied.');return}
   if(b.hasAttribute('data-close'))b.closest('dialog').close();
  }catch(error){status(error.message);b.disabled=false}
 });
 $('#add-friend').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{await action('friend_request',{username:$('#friend-username').value});$('#friend-username').value='';status('Friend request sent. They can accept it from Friends & chats.');await refresh()}catch(error){status(error.message)}finally{b.disabled=false}};
 $('#new-group').onclick=()=>{
  if(!overview)return;
  $('#group-friends').innerHTML=overview.friends.map(f=>`<label class="friend-choice"><input type="checkbox" value="${f.person.id}">${person(f.person)}</label>`).join('')||'<p>Add and accept a friend before creating a group.</p>';
  $('#group-dialog .dialog-status').textContent='';$('#group-dialog').showModal();
 };
 $('#create-group').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('[type=submit]');b.disabled=true;try{const result=await action('group_create',{title:$('#group-title').value,user_ids:[...$('#group-friends').querySelectorAll(':checked')].map(x=>Number(x.value))});$('#group-dialog').close();$('#group-title').value='';await refresh();await choose(result.id)}catch(error){$('#group-dialog .dialog-status').textContent=error.message}finally{b.disabled=false}};
 $('#send-message').onsubmit=async e=>{
  e.preventDefault();if(sending||!active||!current?.can_send)return; sending=true;
  const text=$('#message-text').value,id=active,b=e.target.querySelector('button');b.disabled=true;
  try{await action('send',{conversation_id:id,text,command:crypto.randomUUID()});if(active===id&&$('#message-text').value===text)$('#message-text').value='';drafts.delete(id);messageSignature='';await loadConversation()}
  catch(error){$('#conversation-status').textContent=error.message}finally{sending=false;b.disabled=!current?.can_send}
 };
 $('#message-text').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#send-message').requestSubmit()}};
 function showMembers(){
  $('#members-list').innerHTML=current.members.map(p=>`<div class="person-row">${person(p)}${p.id===current.owner?'<small>Owner</small>':''}</div>`).join('');
  const owner=current.owner===overview.me.id;
  $('#add-member').hidden=!owner;$('#rename-group').hidden=!owner;
  $('#member-select').innerHTML=overview.friends.filter(f=>!current.members.some(m=>m.id===f.person.id)).map(f=>`<option value="${f.person.id}">${esc(f.person.name)} (@${esc(f.person.username)})</option>`).join('');
  $('#add-member button').disabled=!$('#member-select').options.length;
  $('#rename-title').value=current.title;$('#members-dialog .dialog-status').textContent='';
 }
 $('#group-settings').onclick=()=>{showMembers();$('#members-dialog').showModal()};
 for(const [form,name,payload] of [['#add-member','group_add',()=>({user_id:Number($('#member-select').value)})],['#rename-group','group_rename',()=>({title:$('#rename-title').value})]]){
  $(form).onsubmit=async e=>{e.preventDefault();try{await action(name,{conversation_id:active,...payload()});await refresh();showMembers()}catch(error){$('#members-dialog .dialog-status').textContent=error.message}};
 }
 $('#leave-group').onclick=async()=>{if(!confirm('Leave this group? You will lose access to its messages.'))return;try{await action('group_leave',{conversation_id:active});$('#members-dialog').close();active=null;current=null;document.body.classList.remove('conversation-open');$('#active-conversation').hidden=true;$('#conversation-empty').hidden=false;history.replaceState({},'','/friends/');await refresh()}catch(error){$('#members-dialog .dialog-status').textContent=error.message}};
 let matchCommand=null;
 $('#start-group-match').onclick=()=>{matchCommand=crypto.randomUUID();$('#match-dialog .dialog-status').textContent='';$('#match-dialog').showModal()};
 $('#create-match').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('[type=submit]');b.disabled=true;try{await action('match_create',{conversation_id:active,mode:$('#match-mode').value,command:matchCommand});$('#match-dialog').close();messageSignature='';await refresh();status('Match invitation posted. Open the table to play.')}catch(error){$('#match-dialog .dialog-status').textContent=error.message}finally{b.disabled=false}};
 setInterval(()=>{if(document.visibilityState==='visible')refresh()},2500);
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refresh()});
 refresh();
})();
