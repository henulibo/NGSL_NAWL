'use strict';
const VERSION='__CACHE_VERSION__';
const PREFIX='ielts-workbook-v1-';
const CACHE=PREFIX+VERSION;
const ASSETS=__ASSETS__;
const absolute=path=>new URL(path,self.location.origin).href;
const assetUrls=new Set(ASSETS.filter(path=>path.startsWith('/assets/')).map(absolute));
async function complete(cache){
 const responses=await Promise.all(ASSETS.map(path=>cache.match(path)));
 return responses.every(response=>response&&response.ok&&response.headers.get('X-Workbook-Version')===VERSION);
}
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(CACHE);
 if(await complete(cache)){await self.skipWaiting();return;}
 try{
  for(const path of ASSETS){
   const response=await fetch(absolute(path),{credentials:'same-origin',cache:'no-store'});
   if(!response.ok||response.redirected||response.headers.get('X-Workbook-Version')!==VERSION)throw new Error('离线学习页面或资源尚未准备好');
   await cache.put(path,response.clone());
   const pathname=new URL(path,self.location.origin).pathname;
   if(['/offline-shell','/login'].includes(pathname))await cache.put(pathname,response.clone());
  }
  await self.skipWaiting();
 }catch(error){await caches.delete(CACHE);throw error;}
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 if(!await complete(await caches.open(CACHE)))throw new Error('离线资源不完整');
 for(const name of await caches.keys())if(name.startsWith(PREFIX)&&name!==CACHE)await caches.delete(name);
 await self.clients.claim();
})()));
self.addEventListener('message',event=>{
 if(event.data?.type!=='CHECK_READY'||!event.ports?.[0])return;
 event.waitUntil((async()=>{event.ports[0].postMessage({version:VERSION,ready:await complete(await caches.open(CACHE))});})());
});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin)return;
 if(assetUrls.has(url.href)){
  event.respondWith((async()=>{const cache=await caches.open(CACHE);return await cache.match(request)||fetch(request);})());return;
 }
 if(request.mode==='navigate'&&['/','/login','/offline-shell'].includes(url.pathname)){
  event.respondWith((async()=>{
   try{const response=await fetch(request);if(response.status<500)return response;}
   catch(error){}
   const cache=await caches.open(CACHE),fallback=await cache.match(url.pathname==='/login'?'/login':'/offline-shell');
   return fallback||new Response('离线资源尚未缓存，请联网后重新打开。',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
  })());
 }
});
