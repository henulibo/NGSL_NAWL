const test=require('node:test');
const assert=require('node:assert/strict');
const {IDBFactory}=require('fake-indexeddb');
const {openOfflineStore}=require('../server/static/offline-store.js');
const {createOfflineClient}=require('../server/static/offline-client.js');
const user={id:1,username:'alice',role:'user',active:true};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return {resolve,promise};}
async function fixture(){const indexedDB=new IDBFactory();const store=await openOfflineStore({indexedDB,name:'client-test'});await store.activate(user);await store.accept(1,{revision:0,words:{}},[]);return {store,indexedDB};}

function server(words={},revision=0){
 const seen=new Set();return async(path,options)=>{
  if(path==='/api/progress')return {revision,words:{...words}};
  assert.equal(path,'/api/progress/sync');
  for(const op of options.body.operations){if(!seen.has(op.id)){seen.add(op.id);revision++;if(op.status==='new')delete words[op.word_id];else words[op.word_id]=op.status;}}
  return {revision,words:{...words},acknowledged:options.body.operations.map(op=>op.id)};
 };
}

test('offline reload keeps edits and reconnect merges only touched words',async()=>{
 const {store,indexedDB}=await fixture();
 let online=false;const remote=server({'NGSL:the':'known'},4);
 const request=async(...args)=>{if(!online){const e=new Error('disconnected');e.code='NETWORK';throw e;}return remote(...args);};
 const client=createOfflineClient({store,user,request});await client.load();await client.setWord('NGSL:child','review');await client.flush();
 assert.equal(client.pendingCount,1);
 const restart=createOfflineClient({store:await openOfflineStore({indexedDB,name:'client-test'}),user,request});
 await restart.load();assert.deepEqual(restart.words,{'NGSL:child':'review'});
 online=true;await restart.flush();
 assert.deepEqual(restart.words,{'NGSL:the':'known','NGSL:child':'review'});assert.equal(restart.pendingCount,0);
});

test('a newer edit during an in-flight batch never disappears on old acknowledgement',async()=>{
 const {store}=await fixture();const entered=deferred(),reply=deferred();let first=true;
 const remote=server();
 const request=async(path,options)=>{if(path==='/api/progress/sync'&&first){first=false;entered.resolve();await reply.promise;}return remote(path,options);};
 const snapshots=[];const client=createOfflineClient({store,user,request,onSnapshot:s=>snapshots.push(s.words['NGSL:child'])});
 await client.load();await client.setWord('NGSL:child','known');const flushing=client.flush();await entered.promise;
 await client.setWord('NGSL:child','review');const index=snapshots.length;
 reply.resolve();await flushing;
 assert.equal(client.words['NGSL:child'],'review');assert.equal(client.pendingCount,0);
 assert.ok(snapshots.slice(index).every(value=>value==='review'));
});

test('expired session retains pending data and switching accounts blocks old uploads',async()=>{
 const {store}=await fixture();let sends=0;
 const client=createOfflineClient({store,user,request:async()=>{sends++;const e=new Error('login expired');e.status=401;throw e;}});
 await client.load();await client.setWord('NGSL:child','known');
 await assert.rejects(client.flush(),e=>e.status===401);assert.equal(client.pendingCount,1);
 await store.activate({id:2,username:'bob',role:'user',active:true});
 const previous=sends;await assert.rejects(client.flush(),e=>e.code==='ACCOUNT_CHANGED');assert.equal(sends,previous);
 assert.equal(Object.keys((await store.read(1)).pending).length,1);assert.deepEqual((await store.read(2)).pending,{});
});

test('two tabs share durable state and serialize their synchronization',async()=>{
 const {store,indexedDB}=await fixture();const entered=deferred(),reply=deferred();let first=true;
 const remote=server();const request=async(path,options)=>{if(path==='/api/progress/sync'&&first){first=false;entered.resolve();await reply.promise;}return remote(path,options);};
 const a=createOfflineClient({store,user,request}),b=createOfflineClient({store:await openOfflineStore({indexedDB,name:'client-test'}),user,request});
 await a.load();await b.load();await a.setWord('NGSL:child','known');const flushing=a.flush();await entered.promise;
 await b.setWord('NGSL:child','review');await b.flush();
 assert.equal(b.words['NGSL:child'],'review');reply.resolve();await flushing;await b.load();
 assert.equal(b.words['NGSL:child'],'review');assert.equal(b.pendingCount,0);
});

test('malformed acknowledgements never discard durable pending operations',async()=>{
 const {store}=await fixture();const client=createOfflineClient({store,user,request:async path=>path==='/api/progress'?{revision:0,words:{}}:{revision:1,words:{'NGSL:child':'known'},acknowledged:['unrelated-operation']}});
 await client.load();await client.setWord('NGSL:child','known');await client.flush();assert.equal(client.pendingCount,1);
 await assert.rejects(client.importWords({}),/待同步/);
});

test('unchanged background refreshes do not redraw the word controls',async()=>{
 const {store}=await fixture();let redraws=0;
 const client=createOfflineClient({store,user,request:server(),onSnapshot:()=>redraws++});
 await client.load();await client.flush();await client.flush();assert.equal(redraws,1);
 await client.setWord('NGSL:child','known');await client.flush();assert.equal(redraws,2);
});
