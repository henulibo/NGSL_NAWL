const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const {IDBFactory}=require('fake-indexeddb');const {openOfflineStore}=require('../server/static/offline-store.js');const {createOfflineClient}=require('../server/static/offline-client.js');
const alice={id:1,username:'alice',role:'user',active:true};
function page(store,fetch){
 const status={textContent:'',classList:{toggle(){}}},other={textContent:'',addEventListener(){}};
 const snapshots=[];const context={window:{addEventListener(){}},openOfflineStore:async()=>store,createOfflineClient,prepareOfflineResources:async()=>({ready:true}),fetch,
 document:{getElementById:id=>id==='save-status'?status:other,addEventListener(){},visibilityState:'visible'},localStorage:{getItem(){return null;},setItem(){}},location:{replace(){},reload(){}},setInterval(){}};
 vm.runInNewContext(fs.readFileSync('server/static/cloud.js','utf8'),context);
 return {cloud:context.window.cloud,status,snapshots,hooks:{readView:()=>({}),applyView(){},applySnapshot:s=>snapshots.push(s.words),toast(){}}};
}

test('cached offline boot still reports offline after resource readiness completes',async()=>{
 const store=await openOfflineStore({indexedDB:new IDBFactory(),name:'offline-boot'});await store.activate(alice);await store.accept(1,{revision:0,words:{'NGSL:child':'known'}},[]);
 const p=page(store,async()=>{throw new TypeError('network unavailable');});await p.cloud.boot(p.hooks);await new Promise(r=>setImmediate(r));
 assert.equal(p.cloud.ready,true);assert.deepEqual(p.snapshots.at(-1),{'NGSL:child':'known'});assert.match(p.status.textContent,/^离线学习/);
});

test('online boot under a different login does not display or send the previous accounts queue',async()=>{
 const store=await openOfflineStore({indexedDB:new IDBFactory(),name:'changed-login'});await store.activate(alice);await store.accept(1,{revision:0,words:{}},[]);await store.enqueue(1,{word_id:'NGSL:child',status:'known'});
 const bob={id:2,username:'bob',role:'user',active:true};const words={};let revision=0;
 const p=page(store,async(path,options)=>({ok:true,status:200,json:async()=>{
  if(path==='/api/me')return {user:bob,csrf:'bob-csrf'};
  if(path==='/api/progress')return {revision,words:{...words}};
  assert.equal(path,'/api/progress/sync');const ops=JSON.parse(options.body).operations;
  for(const op of ops){assert.equal(op.word_id,'NGSL:the');words[op.word_id]=op.status;revision++;}
  return {revision,words:{...words},acknowledged:ops.map(op=>op.id)};
 }}));
 await p.cloud.boot(p.hooks);assert.deepEqual(p.snapshots.at(-1),{});await p.cloud.setWord('NGSL:the','review');await p.cloud.refresh();
 assert.deepEqual(words,{'NGSL:the':'review'});assert.equal(Object.keys((await store.read(1)).pending).length,1);
 assert.ok(!p.snapshots.some(snapshot=>'NGSL:child' in snapshot));
});
