'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
test('unsupported browsers explain that offline page caching is unavailable',async()=>{
 const context=vm.createContext({navigator:{}});
 vm.runInContext(fs.readFileSync('server/static/offline-resources.js','utf8'),context);
 const result=await context.prepareOfflineResources();
 assert.equal(result.ready,false);
 assert.match(result.reason,/此浏览器不支持离线页面/);
});
test('an existing old worker waits for the newly requested version',async()=>{
 let updates=0;
 const worker=version=>({state:'activated',postMessage(data,ports){queueMicrotask(()=>ports[0].reply({ready:true,version}));}});
 const old=worker('old'),fresh=worker('new');
 const registration={active:old,installing:null,waiting:null,async update(){updates++;this.installing=fresh;}};
 class Channel{constructor(){this.port1={close(){}};this.port2={reply:data=>this.port1.onmessage({data})};}}
 const context=vm.createContext({navigator:{serviceWorker:{async getRegistration(){return registration;},async register(){return registration;}}},document:{querySelector(){return {content:'new'};}},MessageChannel:Channel,setTimeout,clearTimeout});
 vm.runInContext(fs.readFileSync('server/static/offline-resources.js','utf8'),context);
 const result=await context.prepareOfflineResources();
 assert.equal(result.ready,true);assert.equal(updates,1);
});
