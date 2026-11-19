let csrf='',offset=0,parent='',library='',total=0,chosen=null,trail=[],pairTimer=null,connected=false;
const $=id=>document.getElementById(id),status=text=>$('status').textContent=text;
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Vesper-CSRF':csrf},body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw Error(value.error||'Request failed');return value}
function safe(fn){return async e=>{try{await fn(e)}catch(err){status(err.message)}}}
async function libraries(){const data=await api('/api/libraries');$('libraries').replaceChildren();for(const item of [{id:'',name:'All titles'},...data.items]){const button=document.createElement('button');button.textContent=item.name;button.setAttribute('aria-current',item.id===library?'page':'false');button.onclick=safe(async()=>{library=item.id;parent='';trail=[];offset=0;$('query').value='';for(const sibling of $('libraries').children)sibling.setAttribute('aria-current',sibling===button?'page':'false');await load()});$('libraries').append(button)}}
async function load(){status('Loading your catalogue…');const q=new URLSearchParams({q:$('query').value,offset,parent,library});const data=await api('/api/catalog?'+q);total=data.total;$('grid').replaceChildren();for(const item of data.items){const b=document.createElement('button');b.className='card';b.dataset.kind=item.type;if(item.poster){const img=document.createElement('img');img.src='/api/poster/'+item.id;img.alt='';img.loading='lazy';b.append(img)}else{const p=document.createElement('div');p.className='placeholder';p.textContent=item.type==='Episode'?'Episode '+item.number:item.name;b.append(p)}const title=document.createElement('strong');title.textContent=item.name;const year=document.createElement('small');year.textContent=item.type==='Episode'?'Episode '+item.number:(item.year||item.type);b.append(title,year);b.onclick=safe(async()=>{if(item.type==='Series'||item.type==='Season'){trail.push({parent,name:item.name});parent=item.id;offset=0;$('query').value='';await load()}else{chosen=item;$('autoplay').disabled=item.type!=='Episode';$('autoplay').checked=item.type==='Episode';$('autoplay').parentElement.hidden=item.type!=='Episode';$('kind').textContent=item.type==='Episode'?'EPISODE '+item.number:'MOVIE';$('title').textContent=item.name;$('overview').textContent=item.overview||'No description available.';$('detail').showModal()}});$('grid').append(b)}$('count').textContent=total?`${offset+1}–${Math.min(offset+48,total)} of ${total}`:'No matching titles';$('previous').disabled=offset===0;$('next').disabled=offset+48>=total;$('trail').replaceChildren();if(trail.length){const back=document.createElement('button');back.className='secondary';back.textContent='← Back';back.onclick=safe(async()=>{parent=trail.pop().parent;offset=0;await load()});$('trail').append(back);const label=document.createElement('span');label.textContent=trail.map(x=>x.name).join(' / ');$('trail').append(label)}status(total?'Your library · choose a title to watch.':'No titles found. Try another search or category.')}
async function connectedView(){connected=true;$('pairWorld').hidden=false;$('stopPair').hidden=false;$('pair').hidden=true;$('connect').hidden=true;$('disconnect').hidden=false;await libraries();await load();await playback()}
async function checkPair(){const r=await api('/api/connect/status',{});if(!r.connected)return false;clearTimeout(pairTimer);await connectedView();return true}
async function pollPair(){try{if(!await checkPair())pairTimer=setTimeout(pollPair,5000)}catch(e){status(e.message);clearTimeout(pairTimer)}}
async function playback(){if(!connected)return;try{const s=await api('/room/theatre.json');$('cancelAuto').disabled=!s.autoplay;let text=s.state==='idle'?'No theatre selection yet.':s.state==='failed'?'Preparation failed. Choose the title again to retry.':s.ready?'Selected: '+s.title+' · Ready for the connected theatre.':'Preparing: '+s.title;if(s.autoplay)text+=s.nextReady?' Up next: '+s.nextTitle+'.':' Following episodes enabled.';$('theatreStatus').textContent=text}catch(e){$('theatreStatus').textContent='The theatre connection is unavailable.'}}
$('connect').onclick=safe(async()=>{clearTimeout(pairTimer);const r=await api('/api/connect',{server:$('serverAddress').value.trim()});$('approvalLink').href=r.approvalUrl;$('code').textContent=r.code;$('pair').hidden=false;status('Approve the code in Jellyfin. This page will connect automatically.');pairTimer=setTimeout(pollPair,5000)});
$('approved').onclick=safe(async()=>{if(!await checkPair())status('Not approved yet. Check Quick Connect in Jellyfin.')});
$('disconnect').onclick=safe(async()=>{await api('/api/disconnect',{});location.reload()});
$('search').onsubmit=safe(async e=>{e.preventDefault();offset=0;await load()});$('previous').onclick=safe(async()=>{offset=Math.max(0,offset-48);await load()});$('next').onclick=safe(async()=>{offset+=48;await load()});$('close').onclick=()=>$('detail').close();
$('prepare').onclick=safe(async()=>{if(!chosen)return;const r=await api('/api/prepare',{id:chosen.id,autoplay:$('autoplay').checked});$('detail').close();status(r.message);await playback()});
$('cancelAuto').onclick=safe(async()=>{const r=await api('/api/autoplay/cancel',{});status(r.message);await playback()});
safe(async()=>{const s=await api('/api/session');csrf=s.csrf;$('serverAddress').value=s.server||'';if(!s.connected)$('serverEntry').hidden=false;if(s.connected)await connectedView();else{try{if(!await checkPair())pairTimer=setTimeout(pollPair,5000)}catch(e){/* No pending connection. Use Connect Jellyfin. */}}})();setInterval(playback,5000);

