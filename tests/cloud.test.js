const assert = require('node:assert/strict');
const test = require('node:test');
const {createSyncClient}=require('../server/static/sync-client.js');

function deferred(){let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j});return {promise,resolve,reject};}

test('a late snapshot cannot roll progress back', async()=>{
 const snapshots=[];
 const sync=createSyncClient({request:async()=>({revision:3,words:{'NGSL:child':'known'}}),onSnapshot:s=>snapshots.push(s)});
 sync.accept({revision:2,words:{}});sync.accept({revision:5,words:{'NGSL:the':'review'}});sync.accept({revision:3,words:{'NGSL:child':'known'}});
 assert.equal(sync.revision,5);assert.deepEqual(sync.words,{'NGSL:the':'review'});assert.equal(snapshots.length,2);
});

test('mutations are serial and a failed save never becomes confirmed progress', async()=>{
 const first=deferred();let calls=0;
 const sync=createSyncClient({request:async(path,options)=>{calls++;if(calls===1)return first.promise;return {revision:2,words:{'NGSL:the':'review'}}}});
 sync.accept({revision:0,words:{}});
 const a=sync.setWord('NGSL:child','known');const b=sync.setWord('NGSL:the','review');
 await new Promise(r=>setImmediate(r));assert.equal(calls,1);
 first.reject(new Error('offline'));await assert.rejects(a,/offline/);await b;
 assert.deepEqual(sync.words,{'NGSL:the':'review'});
});

test('import conflicts are reported without changing confirmed words',async()=>{
 let payload;
 const sync=createSyncClient({request:async(path,options)=>{payload=options.body;const e=new Error('changed');e.status=409;throw e;}});
 sync.accept({revision:4,words:{'NGSL:child':'known'}});
 await assert.rejects(sync.importWords({'NGSL:the':'review'}),e=>e.status===409);
 assert.equal(payload.revision,4);assert.deepEqual(sync.words,{'NGSL:child':'known'});
});
