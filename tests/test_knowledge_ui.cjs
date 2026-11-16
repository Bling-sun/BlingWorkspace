const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/app.js'), 'utf8');
function harness() {
  const nodes = new Map();
  const node = id => { if (!nodes.has(id)) nodes.set(id, { value: '', innerHTML: '', textContent: '', onclick: null, focus() {}, querySelector: id => node(id), querySelectorAll: () => [] }); return nodes.get(id); };
  const document = { querySelector: node, querySelectorAll: () => [] };
  const sandbox = { document, console, AbortController, setTimeout, clearTimeout, localStorage: { getItem() { return null; }, setItem() {} } };
  vm.createContext(sandbox);
  vm.runInContext(source.slice(0, source.indexOf("S.libFilter =")), sandbox);
  vm.runInContext(source.slice(source.indexOf('function renderKnowledgeImporter('), source.indexOf('function renderKnowledgePlan(')), sandbox);
  vm.runInContext(source.slice(source.indexOf('async function organizeStudy('), source.indexOf('/* ---------------- 启动')), sandbox);
  vm.runInContext(source.slice(source.indexOf('function talkedSet('), source.indexOf('function nextStation(')), sandbox);
  return { sandbox, node, run: code => vm.runInContext(code, sandbox) };
}
test('knowledge selects its own stations and preserves learning vocabulary', () => {
  const h = harness();
  h.run("setKind('knowledge')");
  assert.equal(h.run('isKnowledge()'), true);
  assert.equal(h.run('STATIONS.length'), 9);
  assert.match(h.run("ST['7'].prompt"), /等我回答再判分/);
  assert.match(h.run("ST['6'].prompt"), /没有近期材料/);
  assert.match(h.run('noteLabel()'), /知识点/);
  h.run("S.paper={messages:[{role:'assistant',station:'0'}]}");
  assert.equal(h.run("talkedSet().has('1')"), false);
  h.run("setKind('repo')");
  assert.equal(h.run('isRepo()'), true);
  assert.match(h.run("ST['3'].label"), /入口/);
});
test('knowledge form includes configurable context, frontier sources and concrete goals', () => {
  const h = harness();
  h.run("renderKnowledgeImporter(document.querySelector('#importer'), '<nav>types</nav>')");
  const html = h.node('#importer').innerHTML;
  for (const expected of ['Action Chunk', 'Flow Matching', 'RSI', 'Harness', 'RTC', 'knowledgeDomain', 'knowledgeLevel', 'knowledgeMode', 'knowledgeGoal', 'knowledgeUrls']) assert.ok(html.includes(expected), expected);
  assert.match(html, /没有近期证据/);
});
test('one-click TeX waits for notes, streams report and downloads selected artifact', async () => {
  const h = harness();
  h.node('#studyFormat').value = 'tex';
  h.run("S.slug='knowledge-demo'; globalThis.calls=[]; globalThis.flushSave=async()=>{calls.push('saved');return true}; globalThis.openModal=()=>{};globalThis.toast=()=>{};globalThis.downloadLearning=async url=>calls.push(url); globalThis.streamPost=async (url,body,cb)=>{calls.push(url);calls.push(body.format);cb({type:'progress',text:'working'});cb({type:'text',text:'summary'});cb({type:'done',url:'/report.tex'})}");
  await h.run('organizeStudy()');
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(calls)')), ['saved', '/api/papers/knowledge-demo/study-export', 'tex', '/report.tex']);
  assert.equal(h.run('S.reportCtrl'), null);
});
test('failed save or model error prevents downloading incomplete report', async () => {
  const h = harness();
  h.node('#studyFormat').value = 'tex';
  h.run("globalThis.calls=[];globalThis.flushSave=async()=>false;globalThis.streamPost=async()=>calls.push('request'); globalThis.toast=()=>{};globalThis.openModal=()=>{};globalThis.downloadLearning=async()=>calls.push('download')");
  await h.run('organizeStudy()');
  assert.equal(h.run('calls.length'), 0);
  h.run("globalThis.flushSave=async()=>true;globalThis.streamPost=async (url,body,cb)=>cb({type:'error',error:'quota'})");
  await h.run('organizeStudy()');
  assert.equal(h.run('calls.length'), 0);
  assert.match(h.node('#reportStatus').textContent, /quota/);
});
