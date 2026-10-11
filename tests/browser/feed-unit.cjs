/* Pure no-network tests of remote metadata, rate-limit fallback, and scope guards. */
const fs=require('fs');const vm=require('vm');const assert=require('assert');
const script=fs.readFileSync('docs/assets/site.js','utf8');
const sample=JSON.parse(fs.readFileSync('docs/data/feed.json','utf8'));
// Freeze the test clock around the fixture, so a genuinely stale committed snapshot
// cannot turn a correct production warning into a future CI failure.
const NOW=Date.parse(sample.checked_at)+60000;
class TestDate extends Date { static now(){return NOW;} }
async function run({remote=sample,remoteFails=false,localFails=false,cache}={}) {
  const calls=[];let resolve;
  const result=new Promise(r=>{resolve=r;});
  const element={dataset:{},set textContent(text){resolve(text);}};
  const store=new Map(cache?[['gems65-source-feed',JSON.stringify(cache)]]:[]);
  const context={document:{querySelector:sel=>sel==='[data-feed-status]'?element:null},
    Date:TestDate,TextDecoder,AbortSignal,atob,console,
    sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},
    fetch:async url=>{calls.push(url);const external=url.startsWith('https://api.github.com/');
      assert(external||url==='data/feed.json','Unexpected external request');
      return {ok:external?!remoteFails:!localFails,json:async()=>external?{
        encoding:'base64',content:Buffer.from(JSON.stringify(remote)).toString('base64')}:sample};}
  };
  vm.runInNewContext(script,context);
  return {text:await result,calls,state:element.dataset.state};
}
(async()=>{
  let r=await run();assert(r.text.includes('GITHUB METADATA SNAPSHOT'));assert.equal(r.calls.length,1);
  r=await run({remoteFails:true});assert(r.text.includes('LOCAL FALLBACK SNAPSHOT'));assert.equal(r.calls.length,2);
  r=await run({remote:{...sample,organizer_verified:true}});assert(r.text.includes('LOCAL FALLBACK SNAPSHOT'));
  r=await run({remote:{...sample,training_rerun:true}});assert(r.text.includes('LOCAL FALLBACK SNAPSHOT'));
  r=await run({remote:{...sample,checked:NaN}});assert(r.text.includes('LOCAL FALLBACK SNAPSHOT'));
  r=await run({remoteFails:true,localFails:true});assert(r.text.includes('could not be loaded'));
  r=await run({cache:{saved:NOW,data:sample}});assert.equal(r.calls.length,0);
  r=await run({remote:{...sample,checked_at:new Date(NOW+600000).toISOString()}});assert(r.text.includes('TIMESTAMP REQUIRES REVIEW'));assert.equal(r.state,'caution');
  r=await run({remote:{...sample,checked_at:new Date(NOW-49*3600*1000).toISOString()}});assert(r.text.includes('STALE SNAPSHOT'));assert.equal(r.state,'caution');
  console.log('9 browser-feed unit cases passed; no organizer request or token.');
})().catch(e=>{console.error(e);process.exitCode=1;});
