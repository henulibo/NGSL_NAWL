const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const {createSyncClient}=require('../server/static/sync-client.js');

test('a changed shared login reloads the old tab before accepting other progress',async()=>{
 let changed=false,reloads=0,snapshots=0;
 const element={textContent:'',classList:{toggle(){}},addEventListener(){}};
 const context={window:{},createSyncClient,document:{getElementById:()=>element,addEventListener(){},visibilityState:'visible'},localStorage:{getItem(){return null;},setItem(){}},location:{replace(){},reload(){reloads++;}},setInterval(){},fetch:async path=>({ok:!changed,status:changed?403:200,json:async()=>changed?{detail:'session changed'}:path==='/api/me'?{csrf:'first',user:{id:1,username:'alice'}}:{revision:0,words:{}}})};
 vm.runInNewContext(fs.readFileSync('server/static/cloud.js','utf8'),context);
 await context.window.cloud.boot({readView:()=>({}),applyView(){},applySnapshot(){snapshots++;},toast(){}});
 changed=true;
 await context.window.cloud.refresh();
 assert.equal(reloads,1);
 assert.equal(context.window.cloud.ready,false);
 assert.equal(snapshots,1);
});
