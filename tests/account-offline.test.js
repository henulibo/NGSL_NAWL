const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const {IDBFactory}=require('fake-indexeddb');const {openOfflineStore}=require('../server/static/offline-store.js');const {createOfflineClient}=require('../server/static/offline-client.js');
const alice={id:1,username:'alice',role:'user',active:true},bob={id:2,username:'bob',role:'user',active:true};
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};}
function element(){return {value:'test-password-2468',textContent:'',handlers:{},classList:{toggle(){}},addEventListener(type,fn){this.handlers[type]=fn;},querySelector:()=>({disabled:false}),reset(){},replaceChildren(){},close(){}};}
function page(store,fetch,{login=false,cloud=false}={}){
 const elements=new Map();const get=id=>{if(id==='login-form'&&!login)return null;if(!elements.has(id))elements.set(id,element());return elements.get(id);};const redirects=[];
 const context={window:{addEventListener(){},indexedDB:{}},indexedDB:{},URLSearchParams,openOfflineStore:async()=>store,createOfflineClient,prepareOfflineResources:async()=>({ready:true}),fetch,
  document:{getElementById:get,addEventListener(){},visibilityState:'visible'},location:{search:'',replace:path=>redirects.push(path),reload(){}},localStorage:{getItem(){return null;},setItem(){}},setInterval(){}};
 vm.runInNewContext(fs.readFileSync('server/static/'+(cloud?'cloud.js':'account.js'),'utf8'),context);
 return {get,redirects,cloud:context.window.cloud};
}
async function fixture(){const store=await openOfflineStore({indexedDB:new IDBFactory(),name:'account-transitions'});await store.activate(alice);await store.accept(1,{revision:0,words:{}},[]);return store;}

for(const operation of ['logout','password'])test('account '+operation+' preserves an edit committed while the response is pending',async()=>{
 const store=await fixture(),entered=deferred(),reply=deferred();
 const p=page(store,async path=>{
  if(path!=='/api/me'){entered.resolve();await reply.promise;}
  return {ok:true,status:200,json:async()=>path==='/api/me'?{user:alice,csrf:'alice-csrf'}:{ok:true}};
 });
 await new Promise(r=>setImmediate(r));
 const closing=operation==='logout'?p.get('logout').handlers.click():p.get('password-form').handlers.submit({preventDefault(){}});
 await entered.promise;const edit=await store.enqueue(1,{word_id:'NGSL:child',status:'review'});reply.resolve();await closing;
 assert.equal((await store.read(1)).pending['NGSL:child'].id,edit.id);assert.equal(await store.active(),null);assert.equal(p.redirects.at(-1),'/login?pending=1');
});

test('workbook logout also preserves a concurrent edit for reauthentication',async()=>{
 const store=await fixture(),entered=deferred(),reply=deferred();
 const p=page(store,async path=>{
  if(path==='/api/auth/logout'){entered.resolve();await reply.promise;}
  return {ok:true,status:200,json:async()=>path==='/api/me'?{user:alice,csrf:'alice-csrf'}:path==='/api/progress'?{revision:0,words:{}}:{ok:true}};
 },{cloud:true});
 await p.cloud.boot({readView:()=>({}),applyView(){},applySnapshot(){},toast(){}});
 const closing=p.get('logout-btn').handlers.click();await entered.promise;
 const edit=await store.enqueue(1,{word_id:'NGSL:child',status:'review'});reply.resolve();await closing;
 assert.equal((await store.read(1)).pending['NGSL:child'].id,edit.id);assert.equal(await store.active(),null);assert.equal(p.redirects.at(-1),'/login?pending=1');
});

test('successful login updates offline identity before navigation even if the next request loses connectivity',async()=>{
 const store=await fixture();await store.enqueue(1,{word_id:'NGSL:child',status:'known'});const entered=deferred(),reply=deferred();
 const p=page(store,async(path,options)=>{assert.equal(path,'/api/auth/login');assert.equal(JSON.parse(options.body).username,'bob');entered.resolve();await reply.promise;return {ok:true,status:200,json:async()=>({user:bob,csrf:'bob-csrf'})};},{login:true});
 p.get('username').value='bob';const signingIn=p.get('login-form').handlers.submit({preventDefault(){}});await entered.promise;
 assert.equal(await store.active(),null);reply.resolve();await signingIn;
 assert.equal((await store.active()).id,2);assert.equal(p.redirects.at(-1),'/');assert.equal(Object.keys((await store.read(1)).pending).length,1);
 const disconnected=page(store,async()=>{throw new TypeError('offline');},{cloud:true});let snapshots=0;
 await assert.rejects(disconnected.cloud.boot({readView:()=>({}),applyView(){},applySnapshot(){snapshots++;},toast(){}}),/尚未缓存/);
 assert.equal(snapshots,0);assert.equal(disconnected.cloud.ready,false);
});
