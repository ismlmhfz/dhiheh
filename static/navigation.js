(()=>{
const menu=document.querySelector('#mobile-menu'),header=document.querySelector('#site-header'),nav=document.querySelector('#site-nav'),mobile=matchMedia('(max-width:720px)');
let restingHeight=innerHeight,lastWidth=innerWidth;
function fit(){
    const viewport=window.visualViewport,unzoomed=!viewport||Math.abs(viewport.scale-1)<.01;
    if(!unzoomed)return;
    const height=viewport?Math.min(innerHeight,viewport.height):innerHeight;
    const editing=document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]),textarea,[contenteditable=true]');
    const wasKeyboard=document.body.classList.contains('keyboard-open');
    if(Math.abs(innerWidth-lastWidth)>40){restingHeight=innerHeight;lastWidth=innerWidth}
    if(!editing&&!wasKeyboard)restingHeight=Math.max(height,innerHeight);
    const keyboard=mobile.matches&&document.body.classList.contains('in-room')&&(editing||wasKeyboard)&&restingHeight-height>100;
    document.body.classList.toggle('keyboard-open',Boolean(keyboard));
    document.documentElement.style.setProperty('--game-height',height+'px');
    document.documentElement.style.setProperty('--game-top',Math.max(0,viewport?.offsetTop||0)+'px');
}
function scheduleFit(){fit();requestAnimationFrame(fit);setTimeout(fit,150)}
window.visualViewport?.addEventListener('resize',scheduleFit);window.visualViewport?.addEventListener('scroll',fit);
window.addEventListener('resize',scheduleFit);document.addEventListener('focusin',scheduleFit);document.addEventListener('focusout',scheduleFit);fit();
const original=[...nav.children].filter(n=>n.matches('.account-link,.logout-form,#rules-button,#sound,#fullscreen')).map(node=>{const anchor=document.createComment('Header control');node.before(anchor);return {node,anchor}});
const heading=document.createElement('div');heading.className='menu-heading';heading.innerHTML='<div><span>YOUR TABLE</span><strong id="menu-room-code">Table menu</strong></div><button type="button" class="menu-close" aria-label="Close menu">×</button>';
const groups={};
for(const [key,title] of [['table','At the table'],['controls','Voice & display'],['account','Your account'],['exit','Leave or close']]){
    const group=document.createElement('section');group.className='menu-section menu-'+key;group.innerHTML='<h3>'+title+'</h3><div class="menu-items"></div>';groups[key]=group;
}
function move(selector,key,icon){const node=document.querySelector(selector);if(!node)return;if(icon)node.dataset.menuIcon=icon;groups[key].querySelector('.menu-items').append(node)}
function arrange(){
    if(!mobile.matches){
        for(const {node,anchor} of original)anchor.after(node);
        heading.remove();Object.values(groups).forEach(g=>g.remove());close();return;
    }
    nav.prepend(heading);Object.values(groups).forEach(g=>nav.append(g));
    move('#open-chat','table','▤');move('#invite','table','↗');move('#rename-team','table','✎');move('.group-back','table','♧');
    move('.phone-tools','controls');move('#sound','controls','♫');move('#fullscreen','controls','⛶');move('#rules-button','controls','?');
    move('.friends-link','account','♧');
    for(const {node} of original)if(node.matches('.account-link:not(.friends-link),.logout-form')){node.dataset.menuIcon=node.matches('.logout-form')?'↪':node.getAttribute('href')==='/admin/'?'⚙':'♙';groups.account.querySelector('.menu-items').append(node)}
    move('#leave','exit','↩');move('#delete-table','exit','×');
    const sound=document.querySelector('#sound'),full=document.querySelector('#fullscreen');sound.setAttribute('aria-label','Toggle game sounds');sound.title='Toggle game sounds';full.title='Fullscreen';
}
function close(){header.classList.remove('menu-open');menu.setAttribute('aria-expanded','false')}
function open(){arrange();document.querySelector('#menu-room-code').textContent=roomCode?'Table '+roomCode:'Table menu';header.classList.add('menu-open');menu.setAttribute('aria-expanded','true')}
menu.onclick=()=>header.classList.contains('menu-open')?close():open();heading.querySelector('button').onclick=()=>{close();menu.focus()};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&header.classList.contains('menu-open')){close();menu.focus()}});
nav.addEventListener('click',e=>{if(e.target.closest('a,button'))close()});
document.addEventListener('pointerdown',e=>{if(!header.contains(e.target))close()});
mobile.addEventListener('change',arrange);window.clubMenu={arrange};arrange();
})();
