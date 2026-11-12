/* Clipboard API can be unavailable on HTTP, in embedded pages, or after a denied permission. */
(function (root) {
  'use strict';
  async function copyText(value) {
    const text = String(value ?? '');
    try {
      if (root.navigator?.clipboard?.writeText) {
        await root.navigator.clipboard.writeText(text);
        return true;
      }
    } catch { /* Try the selection-based browser copy below. */ }
    const doc = root.document;
    if (!doc?.body) return false;
    const active = doc.activeElement;
    const selection = root.getSelection?.();
    const ranges = [];
    for (let i = 0; selection && i < selection.rangeCount; i++) ranges.push(selection.getRangeAt(i).cloneRange());
    const inputSelection = active && typeof active.selectionStart === 'number'
      ? [active.selectionStart, active.selectionEnd, active.selectionDirection] : null;
    const field = doc.createElement('textarea');
    field.value = text;
    field.readOnly = true;
    field.setAttribute('aria-label', '复制内容');
    Object.assign(field.style, { position: 'fixed', top: '0', left: '0', width: '1px', height: '1px', opacity: '0', fontSize: '16px' });
    doc.body.appendChild(field);
    try {
      field.focus({ preventScroll: true });
      field.select();
      field.setSelectionRange(0, text.length);
      return !!doc.execCommand?.('copy');
    } catch {
      return false;
    } finally {
      field.remove();
      active?.focus?.({ preventScroll: true });
      if (inputSelection) active.setSelectionRange?.(...inputSelection);
      if (selection) {
        selection.removeAllRanges();
        ranges.forEach(range => selection.addRange(range));
      }
    }
  }
  root.BlingClipboard = { copyText };
})(globalThis);
