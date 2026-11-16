const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/static/app.js'), 'utf8');
const render = app.slice(app.indexOf('function renderJob(box, j) {'), app.indexOf('function watchJob('));
const esc = app.match(/^const esc = .*;$/m)[0];
function widget() {
  const button = {}; const log = { scrollHeight: 100, scrollTop: 0 }; const copies = [];
  const context = vm.createContext({ $: selector => selector === '#jobLog' ? log : button, copyContent: value => copies.push(value) });
  vm.runInContext(esc + render, context);
  return { render: context.renderJob, button, copies, box: { innerHTML: '' } };
}
test('failed import log has a copy action preserving complete Unicode traceback and line breaks', () => {
  const w = widget();
  const job = { status: 'failed', log: ['下载网络：http://127.0.0.1:7897', '▸ GR00T 2', 'PermissionError: [WinError 32]\n文件被占用'] };
  w.render(w.box, job);
  assert.match(w.box.innerHTML, /复制完整日志/); w.button.onclick();
  assert.equal(w.copies[0], job.log.join('\n'));
});
test('copy follows latest polled log and works while running or completed', () => {
  const w = widget(); const job = { status: 'running', log: ['start'] };
  w.render(w.box, job); job.log.push('latest'); w.render(w.box, job); w.button.onclick();
  assert.equal(w.copies[0], 'start\nlatest');
  job.status = 'done'; w.render(w.box, job); w.button.onclick(); assert.equal(w.copies[1], 'start\nlatest');
});
test('log text stays escaped in the page while copying preserves the original text', () => {
  const w = widget(); const value = '<script>alert("error")</script>';
  w.render(w.box, { status: 'failed', log: [value] });
  assert.doesNotMatch(w.box.innerHTML, /<script>/); w.button.onclick(); assert.equal(w.copies[0], value);
});
