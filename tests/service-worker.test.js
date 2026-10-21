const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const origin='https://study.test';const version='test-version-1';
const assets=['/offline-shell','/login','/assets/cloud.js?v='+version];
function environment({fail=null,redirectShell=false,mixedVersion=false}={}){
 const handlers={},storage=new Map();let network=true;
 const key=value=>new URL(typeof value==='string'?value:value.url,origin).href;
 const caches={
  async keys(){return [...storage.keys()];},async delete(name){return storage.delete(name);},
  async open(name){if(!storage.has(name))storage.set(name,new Map());const cache=storage.get(name);return {async match(request){return cache.get(key(request))?.clone();},async put(request,response){cache.set(key(request),response.clone());}};}
 };
 const fetch=async request=>{const url=key(request);if(!network||url.includes(fail||'\u0000'))throw new TypeError('unreachable');return new Response(url.includes('offline-shell')?'workbook':'resource',{headers:redirectShell&&url.includes('offline-shell')?{}:{'X-Workbook-Version':mixedVersion&&url.includes('cloud.js')?'newer-release':version}});};
 const context={URL,Response,Promise,caches,fetch,self:{location:{origin},addEventListener:(type,handler)=>handlers[type]=handler,skipWaiting:async()=>{},clients:{claim:async()=>{}}}};
 const source=fs.readFileSync('server/static/service-worker.js','utf8').replaceAll('__CACHE_VERSION__',version).replace('__ASSETS__',JSON.stringify(assets));
 vm.runInNewContext(source,context);
 async function event(type,extra={}){let task,response;handlers[type]({...extra,waitUntil:p=>{task=p;},respondWith:p=>{response=p;}});if(task)await task;return response?await response:null;}
 return {event,caches,storage,offline:()=>{network=false;}};
}

test('complete install serves workbook and assets after network loss while bypassing APIs',async()=>{
 const e=environment();await e.event('install');await e.event('activate');e.offline();
 const root=await e.event('fetch',{request:{url:origin+'/',method:'GET',mode:'navigate'}});assert.equal(await root.text(),'workbook');
 const asset=await e.event('fetch',{request:{url:origin+assets[2],method:'GET',mode:'cors'}});assert.equal(await asset.text(),'resource');
 for(const path of ['/api/me','/api/progress','/account'])assert.equal(await e.event('fetch',{request:{url:origin+path,method:'GET',mode:'navigate'}}),null);
 assert.equal(await e.event('fetch',{request:{url:origin+'/api/progress/sync',method:'POST'}}),null);
 assert.equal(await e.event('fetch',{request:{url:'https://other.test/',method:'GET',mode:'navigate'}}),null);
});

test('failed resource update preserves an older complete cache and removes partial data',async()=>{
 const e=environment({fail:'cloud.js'});const old=await e.caches.open('ielts-workbook-v1-old');await old.put('/offline-shell',new Response('older workbook'));
 await assert.rejects(e.event('install'),/unreachable/);
 assert.equal(await (await old.match('/offline-shell')).text(),'older workbook');
 assert.deepEqual(await e.caches.keys(),['ielts-workbook-v1-old']);
});

test('a redirected login page cannot be mistaken for a cached authenticated workbook',async()=>{
 const e=environment({redirectShell:true});await assert.rejects(e.event('install'),/学习页面/);assert.deepEqual(await e.caches.keys(),[]);
});

test('activation cleans only older workbook caches and readiness reports the installed version',async()=>{
 const e=environment();await e.caches.open('another-app');await e.caches.open('ielts-workbook-v1-old');await e.event('install');await e.event('activate');
 assert.deepEqual((await e.caches.keys()).sort(),['another-app','ielts-workbook-v1-'+version]);
 let response;await e.event('message',{data:{type:'CHECK_READY'},ports:[{postMessage:data=>{response=data;}}]});
 assert.equal(response.ready,true);assert.equal(response.version,version);
});


test('a release change during asset download cannot replace a complete older cache',async()=>{
 const e=environment({mixedVersion:true});const old=await e.caches.open('ielts-workbook-v1-old');await old.put('/offline-shell',new Response('older workbook'));
 await assert.rejects(e.event('install'),/资源/);assert.deepEqual(await e.caches.keys(),['ielts-workbook-v1-old']);
});
