let csrf='',timer=null,approvalUrl='',approvalCode='';
const jellyfinSignIn=document.getElementById('jellyfinSignIn');
async function copyApprovalCode(){
 try{await navigator.clipboard.writeText(approvalCode);return true;}catch{return false;}
}
jellyfinSignIn.onclick=()=>{
 if(!approvalUrl)return;
 window.open(approvalUrl,'_blank','noopener,noreferrer');
};
const button=document.getElementById('signIn'),message=document.getElementById('loginStatus'),serverInput=document.getElementById('serverAddress');
async function api(path,body){
 const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Vesper-CSRF':csrf},body:JSON.stringify(body)});
 const data=await r.json();if(!r.ok)throw Error(data.error||'Connection failed');return data;
}
async function poll(){
 try{const s=await api('/api/connect/status',{});if(s.connected){location.reload();return;}timer=setTimeout(poll,5000);}
 catch(e){message.textContent=e.message;button.disabled=false;serverInput.disabled=false;}
}
document.getElementById('useLocal').onclick=()=>{serverInput.value='http://127.0.0.1:8096';document.getElementById('serverOptions').open=false;};
button.onclick=async()=>{
 try{
  clearTimeout(timer);document.getElementById('codeCopyStatus').textContent='';approvalUrl='';approvalCode='';jellyfinSignIn.disabled=true;button.disabled=true;document.getElementById('loginCode').hidden=true;message.textContent='Connecting to Jellyfin…';
  const result=await api('/api/connect',{server:serverInput.value.trim()});
  serverInput.disabled=true;document.getElementById('code').textContent=result.code;
  approvalUrl=result.approvalUrl;approvalCode=String(result.code);jellyfinSignIn.disabled=false;
  document.getElementById('loginCode').hidden=false;button.disabled=false;
  const copied=await copyApprovalCode();
  document.getElementById('codeCopyStatus').textContent=copied?'Code copied! Paste it into Jellyfin’s Quick Connect.':'Automatic copying was blocked. Select and copy the code above, or type it into Jellyfin.';
  message.textContent=copied?'Code copied! Choose Open Jellyfin, then paste the code into Quick Connect.':'Choose Open Jellyfin. Automatic copying was blocked; select and copy the code above, or type it into Quick Connect.';
  timer=setTimeout(poll,5000);
 }catch(e){button.disabled=false;serverInput.disabled=false;message.textContent=e.message;}
};
(async()=>{
 try{
  const s=await api('/api/session');csrf=s.csrf;serverInput.value=s.server||'http://127.0.0.1:8096';
  document.getElementById('serverOptions').open=!!s.server&&!/^http:\/\/(127\.0\.0\.1|localhost):8096\/?$/.test(s.server);
  button.disabled=false;
  if(s.connected){location.reload();return;}
  // Do not resume an invisible pending approval: request a fresh visible code instead.
 }catch(e){message.textContent=e.message;}
})();
