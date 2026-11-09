const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('src/index.html', 'utf8');
assert(html.includes('id="update-dialog"'), 'update dialog must exist');
assert(html.includes('check_update_python'), 'frontend must start an asynchronous update check');
assert(html.includes('open_release_page_python'), 'frontend must open the official release page');
assert(html.includes('copyUpdateSha256'), 'frontend must copy the published SHA256');
assert(html.includes('setTimeout(() => checkForUpdates(false,true), 4000)'), 'startup check must be delayed');
assert(html.includes('当前版本：v'), 'frontend must show the current version');
console.log('update UI checks passed');

const elements = Object.fromEntries(['update-current','update-status','update-notes','update-sha256','update-action','update-open-release','update-copy-sha'].map(id => [id,{disabled:true,textContent:''}]));
let opened = [];
let alerts = [];
const context = {
  APP_VERSION:'1.4.6', updateState:{status:'error',release:null,error:'Release 缺少 SHA-256 文件'},
  document:{getElementById:id=>elements[id]},
  window:{pywebview:{api:{open_release_page_python:async url=>{opened.push(url);return {status:'success'};}}}},
  alert:message=>alerts.push(message),
};
const start=html.indexOf('function renderUpdateState()');
const end=html.indexOf('async function exportPlot(',start);
vm.runInNewContext(html.slice(start,end),context);
context.renderUpdateState();
assert.strictEqual(elements['update-open-release'].disabled,false,'release button stays enabled on failed check');
assert.strictEqual(elements['update-copy-sha'].disabled,true,'missing checksum cannot be copied');
Promise.resolve().then(async()=>{
  await context.openReleasePage();
  assert.deepStrictEqual(opened,[''],'null release must invoke backend fallback');
  context.updateState={status:'up-to-date',release:{version:'1.4.5',release_url:'https://github.com/zhao78574/Perovskite_PC/releases/tag/v1.4.5',sha256:''}};
  context.renderUpdateState();
  assert.strictEqual(elements['update-open-release'].disabled,false);
  assert(elements['update-status'].textContent.includes('没有更新版本'));
  await context.openReleasePage();
  assert.strictEqual(opened[1],context.updateState.release.release_url);
  context.window.pywebview.api.open_release_page_python=async()=>({status:'error',message:'browser unavailable'});
  await context.openReleasePage();
  assert(alerts[0].includes('browser unavailable'),'browser failure must be visible');
  console.log('update UI interaction checks passed');
}).catch(error=>{console.error(error);process.exitCode=1;});