async function worldStatus(){
 if(!connected)return;
 try{
  const state=await api('/api/world/status'),direct=state.direct||{},pair=state.pairing;
  $('directPanel').hidden=!direct.available;
  $('directStatus').textContent='Connected for this visit. Choose a title in VRChat to start watching.';
  $('worldPair').hidden=pair.state==='idle';$('worldLink').hidden=pair.state!=='ready';
  if(pair.state==='ready'){
   $('worldPairStatus').textContent='Your catalogue is ready to connect in the Keep.';
   $('pairUrl').value=pair.url;$('pairCode').value=pair.url.split('/').pop();
  }else{
   $('pairUrl').value='';$('pairCode').value='';
   $('worldPairStatus').textContent=pair.state==='preparing'?'Preparing your catalogue and posters. The service may need a moment to wake up.':pair.state==='left'?'You left the paired world. Create a fresh link when you return.':pair.state==='expired'?'Create a fresh link to connect again.':pair.message||'Pair the catalogue when you are ready.';
  }
 }catch(e){status(e.message)}
}
$('pairWorld').onclick=safe(async()=>{await api('/api/world/share',{});$('worldPair').hidden=false;await worldStatus()});
$('copyPair').onclick=safe(async()=>{try{await navigator.clipboard.writeText($('pairUrl').value);$('worldPairStatus').textContent='Link copied. Paste it into the catalogue input in your Keep.'}catch(e){$('pairUrl').select();$('worldPairStatus').textContent='Select and copy the link, then paste it into your Keep.'}});
setInterval(worldStatus,5000);



$('stopPair').onclick=safe(async()=>{await api('/api/world/stop',{});$('pairUrl').value='';$('pairCode').value='';await worldStatus();await playback();status('Pairing stopped. You are still signed into Jellyfin. Create a new pairing link when ready to connect elsewhere.');});
$('directAutoplay').onchange=safe(async()=>{await api('/api/world/direct',{enabled:true,autoplay:$('directAutoplay').checked});await worldStatus()});

$('copyCode').onclick=safe(async()=>{try{await navigator.clipboard.writeText($('pairCode').value);$('worldPairStatus').textContent='Code copied. In VRChat, paste it after the matching prefilled /shared/ address.'}catch(e){$('pairCode').select();$('worldPairStatus').textContent='Select and copy the code, then paste it after the address in VRChat.'}});
