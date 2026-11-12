const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../web/static/clipboard.js'), 'utf8');

function browser({ modern, legacy = true, throws = false } = {}) {
  const seen = { text: null, removed: false, focusRestored: false, legacyCalled: false };
  const active = { selectionStart: 1, selectionEnd: 2, selectionDirection: 'forward',
    focus() { seen.focusRestored = true; }, setSelectionRange(...args) { seen.selectionRestored = args; } };
  const field = { style: {}, setAttribute() {}, focus() {}, select() {}, setSelectionRange() {}, remove() { seen.removed = true; } };
  const context = vm.createContext({
    navigator: modern ? { clipboard: { writeText: modern } } : {},
    document: { activeElement: active, body: { appendChild(el) { seen.text = el.value; } },
      createElement() { return field; }, execCommand(command) {
        assert.equal(command, 'copy'); seen.legacyCalled = true;
        if (throws) throw new Error('blocked');
        return legacy;
      } },
  });
  vm.runInContext(code, context);
  return { copy: context.BlingClipboard.copyText, seen };
}

test('copies exact Markdown, Unicode and newlines using modern clipboard', async () => {
  const value = '## 代码\n```py\nprint("测试")\n```';
  let copied;
  const { copy, seen } = browser({ modern: async text => { copied = text; } });
  assert.equal(await copy(value), true); assert.equal(copied, value); assert.equal(seen.legacyCalled, false);
});
test('denied clipboard permission falls back and preserves editor focus and selection', async () => {
  const { copy, seen } = browser({ modern: async () => { throw new Error('NotAllowedError'); } });
  assert.equal(await copy('待复制\ncontent'), true); assert.equal(seen.text, '待复制\ncontent');
  assert.equal(seen.removed, true); assert.equal(seen.focusRestored, true);
  assert.deepEqual(seen.selectionRestored, [1, 2, 'forward']);
});
test('HTTP or embedded browser without Clipboard API uses compatible copy', async () => {
  const { copy, seen } = browser(); assert.equal(await copy('hello'), true); assert.equal(seen.legacyCalled, true);
});
test('blocked compatible copy returns false for manual selection, cleans up and restores focus', async () => {
  for (const options of [{ legacy: false }, { throws: true }]) {
    const { copy, seen } = browser(options); assert.equal(await copy('manual'), false);
    assert.equal(seen.removed, true); assert.equal(seen.focusRestored, true);
  }
});
