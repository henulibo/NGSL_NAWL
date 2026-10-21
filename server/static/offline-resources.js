(function(root){
 'use strict';
 function inspectWorker(worker,version){
  return new Promise((resolve,reject)=>{
   const channel=new MessageChannel();const timer=setTimeout(()=>{channel.port1.close();reject(new Error('离线资源检查超时'));},10000);
   channel.port1.onmessage=event=>{clearTimeout(timer);channel.port1.close();const ready=event.data?.ready===true&&event.data.version===version;resolve({ready,reason:ready?'':event.data?.version!==version?'离线资源正在更新，请联网刷新重试':'离线资源缓存不完整，请联网刷新重试'});};
   worker.postMessage({type:'CHECK_READY'},[channel.port2]);
  });
 }
 function activated(worker){
  return new Promise((resolve,reject)=>{
   if(worker.state==='activated'){resolve();return;}
   const timer=setTimeout(()=>reject(new Error('离线资源仍在准备中')),45000);
   function changed(){
    if(worker.state==='activated'){clearTimeout(timer);worker.removeEventListener('statechange',changed);resolve();}
    if(worker.state==='redundant'){clearTimeout(timer);worker.removeEventListener('statechange',changed);reject(new Error('离线资源安装未完成'));}
   }
   worker.addEventListener('statechange',changed);changed();
  });
 }
 async function prepareOfflineResources(){
  if(!root.navigator?.serviceWorker)return {ready:false,reason:'此浏览器不支持离线页面，请换用支持离线缓存的浏览器'};
  const version=document.querySelector('meta[name="workbook-version"]')?.content;
  const existing=await navigator.serviceWorker.getRegistration('/');
  if(existing?.active){
   try{const cached=await inspectWorker(existing.active,version);if(cached.ready){existing.update().catch(()=>{});return cached;}}catch(error){}
  }
  const registration=await navigator.serviceWorker.register('/service-worker.js',{scope:'/',updateViaCache:'none'});
  // Registration may return the previous active worker before its update starts.
  if(!registration.installing&&!registration.waiting&&registration.active)await registration.update();
  const worker=registration.installing||registration.waiting||registration.active;
  if(!worker)throw new Error('离线资源尚未开始安装');
  await activated(worker);return inspectWorker(worker,version);
 }
 root.prepareOfflineResources=prepareOfflineResources;
})(typeof globalThis!=='undefined'?globalThis:this);
