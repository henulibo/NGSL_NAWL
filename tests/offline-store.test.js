const test=require('node:test');
const assert=require('node:assert/strict');
const {IDBFactory}=require('fake-indexeddb');
const {openOfflineStore}=require('../server/static/offline-store.js');
const alice={id:1,username:'alice',role:'user',active:true};
const bob={id:2,username:'bob',role:'user',active:true};

async function fixture(){const indexedDB=new IDBFactory();return {indexedDB,store:await openOfflineStore({indexedDB,name:'test-offline'})};}

test('committed offline edits survive another connection and contain no auth secrets',async()=>{
 const {store,indexedDB}=await fixture();
 await store.activate({...alice,password:'not-for-storage',csrf:'not-for-storage'});
 await store.accept(1,{revision:2,words:{'NGSL:the':'known'}},[]);
 const operation=await store.enqueue(1,{word_id:'NGSL:child',status:'review'});
 const restarted=await openOfflineStore({indexedDB,name:'test-offline'});
 const saved=await restarted.read(1);
 assert.deepEqual(saved.snapshot.words,{'NGSL:the':'known'});
 assert.equal(saved.pending['NGSL:child'].id,operation.id);
 assert.deepEqual(await restarted.active(),alice);
 assert.ok(!JSON.stringify(saved).includes('not-for-storage'));
});

test('an acknowledgement cannot delete a newer edit or roll back a snapshot',async()=>{
 const {store}=await fixture();await store.activate(alice);
 const old=await store.enqueue(1,{word_id:'NGSL:child',status:'known'});
 const newer=await store.enqueue(1,{word_id:'NGSL:child',status:'review'});
 await store.accept(1,{revision:5,words:{'NGSL:the':'known'}},[]);
 await store.accept(1,{revision:3,words:{'NGSL:child':'known'}},[old.id]);
 const saved=await store.read(1);
 assert.equal(saved.pending['NGSL:child'].id,newer.id);
 assert.deepEqual(saved.snapshot,{revision:5,words:{'NGSL:the':'known'}});
 await store.accept(1,{revision:6,words:{'NGSL:child':'review'}},[newer.id]);
 assert.deepEqual((await store.read(1)).pending,{});
});

test('account switching cannot enqueue into the previous account and logout keeps sequence monotonic',async()=>{
 const {store}=await fixture();await store.activate(alice);
 const first=await store.enqueue(1,{word_id:'NGSL:child',status:'known'});
 await store.activate(bob);
 await assert.rejects(store.enqueue(1,{word_id:'NGSL:the',status:'review'}),e=>e.code==='ACCOUNT_CHANGED');
 assert.deepEqual((await store.read(2)).pending,{});
 await store.clearUser(1);assert.equal((await store.active()).id,2);
 await store.activate(alice);
 const second=await store.enqueue(1,{word_id:'NGSL:child',status:'review'});
 assert.equal(second.device_id,first.device_id);assert.ok(second.sequence>first.sequence);
});

test('persistent leases exclude other tabs and only their owner may release them',async()=>{
 const {store,indexedDB}=await fixture();
 const tab=await openOfflineStore({indexedDB,name:'test-offline'});
 assert.equal(await store.lease('user-1','tab-a',3000,1000),true);
 assert.equal(await tab.lease('user-1','tab-b',4000,2000),false);
 await tab.release('user-1','tab-b');
 assert.equal(await tab.lease('user-1','tab-b',4000,2001),false);
 assert.equal(await tab.lease('user-1','tab-b',6000,4001),true);
 await store.release('user-1','tab-a');
 assert.equal(await store.lease('user-1','tab-a',7000,5000),false);
});

test('a failed storage write leaves the previously committed progress unchanged',async()=>{
 const {store}=await fixture();await store.activate(alice);
 const {IDBObjectStore}=require('fake-indexeddb');const original=IDBObjectStore.prototype.put;
 IDBObjectStore.prototype.put=function(value,key){
  if(this.name==='users'&&Object.keys(value.pending||{}).length)throw new DOMException('disk full','QuotaExceededError');
  return original.call(this,value,key);
 };
 try{await assert.rejects(store.enqueue(1,{word_id:'NGSL:child',status:'known'}),e=>e.name==='QuotaExceededError');}
 finally{IDBObjectStore.prototype.put=original;}
 assert.deepEqual((await store.read(1)).pending,{});
});

test('cleanup preserves a concurrently committed edit while clearing offline identity',async()=>{
 const {store}=await fixture();await store.activate(alice);await store.accept(1,{revision:0,words:{}},[]);
 const operation=await store.enqueue(1,{word_id:'NGSL:child',status:'review'});
 const result=await store.clearUser(1);
 assert.equal(result.pending,1);assert.equal(await store.active(),null);
 assert.equal((await store.read(1)).pending['NGSL:child'].id,operation.id);
 await store.activate(alice);await store.accept(1,{revision:1,words:{'NGSL:child':'review'}},[operation.id]);
 assert.equal((await store.clearUser(1)).pending,0);assert.equal(await store.read(1),null);
});

test('a delayed boot cannot replace the identity from a newer successful login',async()=>{
 const {store}=await fixture();await store.activate(alice);await store.deactivate();
 await assert.rejects(store.activate(alice,{expectedActiveId:null}),e=>e.code==='LOGIN_TRANSITION');
 await store.activate(bob);
 await assert.rejects(store.activate(alice,{expectedActiveId:1}),e=>e.code==='ACCOUNT_CHANGED');
 assert.equal((await store.active()).id,2);
});
