(function(root){
 'use strict';
 function accountChanged(){const error=new Error('登录账号已变化，请刷新页面');error.code='ACCOUNT_CHANGED';return error;}
 function createOfflineClient({store,user,request,onSnapshot=()=>{},onState=()=>{},lock}){
  let record=null,view={},flushing=null,mode='pending',rendered=false;
  const owner=root.crypto.randomUUID(),lockName='ielts-sync-user-'+user.id;
  const count=()=>record?Object.keys(record.pending).length:0;
  function state(next,error){mode=next;onState({mode,pending:count(),error});}
  async function load(){
   const active=await store.active();if(!active||active.id!==user.id)throw accountChanged();
   record=await store.read(user.id);if(!record)throw accountChanged();
   const next={...record.snapshot.words};
   for(const operation of Object.values(record.pending)){
    if(operation.status==='new')delete next[operation.word_id];else next[operation.word_id]=operation.status;
   }
   const changed=!rendered||Object.keys(next).length!==Object.keys(view).length||Object.entries(next).some(([key,value])=>view[key]!==value);
   view=next;
   if(changed){rendered=true;onSnapshot({revision:record.snapshot.revision,words:{...view},pending:count()});}
   return record;
  }
  async function exclusive(action){
   if(lock)return lock(action);
   if(root.navigator&&root.navigator.locks)return root.navigator.locks.request(lockName,{ifAvailable:true},held=>held?action():undefined);
   if(!await store.lease(lockName,owner,Date.now()+30000))return;
   const renewal=setInterval(()=>{store.lease(lockName,owner,Date.now()+30000).catch(()=>{});},10000);
   if(renewal&&renewal.unref)renewal.unref();
   try{return await action();}finally{clearInterval(renewal);await store.release(lockName,owner);}
  }
  function validateAcknowledgement(response,operations){
   if(!Array.isArray(response.acknowledged))throw new Error('同步确认缺失，操作仍保存在本机');
   const expected=new Set(operations.map(operation=>operation.id));
   if(response.acknowledged.length!==expected.size||response.acknowledged.some(id=>!expected.delete(id))||expected.size)throw new Error('同步确认不完整，操作仍保存在本机');
  }
  async function synchronize(){
   await load();state('syncing');
   const latest=await request('/api/progress');await store.accept(user.id,latest,[]);await load();
   while(count()){
    const operations=Object.values(record.pending).sort((a,b)=>a.sequence-b.sequence).slice(0,200);
    const response=await request('/api/progress/sync',{method:'POST',body:{operations}});
    validateAcknowledgement(response,operations);
    await store.accept(user.id,response,response.acknowledged);await load();state('syncing');
   }
   state('synced');
  }
  return {
   load,
   get words(){return {...view};},get revision(){return record?record.snapshot.revision:-1;},
   get pendingCount(){return count();},get mode(){return mode;},
   async setWord(word_id,status){
    await store.enqueue(user.id,{word_id,status});await load();state('pending');
   },
   flush(){
    if(flushing)return flushing;
    flushing=(async()=>{
     try{await load();await exclusive(synchronize);}
     catch(error){
      if(error.code==='ACCOUNT_CHANGED'||[401,403].includes(error.status)){state('blocked',error);throw error;}
      state(error.code==='NETWORK'?'offline':'failed',error);
     }
     finally{flushing=null;}
    })();
    return flushing;
   },
   async importWords(words){
    await load();
    if(count()||flushing)throw new Error('还有待同步操作，请完成同步后再导入');
    if(mode!=='synced')throw new Error('导入进度需要联网并完成同步');
    const revision=record.snapshot.revision;
    const response=await request('/api/progress/import',{method:'POST',body:{words,revision}});
    await store.accept(user.id,response,[]);await load();state('synced');
   }
  };
 }
 root.createOfflineClient=createOfflineClient;
 if(typeof module!=='undefined'&&module.exports)module.exports={createOfflineClient};
})(typeof globalThis!=='undefined'?globalThis:this);
