(function(root){
 'use strict';
 function createSyncClient({request,onSnapshot=()=>{}}){
  let revision=-1,words={},queue=Promise.resolve();
  function accept(snapshot){
   if(!Number.isSafeInteger(snapshot.revision)||snapshot.revision<0||!snapshot.words||Array.isArray(snapshot.words)||typeof snapshot.words!=='object')throw new Error('云端进度格式不正确');
   if(snapshot.revision<=revision)return false;
   revision=snapshot.revision;words={...snapshot.words};onSnapshot({revision,words:{...words}});return true;
  }
  function mutate(path,body,method){
   const operation=queue.then(()=>request(path,{method,body})).then(snapshot=>{accept(snapshot);return snapshot;});
   queue=operation.catch(()=>{});return operation;
  }
  return {
   accept,
   get revision(){return revision;},get words(){return {...words};},
   refresh:()=>request('/api/progress').then(snapshot=>{accept(snapshot);return snapshot;}),
   setWord:(word_id,status)=>mutate('/api/progress',{word_id,status},'PATCH'),
   importWords:words=>mutate('/api/progress/import',{words,revision},'POST')
  };
 }
 root.createSyncClient=createSyncClient;
 if(typeof module!=='undefined'&&module.exports)module.exports={createSyncClient};
})(typeof globalThis!=='undefined'?globalThis:this);
