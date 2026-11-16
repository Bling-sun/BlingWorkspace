const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/static/work-groups.js'), 'utf8'), context);
const { entries, matches } = context.BlingWorks;
const paper = { slug: 'paper', kind: 'paper', title: 'SuperMimic paper', arxiv_id: '2610.28480', mtime: 1, progress: { messages: 8 } };
const site = { slug: 'site', kind: 'website', title: 'SuperMimic demo', source_url: 'https://supermimic.github.io', mtime: 2, progress: { messages: 4 } };
const code = { slug: 'code', kind: 'repo', title: 'controller', languages: [{ name: 'Python' }], mtime: 3, progress: { messages: 2 } };
const group = { id: 'work', title: 'SuperMimic', primary_slug: 'paper', members: [paper, site, code] };
test('one work entry replaces separate cards without modifying materials', () => {
  const original = JSON.stringify([paper, site, code]);
  const list = entries([paper, site, code], [group]);
  assert.equal(list.length, 1); assert.equal(list[0].slug, 'paper'); assert.equal(list[0].kind, 'work');
  assert.equal(list[0].members.length, 3); assert.equal(list[0].progress.messages, 14);
  assert.equal(JSON.stringify([paper, site, code]), original);
});
test('search and filters include secondary materials and their languages', () => {
  const work = entries([paper, site, code], [group])[0];
  for (const query of ['Python', '2610.28480', 'supermimic.github.io', 'controller']) assert.equal(matches(work, query, 'all'), true);
  assert.equal(matches(work, '', 'repo'), true); assert.equal(matches(work, '', 'paper'), true);
  assert.equal(matches(work, 'unrelated', 'all'), false);
});
test('recycled materials stay absent; restore and dissolve recover original entries', () => {
  const list = entries([site], [group]); assert.equal(list.length, 1); assert.equal(list[0].slug, 'site');
  assert.equal(list[0].members.length, 1); assert.equal(entries([], [group]).length, 0);
  assert.equal(entries([paper, site, code], []).length, 3);
});

const app = fs.readFileSync(path.join(__dirname, '../web/static/app.js'), 'utf8');
const saveCode = app.slice(app.indexOf('function flushSave() {'), app.indexOf("window.addEventListener('beforeunload'"));
const routeCode = app.slice(app.indexOf('async function route() {'), app.indexOf("window.addEventListener('hashchange'"));
function saving(api) {
  const state = { slug: 'paper', notes: { sections: { s1: 'first note' } }, saveState: '未保存', saveTimer: null };
  const changes = [];
  const ctx = vm.createContext({ S: state, api, clearTimeout() {}, setSaveState(value) { state.saveState = value; }, toast() {},
    history: { replaceState(_a, _b, hash) { changes.push(hash); } }, location: { hash: '#/p/site' },
    openPaper(slug) { changes.push('opened:' + slug); }, showLibrary() { changes.push('library'); } });
  vm.runInContext(saveCode + routeCode, ctx);
  return { ctx, state, changes };
}
test('switching materials waits for an in-flight save and keeps the original note destination', async () => {
  let release; const calls = [];
  const { ctx, state, changes } = saving((url, body) => { calls.push({ url, body }); return new Promise(r => { release = r; }); });
  const save = ctx.flushSave(); assert.equal(ctx.flushSave(), save);
  const route = ctx.route(); assert.equal(changes.length, 0);
  release({ updated: 'now' }); await route;
  assert.equal(calls[0].url, '/api/papers/paper/notes'); assert.deepEqual(changes, ['opened:site']);
  assert.equal(state.savePromise, null);
});
test('edits made during saving are saved before the material can switch', async () => {
  const pending = []; const payloads = [];
  const { ctx, state } = saving((url, body) => { payloads.push(JSON.parse(JSON.stringify(body.json.sections))); return new Promise(r => pending.push(r)); });
  const task = ctx.flushSave(); state.notes.sections.s1 = 'edited while saving';
  pending.shift()({ updated: 'one' }); await new Promise(setImmediate);
  assert.equal(payloads.length, 2); assert.equal(payloads[0].s1, 'first note'); assert.equal(payloads[1].s1, 'edited while saving');
  pending.shift()({ updated: 'two' }); assert.equal(await task, true);
});
test('a failed note save keeps the current material and unsaved content', async () => {
  const { ctx, state, changes } = saving(async () => { throw new Error('offline'); });
  await ctx.route(); assert.equal(state.slug, 'paper'); assert.equal(state.notes.sections.s1, 'first note');
  assert.equal(state.saveState, '保存失败'); assert.deepEqual(changes, ['#/p/paper']);
});
