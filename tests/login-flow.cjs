const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../src/login.js'),'utf8');
async function run(blocked=false,failed=false){
 const nodes={};const get=id=>nodes[id]??=( {disabled:true,hidden:true,value:'',textContent:''} );
 const copied=[],opened=[];
 const context={document:{getElementById:get},navigator:{clipboard:{writeText:async text=>{if(blocked)throw Error('denied');copied.push(text)}}},window:{open:(...args)=>opened.push(args)},location:{reload(){}},setTimeout:()=>1,clearTimeout(){},fetch:async path=>({ok:!(failed&&path==='/api/connect'),json:async()=>path==='/api/session'?{csrf:'test',server:'http://127.0.0.1:8096'}:failed?{error:'Server unavailable'}:{code:'012345',approvalUrl:'http://127.0.0.1:8096/web/#/quickconnect'}})};
 vm.runInNewContext(source,context);await new Promise(setImmediate);
 get('jellyfinSignIn').onclick();assert.equal(opened.length,0);
 await get('signIn').onclick();assert.equal(opened.length,0,'Connect must not open Jellyfin automatically');
 if(failed){assert.equal(get('jellyfinSignIn').disabled,true);assert.equal(copied.length,0);return;}
 assert.equal(get('code').textContent,'012345');assert.equal(get('signIn').disabled,false);
 assert.equal(get('jellyfinSignIn').disabled,false);
 if(blocked)assert.match(get('loginStatus').textContent,/blocked/);else assert.deepEqual(copied,['012345']);
 get('jellyfinSignIn').onclick();assert.equal(opened[0][0],'http://127.0.0.1:8096/web/#/quickconnect');assert.equal(opened[0][2],'noopener,noreferrer');
}
(async()=>{await run();await run(true);await run(false,true);console.log('PASS: automatic copy, blocked-copy message, correct approval link, explicit-only opening, connection failure, leading-zero code, retry enabled.');})().catch(e=>{console.error(e);process.exit(1)});