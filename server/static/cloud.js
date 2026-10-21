(function(){
 'use strict';
 let csrf='',user=null,client=null,store=null,hooks=null,ready=false,onlineOnly=false,resources='preparing';
 let latestState={mode:'pending',pending:0},resourceReason='';
 const viewKey=()=> 'ngsl-nawl-online-view:'+user.id;
 function message(text,error=false){
  const element=document.getElementById('save-status');
  if(element){element.textContent=text;element.classList.toggle('storage-warning',error);}
 }
 function invalidate(error){
  if(error.code==='ACCOUNT_CHANGED'||error.status===403){ready=false;location.reload();return;}
  if(error.status===401){ready=false;location.replace('/login');}
 }
 async function request(path,{method='GET',body,skipCsrf=false}={}){
  let response;const controller=typeof AbortController!=='undefined'?new AbortController():null;
  const timer=controller?setTimeout(()=>controller.abort(),10000):null;
  try{response=await fetch(path,{method,credentials:'same-origin',cache:'no-store',...(controller?{signal:controller.signal}:{}),headers:{'Content-Type':'application/json',...(!skipCsrf&&csrf?{'X-CSRF-Token':csrf}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{})});}
  catch(cause){const error=new Error('网络连接暂不可用，已保存的本机操作会在联网后同步');error.code='NETWORK';throw error;}
  finally{if(timer)clearTimeout(timer);}
  const data=await response.json().catch(()=>({detail:'服务器返回异常，请重试'}));
  if(!response.ok){const error=new Error(data.detail||'请求失败');error.status=response.status;throw error;}
  return data;
 }
 async function boundRequest(path,options){
  const me=await request('/api/me',{skipCsrf:true});
  if(me.user.id!==user.id){const error=new Error('登录账号已变化，请刷新页面');error.code='ACCOUNT_CHANGED';throw error;}
  csrf=me.csrf;return request(path,options);
 }
 function report({mode,pending=0,error}={}){
  latestState={mode,pending,error};
  const resourceText=resources==='ready'?'离线资源已就绪':resources==='preparing'?'离线资源准备中':resourceReason||'离线资源未就绪，请联网刷新重试';
  if(onlineOnly){message(mode==='synced'?'进度已同步 · 此浏览器无法离线保存':'暂时无法同步；此浏览器无法离线保存',mode!=='synced');return;}
  if(mode==='syncing'){message('正在同步 · '+pending+' 项待同步');return;}
  if(pending){message((mode==='offline'?'离线学习 · ':'')+'已保存到本机 · '+pending+' 项待同步 · '+resourceText,mode==='failed'||mode==='blocked');return;}
  if(mode==='offline'){message('离线学习 · 进度已保存到本机 · '+resourceText);return;}
  if(mode==='failed'||mode==='blocked'){message('进度保存在本机 · 同步暂未完成',true);return;}
  message('进度已同步 · '+user.username+' · '+resourceText);
 }
 function saveView(){
  if(!ready)return;
  try{localStorage.setItem(viewKey(),JSON.stringify(hooks.readView()));}catch(error){}
 }
 async function refresh(){
  if(!ready)return;
  try{await (onlineOnly?client.refresh():client.flush());if(onlineOnly)report({mode:'synced'});}
  catch(error){invalidate(error);report({mode:'blocked',pending:client.pendingCount||0,error});}
 }
 async function mutation(action){
  if(!ready)throw new Error('正在读取账号进度，请稍候');
  try{const result=await action();if(onlineOnly)report({mode:'synced'});return result;}
  catch(error){invalidate(error);message(error.name==='QuotaExceededError'?'本机空间不足，本次操作未保存，请释放空间后重试':error.message,true);throw error;}
 }
 window.cloud={
  request,
  get ready(){return ready;},get revision(){return client?client.revision:-1;},
  saveView,
  async setWord(id,status){const result=await mutation(()=>client.setWord(id,status));if(!onlineOnly)refresh();return result;},
  importWords:words=>mutation(()=>client.importWords(words)),
  refresh,
  async boot(callbacks){
   hooks=callbacks;message('正在读取账号进度…');
   try{store=await openOfflineStore();}catch(error){onlineOnly=true;}
   const previousActive=store?await store.active():null;
   let me,networkError;
   try{me=await request('/api/me',{skipCsrf:true});user=me.user;csrf=me.csrf;}
   catch(error){if(error.code!=='NETWORK'){invalidate(error);throw error;}networkError=error;}
   if(me){if(store){try{await store.activate(user,{expectedActiveId:previousActive?.id||null});}catch(error){invalidate(error);throw error;}}}
   else{
    if(!store)throw networkError;
    user=await store.active();const cached=user&&await store.read(user.id);
    if(!cached||cached.snapshot.revision<0)throw new Error('此设备尚未缓存学习进度，请先联网登录');
   }
   try{const view=JSON.parse(localStorage.getItem(viewKey()));if(view)hooks.applyView(view);}catch(error){}
   if(onlineOnly){client=createSyncClient({request:boundRequest,onSnapshot:hooks.applySnapshot});await client.refresh();}
   else{
    client=createOfflineClient({store,user,request:boundRequest,onSnapshot:hooks.applySnapshot,onState:report});
    await client.load();
    if(me)await client.flush();
    if(client.revision<0)throw new Error('学习进度尚未缓存，请联网刷新重试');
   }
   ready=true;report({mode:networkError?'offline':onlineOnly?'synced':client.mode,pending:client.pendingCount});
   const account=document.getElementById('account-link');if(account)account.textContent=user.username+' · 我的账号';
   document.getElementById('logout-btn').addEventListener('click',async()=>{
    try{
     if(!onlineOnly){await client.flush();if(client.pendingCount)throw new Error('请联网完成待同步操作后再退出，当前进度已保存在本机');}
     await request('/api/auth/logout',{method:'POST',body:{}});
     const cleanup=store?await store.clearUser(user.id):null;ready=false;location.replace('/login'+(cleanup?.pending?'?pending=1':''));
    }catch(error){invalidate(error);hooks.toast(error.code==='NETWORK'?'退出登录需要联网，当前进度保留在本机':error.message);}
   });
   document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refresh();});
   if(window.addEventListener)window.addEventListener('online',refresh);
   setInterval(()=>{if(document.visibilityState==='visible')refresh();},15000);
   if(typeof prepareOfflineResources==='function'&&!onlineOnly){
    prepareOfflineResources().then(result=>{resources=result.ready?'ready':'unavailable';resourceReason=result.reason||'';report(latestState);})
     .catch(error=>{resources='unavailable';console.warn('Offline cache setup failed:',error.name,error.message);report(latestState);});
   }else{resources='unavailable';report(latestState);}
  }
 };
})();
