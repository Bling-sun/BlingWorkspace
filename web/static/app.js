/* bling 精读工作台 · 前端（无构建，原生 JS） */
'use strict';

const STATIONS = [
  { id: '0', label: '开场', note: 'basic', prompt: '开始吧：先给基本情况，然后直接讲第 ① 站 动机。' },
  { id: '1', label: '① 动机', note: 's1', prompt: '讲第 ① 站：动机。' },
  { id: '2', label: '② 架构', note: 's2', prompt: '继续，讲第 ② 站：架构。' },
  { id: '3', label: '③ 训练', note: 's3', prompt: '继续，讲第 ③ 站：训练和损失函数。' },
  { id: '4', label: '④ 数据', note: 's4', prompt: '继续，讲第 ④ 站：数据——一条样本到底长什么样。' },
  { id: '5', label: '⑤ 信息流', note: 's5', prompt: '继续，讲第 ⑤ 站：输入输出信息流。' },
  { id: '6', label: '⑥ 例子', note: 's6', prompt: '继续，讲第 ⑥ 站：拿一个具体例子把信息流走一遍，对照代码。' },
  { id: '7', label: '⑦ 实验', note: 's7', prompt: '讲 ⑦：实验结果和这篇现在的地位。' },
  { id: 'free', label: '自由讨论', note: 'qa', prompt: '' },
];
const ST = Object.fromEntries(STATIONS.map(s => [s.id, s]));
const QUICK = [
  ['没懂，换个讲法', '没懂，换一种讲法。'],
  ['举个例子走一遍', '能不能举一个具体例子，带真实数字走一遍？'],
  ['翻译原文', '把这一站对应的原文段落翻译一下，原文和译文对照着放。'],
  ['和 X 的区别', '这个和  有什么区别？', true],
  ['接着说', '接着说。'],
];
const PROVIDERS = {
  claude_cli: '本机 Claude Code（Claude 会员，免 API Key）',
  codex_cli: '本机 Codex（ChatGPT 会员，免 API Key）',
  deepseek: 'DeepSeek（API Key）',
  anthropic: 'Claude API（API Key）',
  openai: '其他 OpenAI 兼容接口（API Key）',
  mock: '演示模式（不调用模型）',
};
const SHORT = { claude_cli: 'Claude Code', codex_cli: 'Codex', deepseek: 'DeepSeek', anthropic: 'Claude API', openai: 'OpenAI 兼容', mock: '演示模式' };
// 每个接口的说明、模型建议、需要哪些输入框
const PINFO = {
  claude_cli: { cli: 'claude', models: ['', 'sonnet', 'opus', 'haiku'], modelHint: '留空用 Claude Code 默认模型；也可以填 sonnet / opus',
    help: `用你电脑上的 <b>Claude Code 命令行</b>，消耗 Claude 会员（Pro / Max）的用量额度，和网页版 Claude 共用，不需要 API Key。<br>
      第一次用：在 PowerShell 里运行 <code>irm https://claude.ai/install.ps1 | iex</code> 安装，然后运行一次 <code>claude</code>，按提示用 Claude 会员账号登录。<br>
      注意：电脑上别设 <code>ANTHROPIC_API_KEY</code> 环境变量（网页端调用时会自动忽略它，确保走会员额度）。` },
  codex_cli: { cli: 'codex', models: [''], modelHint: '留空用 Codex 默认模型',
    help: `用你电脑上的 <b>Codex 命令行</b>，消耗 ChatGPT 会员套餐里的 Codex 额度，不需要 API Key。<br>
      第一次用：装 Node.js 后运行 <code>npm i -g @openai/codex</code>，再运行 <code>codex login</code> 用 ChatGPT 账号登录。VS Code 里装过 Codex 扩展的，会自动找到扩展自带的 codex。<br>
      Codex 命令行看不到图片像素（你用「问 AI」附的图除外），讲图时按图注和正文讲。` },
  deepseek: { key: true, base: true, models: ['deepseek-chat', 'deepseek-reasoner'], baseHint: '默认 https://api.deepseek.com，一般不用改',
    help: `在 <a href="https://platform.deepseek.com/api_keys" target="_blank">platform.deepseek.com</a> 创建 API Key。模型名以 DeepSeek 文档为准，常用 <code>deepseek-chat</code>；
      DeepSeek 不支持看图，讲图时按图注和正文讲。推理模型不支持工具调用时会自动退回只用上下文。` },
  anthropic: { key: true, base: true, models: ['claude-sonnet-4-5', 'claude-opus-4-1'], baseHint: '留空用官方地址；走中转时填中转地址',
    help: '在 console.anthropic.com 创建 API Key，按 API 用量计费（和 Claude 会员是两回事）。' },
  openai: { key: true, base: true, models: [], baseHint: '服务商的 OpenAI 兼容地址，如 https://dashscope.aliyuncs.com/compatible-mode/v1',
    help: '通义、Kimi、智谱、本地 Ollama / vLLM 等都走这里：填服务商给的 Base URL、Key 和模型名。' },
  mock: { help: '不调用任何模型，回复是占位的，用来熟悉界面。' },
};

const S = {
  settings: null, papers: [], root: '', query: '',
  slug: null, paper: null, station: '0', leftTab: 'pdf', mpane: 'center',
  attachments: [], ctrl: null, streamText: '', streamTools: [],
  notes: null, editing: {}, collapsed: {}, drafts: {}, saveTimer: null, saveState: '',
  filePath: 'code', file: null, sel: null, importMode: 'link', job: null,
};

/* ---------------- 小工具 ---------------- */
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem('bling:' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('bling:' + k, JSON.stringify(v)); } catch { /* 无痕模式等 */ } },
};
function toast(msg, ms = 2600) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, ms);
}
async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.json !== undefined) { o.body = JSON.stringify(o.json); o.headers = { 'Content-Type': 'application/json' }; delete o.json; }
  const r = await fetch(path, o);
  let data = null;
  try { data = await r.json(); } catch { /* 非 JSON */ }
  if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
  return data;
}
async function streamPost(url, body, onEvent, signal) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  if (!r.ok) { let e = `${r.status}`; try { e = (await r.json()).error || e; } catch { /* */ } throw new Error(e); }
  const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      const line = chunk.split('\n').find(l => l.startsWith('data: '));
      if (line) { try { onEvent(JSON.parse(line.slice(6))); } catch (e) { console.error(e); } }
    }
  }
}
function fmtTime(ts) {
  if (!ts) return '';
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  const p = n => String(n).padStart(2, '0');
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function authorsLine(m, n = 3) {
  const a = m.authors || [];
  return a.slice(0, n).join('、') + (a.length > n ? ` 等 ${a.length} 人` : '');
}

/* Markdown → 安全 HTML；相对图片路径指到 /files/<slug>/ */
marked.setOptions({ gfm: true, breaks: false });
function md(text, slug = S.slug) {
  const html = DOMPurify.sanitize(marked.parse(text || ''), { ADD_ATTR: ['target'] });
  const t = document.createElement('template'); t.innerHTML = html;
  t.content.querySelectorAll('img').forEach(img => {
    const src = img.getAttribute('src') || '';
    if (slug && !/^(https?:|data:|\/)/.test(src)) img.setAttribute('src', `/files/${encodeURIComponent(slug)}/${src.replace(/^\.\//, '')}`);
    img.setAttribute('loading', 'lazy');
  });
  t.content.querySelectorAll('a[href]').forEach(a => { a.target = '_blank'; a.rel = 'noopener'; });
  return t.innerHTML;
}
function lightbox(src, cap) {
  const lb = $('#lightbox'); $('img', lb).src = src; $('p', lb).textContent = cap || ''; lb.hidden = false;
}
$('#lightbox').addEventListener('click', () => { $('#lightbox').hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#lightbox').hidden = true; closeModal(); } });

function openModal(title, html, onMount) {
  $('#modalTitle').textContent = title; $('#modalBody').innerHTML = html; $('#modal').hidden = false;
  if (onMount) onMount($('#modalBody'));
}
function closeModal() { $('#modal').hidden = true; $('#modalBody').innerHTML = ''; }
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal' || e.target.closest('[data-close]')) closeModal(); });

/* ---------------- 设置 ---------------- */
async function loadSettings() {
  S.settings = await api('/api/settings');
  const c = $('#modelChip'); const mock = S.settings.provider === 'mock';
  c.className = 'chip model-chip' + (mock ? ' mock' : '');
  const p = S.settings.provider;
  c.innerHTML = `<span class="dot"></span>${esc(mock ? '演示模式 · 未配置模型' : SHORT[p] + (S.settings.model ? ' · ' + S.settings.model : ''))}`;
}
$('#settingsBtn').onclick = openSettings;
$('#modelChip').onclick = openSettings;

async function openSettings() {
  const s = await api('/api/settings');
  const prof = await api('/api/profile');
  openModal('设置', `
    <h4 style="margin-top:0">模型接口</h4>
    <label class="field"><span>用哪个模型讲</span><select id="sProvider">${Object.entries(PROVIDERS).map(([k, v]) => `<option value="${k}" ${s.provider === k ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
    <div class="hint" id="pHelp" style="margin:-4px 0 12px;line-height:1.7"></div>
    <div id="pDetect"></div>
    <div class="grid2">
      <label class="field" id="fModel"><span>模型名</span><input id="sModel" list="modelList"><datalist id="modelList"></datalist></label>
      <label class="field" id="fKey"><span id="keyLabel">API Key</span><input id="sKey" type="password" autocomplete="off"></label>
    </div>
    <label class="field" id="fBase"><span>Base URL</span><input id="sBase"></label>
    <label class="field" id="fCli"><span>命令行路径（找不到时才填，如 C:\\Users\\你\\.local\\bin\\claude.exe）</span><input id="sCli"></label>
    <div class="row wrap" style="gap:18px;margin-bottom:6px">
      <label class="check" id="fVision"><input type="checkbox" id="sVision">模型能看图（多模态）</label>
      <label class="check" id="fTools"><input type="checkbox" id="sTools" ${s.use_tools ? 'checked' : ''}>让模型自己读代码 / 原文（工具调用）</label>
    </div>
    <div class="row" style="margin:10px 0 4px"><button class="btn sm" id="sTest">保存并测试连接</button><span class="small" id="testOut"></span></div>
    <p class="hint" style="margin-top:8px">每个接口的 Key / 模型分开保存，切换接口不会丢。Key 只存在本机 <code>web/config.json</code>（已加入 .gitignore，不会上传）。</p>
    <details><summary class="muted small">高级</summary><div class="grid2" style="margin-top:10px">
      <label class="field"><span>单次回复最多 token</span><input id="sMax" type="number" value="${esc(s.max_tokens)}"></label>
      <label class="field"><span>放进上下文的正文最多字数</span><input id="sChars" type="number" value="${esc(s.max_paper_chars)}"></label></div></details>
    <h4>论文库</h4>
    <label class="field"><span>论文目录（每篇论文一个子目录）</span><input id="sRoot" value="${esc(s.papers_root)}"></label>
    <h4>用户画像 profile.md <span class="muted small">（讲解时按它调整：熟的一句带过、不熟的先铺垫、⑥ 用什么场景举例）</span></h4>
    <textarea id="sProfile" rows="8" placeholder="还没有 profile.md，可以从模板开始">${esc(prof.text)}</textarea>
    <div class="row" style="margin-top:8px">${prof.text ? '' : '<button class="btn sm" id="sTpl">从模板开始</button>'}<span class="grow"></span>
      <button class="btn" data-close>取消</button><button class="btn primary" id="sSave">保存</button></div>`, body => {
    const show = (id, on) => { $(id, body).style.display = on ? '' : 'none'; };
    const fill = () => {
      const k = $('#sProvider').value; const info = PINFO[k] || {}; const p = s.profiles[k] || {};
      $('#pHelp').innerHTML = info.help || '';
      show('#fKey', info.key); show('#fBase', info.base); show('#fModel', k !== 'mock'); show('#fCli', !!info.cli);
      show('#fVision', k === 'anthropic' || k === 'openai'); show('#fTools', !!info.key);
      $('#sModel').value = p.model || ''; $('#sModel').placeholder = info.modelHint || '模型名';
      $('#modelList').innerHTML = (info.models || []).filter(Boolean).map(m => `<option value="${esc(m)}">`).join('');
      $('#sKey').value = ''; $('#sKey').placeholder = p.api_key_masked ? '已保存，留空则不改' : '粘贴 API Key';
      $('#keyLabel').innerHTML = 'API Key' + (p.api_key_masked ? ` <span class="muted">（当前：${esc(p.api_key_masked)}）</span>` : '');
      $('#sBase').value = p.base_url || ''; $('#sBase').placeholder = info.baseHint || '';
      $('#sCli').value = p.cli_path || '';
      $('#sVision').checked = !!p.vision;
      const det = $('#pDetect');
      if (info.cli) {
        const path = s.detected[k];
        det.innerHTML = path ? `<p class="small" style="color:var(--ok);margin:0 0 10px">✓ 找到了 ${esc(info.cli)}：<code>${esc(path)}</code>（登录状态点「保存并测试连接」确认）</p>`
          : `<p class="small" style="color:var(--warn);margin:0 0 10px">还没找到 ${esc(info.cli)} 命令：按上面的说明安装并登录，或者在下面填它的路径。</p>`;
      } else det.innerHTML = '';
      $('#testOut').textContent = '';
    };
    $('#sProvider').onchange = fill; fill();
    const tpl = $('#sTpl', body); if (tpl) tpl.onclick = () => { $('#sProfile').value = prof.example; tpl.remove(); };
    const save = async () => {
      const r = await api('/api/settings', { method: 'POST', json: {
        provider: $('#sProvider').value, max_tokens: $('#sMax').value, max_paper_chars: $('#sChars').value,
        use_tools: $('#sTools').checked, papers_root: $('#sRoot').value.trim(),
        profile: { model: $('#sModel').value.trim(), api_key: $('#sKey').value.trim(), base_url: $('#sBase').value.trim(),
          cli_path: $('#sCli').value.trim(), vision: $('#sVision').checked },
      } });
      Object.assign(s, r);
      if ($('#sProfile').value !== prof.text) { await api('/api/profile', { method: 'POST', json: { text: $('#sProfile').value } }); prof.text = $('#sProfile').value; }
      await loadSettings();
    };
    $('#sTest', body).onclick = async () => {
      const out = $('#testOut'); out.style.color = ''; out.innerHTML = '<span class="spinner" style="display:inline-block;vertical-align:middle"></span> 测试中（命令行第一次可能要十几秒）…';
      try {
        await save(); fill();
        const r = await api('/api/settings/test', { method: 'POST' });
        out.style.color = r.ok ? 'var(--ok)' : 'var(--err)';
        out.textContent = r.ok ? `✓ 连接成功：${r.text.replace(/\s+/g, ' ').slice(0, 40)}` : `✗ ${r.error || '没有返回内容'}`;
      } catch (e) { out.style.color = 'var(--err)'; out.textContent = '✗ ' + e.message; }
    };
    $('#sSave', body).onclick = async () => {
      try { await save(); closeModal(); toast('设置已保存'); route(); } catch (e) { toast('保存失败：' + e.message); }
    };
  });
}

/* ---------------- 路由 ---------------- */
function route() {
  const m = location.hash.match(/^#\/p\/(.+)$/);
  if (S.ctrl) { S.ctrl.abort(); S.ctrl = null; }
  if (m) openPaper(decodeURIComponent(m[1])); else showLibrary();
}
window.addEventListener('hashchange', route);

/* ================= 文献库 ================= */
async function showLibrary() {
  S.slug = null; S.paper = null;
  $('#crumbs').innerHTML = '文献库';
  document.title = 'bling 精读工作台';
  const app = $('#app');
  app.innerHTML = `<div class="library"><div class="lib-inner">
    <div class="lib-title"><div><h1>文献库</h1><div class="muted small" id="rootLine"></div></div></div>
    <section class="importer" id="importer"></section>
    <div class="lib-tools"><input id="q" placeholder="搜索标题、作者、arXiv ID" value="${esc(S.query)}"><span class="muted small" id="count"></span></div>
    <div id="cards"></div></div></div>`;
  renderImporter();
  $('#q').oninput = e => { S.query = e.target.value; renderCards(); };
  try {
    const r = await api('/api/papers'); S.papers = r.papers; S.root = r.root;
    $('#rootLine').textContent = '论文目录：' + r.root;
  } catch (e) { toast('读取论文库失败：' + e.message); }
  renderCards();
}

function renderImporter() {
  const el = $('#importer'); if (!el) return;
  const mode = S.importMode;
  const main = {
    link: `<input type="text" id="impTarget" placeholder="arXiv 链接或 ID（如 2410.24164）、alphaxiv / HF Papers 链接、PDF 直链">`,
    pdf: `<label class="dropzone" id="drop"><input type="file" id="impFile" accept="application/pdf" hidden><span id="dropText">把 PDF 拖到这里，或点击选择文件</span></label>`,
    dir: `<input type="text" id="impTarget" placeholder="本机上已有的论文目录（完整路径），只补缺的材料">`,
  }[mode];
  el.innerHTML = `<h2>导入论文</h2>
    <p class="lead">调用 <code>scripts/fetch_paper.py</code>：拉 PDF、LaTeX 源码、每张图裁好的 PNG、大纲和官方代码（5–30 秒）。</p>
    <div class="seg">${[['link', 'arXiv / 链接'], ['pdf', '上传 PDF'], ['dir', '已有目录']].map(([k, v]) => `<button data-mode="${k}" class="${k === mode ? 'on' : ''}">${v}</button>`).join('')}</div>
    <div class="imp-main">${main}<button class="btn primary" id="impGo">导入</button></div>
    <div class="imp-more">
      <input id="impCode" placeholder="官方代码仓库（可选：论文里没写、自己搜到的时候填）">
      <input id="impSlug" placeholder="目录名（可选）">
      <label class="check"><input type="checkbox" id="impNoClone">只找代码链接，不克隆</label>
    </div>
    <div id="jobBox"></div>`;
  $$('.seg button', el).forEach(b => b.onclick = () => { S.importMode = b.dataset.mode; renderImporter(); });
  const drop = $('#drop', el);
  if (drop) {
    const f = $('#impFile', el);
    f.onchange = () => { $('#dropText').textContent = f.files[0] ? `已选：${f.files[0].name}` : '把 PDF 拖到这里，或点击选择文件'; };
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) { f.files = e.dataTransfer.files; f.onchange(); } };
  }
  const t = $('#impTarget', el); if (t) t.onkeydown = e => { if (e.key === 'Enter') doImport(); };
  $('#impGo', el).onclick = doImport;
  if (S.job) renderJob($('#jobBox', el), S.job);
}

async function doImport() {
  const fd = new FormData();
  if (S.importMode === 'pdf') {
    const f = $('#impFile').files[0]; if (!f) return toast('先选一个 PDF');
    fd.append('pdf', f);
  } else {
    const t = $('#impTarget').value.trim(); if (!t) return toast('先填链接 / ID / 路径');
    fd.append('target', t);
  }
  fd.append('code', $('#impCode').value.trim());
  fd.append('slug', $('#impSlug').value.trim());
  if ($('#impNoClone').checked) fd.append('no_clone', '1');
  $('#impGo').disabled = true;
  try {
    const job = await api('/api/import', { method: 'POST', body: fd });
    watchJob(job, () => $('#jobBox'), async j => {
      if (j.status === 'done') {
        const r = await api('/api/papers'); S.papers = r.papers; renderCards();
        toast('导入完成');
      }
    });
  } catch (e) { toast('导入失败：' + e.message); }
  finally { const b = $('#impGo'); if (b) b.disabled = false; }
}

function renderJob(box, j) {
  if (!box) return;
  const status = { running: '<span class="spinner"></span>正在处理…', done: '✓ 完成', failed: '✗ 失败（看上面的日志）' }[j.status];
  box.innerHTML = `<div class="joblog" id="jobLog">${esc(j.log.join('\n')) || '启动中…'}</div>
    <div class="jobbar"><span class="row">${status}</span><span class="grow"></span>
    ${j.status === 'done' && j.slug ? `<a class="btn primary" href="#/p/${encodeURIComponent(j.slug)}">开始精读 →</a>` : ''}</div>`;
  const lg = $('#jobLog', box); lg.scrollTop = lg.scrollHeight;
}

function watchJob(job, boxFn, onEnd) {
  const j = { ...job, log: [] }; S.job = j;
  const tick = async () => {
    try {
      const r = await api(`/api/jobs/${job.id}?since=${j.log.length}`);
      j.log.push(...r.log); j.status = r.status; j.slug = r.slug; j.dest = r.dest;
      renderJob(boxFn(), j);
      if (r.status === 'running') setTimeout(tick, 700); else if (onEnd) onEnd(j);
    } catch (e) { j.status = 'failed'; j.log.push(String(e)); renderJob(boxFn(), j); }
  };
  renderJob(boxFn(), j); tick();
}

function stationDots(p) {
  const talked = new Set(p.talked || []); if (talked.has('0')) talked.add('1');
  const noted = new Set(p.noted || []);
  return STATIONS.slice(1, 8).map(s => `<span class="st-dot ${noted.has(s.note) ? 'noted' : talked.has(s.id) ? 'talked' : ''}" title="${s.label}">${s.label[0]}</span>`).join('');
}

function renderCards() {
  const box = $('#cards'); if (!box) return;
  const q = S.query.trim().toLowerCase();
  const list = S.papers.filter(p => !q || [p.title, p.arxiv_id, ...(p.authors || [])].join(' ').toLowerCase().includes(q));
  $('#count').textContent = `${list.length} 篇`;
  if (!S.papers.length) {
    box.innerHTML = `<div class="empty-lib"><h3>还没有论文</h3><p>在上面贴一个 arXiv 链接试试，比如 <code>https://arxiv.org/abs/2410.24164</code>（π0）。</p></div>`;
    return;
  }
  box.className = 'cards';
  box.innerHTML = list.map(p => `<article class="card" data-slug="${esc(p.slug)}">
      <h3>${esc(p.title)}</h3>
      <div class="muted small">${esc(authorsLine(p))}${p.published ? ' · ' + esc(p.published.slice(0, 10)) : ''}</div>
      ${p.summary ? `<p class="abs">${esc(p.summary)}</p>` : ''}
      <div class="row wrap">${p.arxiv_id ? `<span class="chip">arXiv ${esc(p.arxiv_id)}</span>` : ''}
        <span class="chip">图表 ${p.figures}</span>${p.has_latex ? '<span class="chip">LaTeX</span>' : ''}${p.code ? '<span class="chip">有代码</span>' : ''}</div>
      <div class="row"><div class="stations">${stationDots(p.progress)}</div><span class="grow"></span><span class="muted small">${p.progress.messages ? `${p.progress.messages} 条讨论 · ` : ''}${fmtTime(p.mtime)}</span></div>
    </article>`).join('');
  $$('.card', box).forEach(c => c.onclick = () => { location.hash = '#/p/' + encodeURIComponent(c.dataset.slug); });
}

/* ================= 工作台 ================= */
async function openPaper(slug) {
  const app = $('#app');
  if (S.slug !== slug) {
    Object.assign(S, { slug, attachments: [], editing: {}, drafts: {}, filePath: 'code', file: null, sel: null, leftTab: store.get('leftTab', 'pdf') });
  }
  app.innerHTML = '<div class="welcome"><span class="spinner"></span></div>';
  try { S.paper = await api('/api/papers/' + encodeURIComponent(slug)); }
  catch (e) { app.innerHTML = `<div class="welcome"><h3>打不开这篇</h3><p>${esc(e.message)}</p><a class="btn" href="#/">回文献库</a></div>`; return; }
  const P = S.paper; S.notes = P.notes;
  if (!P.meta.code_dir && !P.code_root) S.filePath = '';
  const talked = talkedSet();
  S.station = store.get('station:' + slug, null) || STATIONS.find(s => s.id !== 'free' && !talked.has(s.id))?.id || 'free';
  document.title = (P.meta.title || slug) + ' · 精读';
  $('#crumbs').innerHTML = `<a href="#/">文献库</a> / ${esc(P.meta.title || slug)}`;
  const m = P.meta;
  app.innerHTML = `<div class="ws">
    <div class="ws-head">
      <a class="btn ghost sm" href="#/" title="回文献库">←</a>
      <div class="grow"><h2>${esc(m.title || slug)}</h2>
        <div class="sub">${[esc(authorsLine(m, 4)), m.published ? esc(m.published.slice(0, 10)) : '', m.arxiv_id ? `<a href="https://arxiv.org/abs/${esc(m.arxiv_id)}" target="_blank">arXiv ${esc(m.arxiv_id)}</a>` : '', m.official_code ? `<a href="${esc(m.official_code)}" target="_blank">代码</a>` : ''].filter(Boolean).join(' · ')}</div></div>
      <button class="btn sm hide-m" data-act="preview">预览笔记</button>
      <button class="btn sm primary" data-act="export">导出 HTML</button>
    </div>
    <div class="panes" id="panes" style="--c1:${store.get('c1', '38%')};--c3:${store.get('c3', '30%')}">
      <section class="pane left" id="paneLeft"></section>
      <div class="split" data-split="c1"></div>
      <section class="pane center" id="paneCenter"></section>
      <div class="split" data-split="c3"></div>
      <section class="pane right" id="paneRight"></section>
    </div>
    <nav class="mtabs">${[['left', '材料'], ['center', '讨论'], ['right', '笔记']].map(([k, v]) => `<button data-m="${k}">${v}</button>`).join('')}</nav>
  </div>`;
  $$('.ws-head [data-act]').forEach(b => b.onclick = () => headAction(b.dataset.act));
  $$('.mtabs button').forEach(b => b.onclick = () => showMobile(b.dataset.m));
  showMobile(S.mpane);
  initSplits();
  renderLeft(); renderCenter(); renderNotes();
}

function showMobile(k) {
  S.mpane = k;
  ['left', 'center', 'right'].forEach(n => { const el = $('#pane' + n[0].toUpperCase() + n.slice(1)); if (el) el.classList.toggle('mshow', n === k); });
  $$('.mtabs button').forEach(b => b.classList.toggle('on', b.dataset.m === k));
}

function initSplits() {
  const panes = $('#panes');
  $$('.split', panes).forEach(sp => {
    sp.onmousedown = e => {
      e.preventDefault(); sp.classList.add('drag');
      const rect = panes.getBoundingClientRect(); const key = sp.dataset.split;
      $$('iframe').forEach(f => f.style.pointerEvents = 'none');
      const move = ev => {
        let pct = key === 'c1' ? (ev.clientX - rect.left) / rect.width * 100 : (rect.right - ev.clientX) / rect.width * 100;
        pct = Math.max(18, Math.min(60, pct));
        panes.style.setProperty('--' + key, pct.toFixed(1) + '%');
      };
      const up = () => {
        sp.classList.remove('drag'); document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
        $$('iframe').forEach(f => f.style.pointerEvents = '');
        store.set(key, panes.style.getPropertyValue('--' + key));
      };
      document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
    };
  });
}

async function headAction(act) {
  const slug = encodeURIComponent(S.slug);
  if (act === 'preview') { await flushSave(); window.open(`/api/papers/${slug}/notes/view`, '_blank'); }
  if (act === 'export') {
    await flushSave();
    openModal('导出精读笔记（HTML）', `
      <p style="margin-top:0">导出成一个<strong>单文件 HTML</strong>：图片都内嵌在文件里，发给别人、换台电脑直接用浏览器打开；浏览器里「打印 → 另存为 PDF」也能得到排好版的 PDF。</p>
      <p class="muted small">论文目录里一直有一份随时更新的 <code>精读笔记.html</code>（图用相对路径，和 figures/ 放在一起时打开）。</p>
      <label class="check" style="margin:12px 0 6px"><input type="checkbox" id="exT">附上完整讨论记录（折叠在文末）</label>
      <label class="check"><input type="checkbox" id="exS" checked>同时在论文目录保存一份 <code>精读笔记-导出.html</code></label>
      <div class="row" style="margin-top:16px"><span class="grow"></span><button class="btn" data-act="exView">先预览</button><button class="btn primary" data-act="exGo">下载 HTML</button></div>`, body => {
      $('[data-act=exView]', body).onclick = () => window.open(`/api/papers/${slug}/notes/view`, '_blank');
      $('[data-act=exGo]', body).onclick = () => {
        const q = `transcript=${$('#exT').checked ? 1 : 0}&save=${$('#exS').checked ? 1 : 0}`;
        const a = document.createElement('a'); a.href = `/api/papers/${slug}/export?${q}`; a.click();
        closeModal(); toast('已导出');
      };
    });
  }
}

/* ---------------- 左栏：材料 ---------------- */
const LEFT_TABS = [['pdf', 'PDF'], ['figs', '图表'], ['outline', '大纲'], ['files', '代码 / 文件'], ['info', '信息']];
function renderLeft() {
  const el = $('#paneLeft'); if (!el) return; const P = S.paper;
  const n = (P.figures || []).filter(f => f.file).length;
  el.innerHTML = `<div class="pane-tabs">${LEFT_TABS.map(([k, v]) => `<button data-tab="${k}" class="${S.leftTab === k ? 'on' : ''}">${v}${k === 'figs' ? ` <span class="muted small">${n}</span>` : ''}</button>`).join('')}</div>
    <div class="pane-body" id="leftBody">
      <iframe class="pdf-frame" id="pdfFrame" ${P.has_pdf ? `src="/files/${encodeURIComponent(S.slug)}/paper.pdf#view=FitH"` : ''} ${S.leftTab === 'pdf' ? '' : 'hidden'} title="PDF"></iframe>
      <div id="leftOther" ${S.leftTab === 'pdf' ? 'hidden' : ''}></div>
    </div>`;
  $$('.pane-tabs button', el).forEach(b => b.onclick = () => { S.leftTab = b.dataset.tab; store.set('leftTab', S.leftTab); switchLeft(); });
  switchLeft();
}
function switchLeft() {
  $$('#paneLeft .pane-tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.leftTab));
  const pdf = S.leftTab === 'pdf';
  $('#pdfFrame').hidden = !pdf; const o = $('#leftOther'); o.hidden = pdf;
  if (pdf) { if (!S.paper.has_pdf) { $('#pdfFrame').hidden = true; o.hidden = false; o.innerHTML = '<div class="pad muted">没有 paper.pdf</div>'; } return; }
  ({ figs: renderFigs, outline: renderOutline, files: renderFiles, info: renderInfo })[S.leftTab](o);
}
function pdfPage(page) {
  S.leftTab = 'pdf'; switchLeft(); showMobile('left');
  const f = $('#pdfFrame'); f.src = `/files/${encodeURIComponent(S.slug)}/paper.pdf#page=${page}&view=FitH`;
}

function figLabel(f) { return (f.kind === 'table' ? '表 ' : '图 ') + f.num; }
function renderFigs(o) {
  const figs = S.paper.figures || [];
  if (!figs.length) { o.innerHTML = `<div class="pad muted">没有裁出图表。<button class="btn sm" data-act="refig">重新裁图</button></div>`; bindRefig(o); return; }
  const fileUrl = f => `/files/${encodeURIComponent(S.slug)}/${f.file}`;
  o.innerHTML = `<div class="row pad" style="padding-bottom:0"><span class="muted small grow">点图放大；「问 AI」把图附到下一条提问，「进笔记」插进当前站的笔记。</span>
      <button class="btn sm" data-act="contact">总览拼图</button><button class="btn sm" data-act="refig">重新裁图</button></div>
    <div class="figs">${figs.map((f, i) => `<div class="fig">
      <div class="thumb" data-i="${i}">${f.file ? `<img src="${fileUrl(f)}" loading="lazy" alt="${esc(figLabel(f))}">` : '<span class="muted small">未裁出</span>'}</div>
      <div class="info"><div class="row"><strong>${esc(figLabel(f))}</strong><span class="muted small">第 ${f.page} 页</span>${f.mode && f.mode !== '裁剪' ? `<span class="tag warn">${esc(f.mode)}</span>` : ''}</div>
        <p class="cap" title="${esc(f.caption)}">${esc(f.caption)}</p>
        <div class="acts">${f.file ? `<button class="btn sm" data-fa="ask" data-i="${i}">问 AI</button><button class="btn sm" data-fa="note" data-i="${i}">进笔记</button>` : ''}<button class="btn sm ghost" data-fa="pdf" data-i="${i}">PDF 第 ${f.page} 页</button></div></div></div>`).join('')}</div>`;
  $$('.thumb', o).forEach(t => t.onclick = () => { const f = figs[t.dataset.i]; if (f.file) lightbox(fileUrl(f), `${figLabel(f)} · ${f.caption}`); });
  $$('[data-fa]', o).forEach(b => b.onclick = () => {
    const f = figs[b.dataset.i];
    if (b.dataset.fa === 'pdf') return pdfPage(f.page);
    if (b.dataset.fa === 'ask') { addAttachment({ type: 'image', path: f.file, label: figLabel(f) }); showMobile('center'); toast(`${figLabel(f)} 已附到提问`); }
    if (b.dataset.fa === 'note') {
      const key = ST[S.station].note; const cap = (f.caption || '').replace(/\s+/g, ' ').slice(0, 60);
      appendToSection(key, `![${figLabel(f)} · ${cap}](${f.file})`);
      toast(`${figLabel(f)} 已插进笔记「${sectionTitle(key)}」`);
    }
  });
  $('[data-act=contact]', o).onclick = () => lightbox(`/files/${encodeURIComponent(S.slug)}/${S.paper.fig_dir}/_contact.png`, '所有裁剪的总览');
  bindRefig(o);
}
function bindRefig(o) {
  const b = $('[data-act=refig]', o); if (!b) return;
  b.onclick = async () => {
    const job = await api(`/api/papers/${encodeURIComponent(S.slug)}/refigures`, { method: 'POST' });
    openModal('重新裁图', '<div id="mjob"></div>');
    watchJob(job, () => $('#mjob'), async j => { if (j.status === 'done') { const p = await api('/api/papers/' + encodeURIComponent(S.slug)); S.paper.figures = p.figures; S.paper.fig_dir = p.fig_dir; renderLeft(); } });
  };
}

function renderOutline(o) {
  o.innerHTML = `<div class="pad md">${S.paper.outline ? md(S.paper.outline) : '<p class="muted">没有 outline.md</p>'}</div>`;
}

async function renderFiles(o) {
  const slug = encodeURIComponent(S.slug);
  if (S.file) return renderFileView(o);
  const roots = [['code', '代码'], ['', '论文目录']];
  o.innerHTML = `<div class="code-nav">${roots.map(([p, l]) => `<button class="btn sm ${S.filePath === p || (p && S.filePath.startsWith(p + '/')) ? 'primary' : ''}" data-root="${p}">${l}</button>`).join('')}
      <span class="muted small grow" id="crumb"></span></div><ul class="tree" id="tree"><li class="muted">读取中…</li></ul>`;
  $$('[data-root]', o).forEach(b => b.onclick = () => { S.filePath = b.dataset.root; renderFiles(o); });
  let r;
  try { r = await api(`/api/papers/${slug}/tree?path=${encodeURIComponent(S.filePath)}`); } catch (e) { r = { error: e.message, items: [] }; }
  if (r.error) {
    $('#tree', o).innerHTML = `<li class="muted" style="cursor:default;display:block">${esc(r.error)}${S.filePath.startsWith('code') ? '<br><br>论文里没找到官方代码时，可以自己搜到仓库地址补上：<div class="row" style="margin-top:8px"><input id="codeUrl" placeholder="https://github.com/…"><button class="btn sm primary" id="codeGo">克隆</button></div>' : ''}</li>`;
    const go = $('#codeGo', o);
    if (go) go.onclick = async () => {
      const url = $('#codeUrl').value.trim(); if (!url) return;
      const job = await api(`/api/papers/${slug}/code`, { method: 'POST', json: { url } });
      openModal('补官方代码', '<div id="mjob"></div>');
      watchJob(job, () => $('#mjob'), async j => { if (j.status === 'done') { S.paper = await api('/api/papers/' + slug); renderFiles(o); } });
    };
    return;
  }
  $('#crumb', o).textContent = r.path || '论文目录';
  const parent = S.filePath.includes('/') ? S.filePath.slice(0, S.filePath.lastIndexOf('/')) : (S.filePath ? null : null);
  const items = (S.filePath && S.filePath !== 'code' ? [{ name: '..', path: parent ?? '', dir: true, up: true }] : []).concat(r.items);
  $('#tree', o).innerHTML = items.map((it, i) => `<li data-i="${i}"><span class="ic">${it.up ? '↑' : it.dir ? '▸' : '·'}</span><span class="grow">${esc(it.name)}</span>${it.size != null ? `<span class="muted small">${it.size > 1024 ? (it.size / 1024).toFixed(0) + ' KB' : it.size + ' B'}</span>` : ''}</li>`).join('') || '<li class="muted">空目录</li>';
  $$('#tree li[data-i]', o).forEach(li => li.onclick = () => {
    const it = items[li.dataset.i];
    if (it.dir) { S.filePath = it.path; renderFiles(o); }
    else if (/\.(png|jpe?g|gif|svg|webp)$/i.test(it.name)) lightbox(`/files/${slug}/${it.path}`, it.path);
    else if (/\.pdf$/i.test(it.name)) window.open(`/files/${slug}/${it.path}`, '_blank');
    else openFile(it.path, o);
  });
}
async function openFile(path, o) {
  try {
    const r = await api(`/api/papers/${encodeURIComponent(S.slug)}/text?path=${encodeURIComponent(path)}`);
    S.file = r; S.sel = null; renderFileView(o);
  } catch (e) { toast('打不开：' + e.message); }
}
function renderFileView(o) {
  const lines = S.file.text.split('\n');
  o.innerHTML = `<div class="code-bar"><button class="btn sm" data-act="back">← 返回</button><strong class="grow" style="word-break:break-all">${esc(S.file.path)}</strong>
      <span class="muted" id="selInfo">点行号选起点，Shift+点选终点</span>
      <button class="btn sm primary" data-act="attach">附到提问</button></div>
    <pre class="codeview">${lines.map((l, i) => `<span class="l" data-n="${i + 1}"><span class="n">${i + 1}</span>${esc(l)}</span>`).join('')}</pre>`;
  const upd = () => {
    const [a, b] = S.sel ? [Math.min(S.sel.a, S.sel.b), Math.max(S.sel.a, S.sel.b)] : [0, -1];
    $$('.codeview .l', o).forEach(l => { const n = +l.dataset.n; l.classList.toggle('sel', n >= a && n <= b); });
    $('#selInfo', o).textContent = S.sel ? `已选 L${a}–${b}（${b - a + 1} 行）` : `共 ${lines.length} 行 · 点行号选起点，Shift+点选终点`;
  };
  $$('.codeview .n', o).forEach(n => n.onclick = e => {
    const k = +n.parentElement.dataset.n;
    S.sel = e.shiftKey && S.sel ? { a: S.sel.a, b: k } : { a: k, b: k }; upd();
  });
  $('[data-act=back]', o).onclick = () => { S.file = null; renderFiles(o); };
  $('[data-act=attach]', o).onclick = () => {
    let a = 1, b = lines.length;
    if (S.sel) { a = Math.min(S.sel.a, S.sel.b); b = Math.max(S.sel.a, S.sel.b); }
    if (b - a > 400) { b = a + 399; toast('一次最多附 400 行，已截到 L' + a + '–' + b); }
    addAttachment({ type: 'code', path: S.file.path, start: a, end: b, text: lines.slice(a - 1, b).join('\n'), label: `${S.file.path.split('/').pop()}:${a}–${b}` });
    showMobile('center');
  };
  upd();
}

function renderInfo(o) {
  const m = S.paper.meta; const links = m.links || {};
  const linkList = Object.entries(links).flatMap(([k, v]) => Array.isArray(v) ? v.slice(0, 4).map(x => [k, x.url]) : []);
  o.innerHTML = `<div class="pad">
    <h3 style="margin-top:0">${esc(m.title)}</h3>
    <p class="muted small">${esc((m.authors || []).join('、'))}</p>
    <div class="row wrap" style="margin:8px 0 14px">${m.published ? `<span class="chip">${esc(m.published.slice(0, 10))}</span>` : ''}${m.arxiv_id ? `<span class="chip">arXiv ${esc(m.arxiv_id)}</span>` : ''}${m.pdf_pages ? `<span class="chip">${m.pdf_pages} 页</span>` : ''}<span class="chip">${m.has_latex ? '有 LaTeX 源码' : '无 LaTeX 源码'}</span>${m.fetched ? `<span class="chip">拉取于 ${esc(m.fetched)}</span>` : ''}</div>
    ${m.summary ? `<h4>摘要</h4><p style="text-align:justify">${esc(m.summary)}</p>` : ''}
    ${m.comment || m.journal_ref ? `<p class="muted small">${esc([m.journal_ref, m.comment].filter(Boolean).join(' · '))}</p>` : ''}
    <h4>代码</h4><p>${m.official_code ? `<a href="${esc(m.official_code)}" target="_blank">${esc(m.official_code)}</a> <span class="muted small">（来自${esc(m.official_code_from || '')}）</span><br><span class="muted small">本地：${esc(S.paper.code_root || '没克隆')}</span>` : '<span class="muted">没找到官方代码，可以在「代码 / 文件」里补。</span>'}</p>
    ${linkList.length ? `<h4>链接</h4><ul>${linkList.map(([k, u]) => `<li><span class="tag">${esc(k)}</span> <a href="${esc(u)}" target="_blank">${esc(u)}</a></li>`).join('')}</ul>` : ''}
    <h4>材料目录</h4><p><code style="word-break:break-all">${esc(S.paper.path)}</code></p></div>`;
}

/* ---------------- 中栏：分析讨论 ---------------- */
function talkedSet() {
  const t = new Set((S.paper?.messages || []).filter(m => m.role === 'assistant').map(m => String(m.station)));
  if (t.has('0')) t.add('1');
  return t;
}
function nextStation() {
  const t = talkedSet();
  return STATIONS.find(s => s.id !== 'free' && s.id !== '0' && !t.has(s.id) && s.id !== S.station) || null;
}
function setStation(id, scroll = true) {
  S.station = id; store.set('station:' + S.slug, id);
  renderStbar(); renderNext();
  if (scroll) { const first = $(`.msg[data-st="${id}"]`); if (first) first.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  $$('.nsec').forEach(n => n.classList.toggle('focus', n.dataset.key === ST[id].note));
}

function renderCenter() {
  const el = $('#paneCenter');
  el.innerHTML = `<div class="stbar" id="stbar"></div><div class="msgs" id="msgs"></div>
    <div class="composer"><div class="next-row" id="nextRow"></div>
      <div class="inbox"><div class="att" id="attBox"></div>
        <textarea id="input" rows="2" placeholder="问任何问题，或复述你的理解让它判对错…  （Enter 发送，Shift+Enter 换行）"></textarea>
        <div class="bar"><div class="quick">${QUICK.map(([l], i) => `<button class="chip" data-q="${i}">${l}</button>`).join('')}</div><span class="grow"></span>
          <button class="btn primary" id="sendBtn">发送</button></div></div></div>`;
  renderStbar(); renderMsgs(); renderNext(); renderAtt();
  const input = $('#input');
  input.oninput = () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 220) + 'px'; };
  input.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } };
  $('#sendBtn').onclick = () => S.ctrl ? stop() : send();
  $$('[data-q]', el).forEach(b => b.onclick = () => {
    const [, text, fill] = QUICK[b.dataset.q];
    if (fill) { input.value = text; input.focus(); input.setSelectionRange(5, 5); } else send(text);
  });
}
function renderStbar() {
  const t = talkedSet();
  $('#stbar').innerHTML = STATIONS.map(s => `<button class="stbtn ${t.has(s.id) ? 'talked' : ''} ${S.station === s.id ? 'on' : ''}" data-st="${s.id}">${s.label}</button>`).join('');
  $$('#stbar .stbtn').forEach(b => b.onclick = () => setStation(b.dataset.st));
}
function renderNext() {
  const box = $('#nextRow'); if (!box) return;
  const t = talkedSet(); const cur = ST[S.station]; const nx = nextStation();
  let html = '';
  if (cur.id !== 'free' && !t.has(cur.id)) html += `<button class="btn primary sm" data-go="${cur.id}">▶ ${cur.id === '0' ? '开始：基本情况 + ① 动机' : '开讲 ' + cur.label}</button>`;
  else if (nx) html += `<button class="btn sm" data-go="${nx.id}">下一站：${nx.label} →</button>`;
  if (cur.id !== 'free' && t.has(cur.id)) html += `<button class="btn sm" data-note="${cur.note}">✎ 把「${cur.label}」整理进笔记</button>`;
  html += `<span class="grow"></span><span class="muted small">当前：${cur.label}</span>`;
  box.innerHTML = html;
  $$('[data-go]', box).forEach(b => b.onclick = () => { const s = ST[b.dataset.go]; setStation(s.id, false); send(s.prompt, 'station'); });
  $$('[data-note]', box).forEach(b => b.onclick = () => { draftSection(b.dataset.note); showMobile('right'); });
}

function msgHtml(m, i, n) {
  const last = i === n - 1;
  const st = ST[m.station]?.label || '';
  const att = m.role === 'user' && ((m.images || []).length || (m.attachments || []).length)
    ? `<div class="att">${(m.images || []).map(p => `<img src="/files/${encodeURIComponent(S.slug)}/${esc(p)}" alt="" data-zoom>`).join('')}${(m.attachments || []).map(a => `<span class="chip">⌗ ${esc(a.path)}:${a.start}–${a.end}</span>`).join('')}</div>` : '';
  const tools = (m.tools || []).length ? `<details class="tools"><summary>查阅了 ${m.tools.length} 处原文 / 代码 / 图</summary><ul>${m.tools.map(t => `<li>${esc(t)}</li>`).join('')}</ul></details>` : '';
  const body = m.role === 'user' ? `<div class="bubble">${esc(m.content)}${att}</div>`
    : `<div class="bubble">${tools}<div class="md">${md(m.content)}</div>${m.error ? `<div class="err">出错了：${esc(m.error)}</div>` : ''}</div>`;
  const acts = m.role === 'user'
    ? `<button class="icon-btn" data-ma="del" title="删除">删除</button>`
    : `<button class="icon-btn" data-ma="copy">复制</button><button class="icon-btn" data-ma="qa" title="把这组问答压成一条记进笔记「问答」">记入问答</button>${last ? '<button class="icon-btn" data-ma="regen">重新生成</button>' : ''}<button class="icon-btn" data-ma="del">删除</button>`;
  return `<div class="msg ${m.role} ${last ? 'last' : ''}" data-id="${esc(m.id)}" data-st="${esc(m.station)}">
    <div class="mhead">${m.role === 'user' ? '' : '<strong>AI</strong>'}<span>${esc(st)}</span><span>${fmtTime(m.ts)}</span></div>${body}<div class="macts">${acts}</div></div>`;
}
function renderMsgs(keepScroll) {
  const box = $('#msgs'); const msgs = S.paper.messages;
  if (!msgs.length) {
    const mock = S.settings?.provider === 'mock';
    box.innerHTML = `<div class="welcome"><h3>材料已经就绪</h3>
      <p>按 SKILL.md 的六站带读：① 动机 → ② 架构 → ③ 训练 → ④ 数据 → ⑤ 信息流 → ⑥ 例子走一遍（可选 ⑦ 实验）。每站讲完会问要不要继续，随时可以打断提问。</p>
      ${mock ? '<p class="err" style="text-align:left">现在是演示模式，回复是占位的。到右上角「设置」里填上模型和 API Key 再开始。</p>' : ''}
      <button class="btn primary" data-start>▶ 开始：基本情况 + ① 动机</button></div>`;
    $('[data-start]', box).onclick = () => { setStation('0', false); send(ST['0'].prompt, 'station'); };
    return;
  }
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  box.innerHTML = msgs.map((m, i) => msgHtml(m, i, msgs.length)).join('');
  bindMsgs(box);
  if (!keepScroll || atBottom) box.scrollTop = box.scrollHeight;
}
function bindMsgs(box) {
  $$('.md img, [data-zoom]', box).forEach(img => img.onclick = () => lightbox(img.src, img.alt));
  $$('[data-ma]', box).forEach(b => b.onclick = async () => {
    const el = b.closest('.msg'); const id = el.dataset.id; const m = S.paper.messages.find(x => x.id === id);
    const act = b.dataset.ma;
    if (act === 'copy') { try { await navigator.clipboard.writeText(m.content); toast('已复制 Markdown'); } catch { toast('复制失败'); } }
    if (act === 'del') {
      if (!confirm('删除这条消息？')) return;
      const r = await api(`/api/papers/${encodeURIComponent(S.slug)}/messages/${id}`, { method: 'DELETE' });
      S.paper.messages = r.messages; renderMsgs(true); renderStbar(); renderNext();
    }
    if (act === 'regen') send('', 'chat', true);
    if (act === 'qa') { draftSection('qa', id); showMobile('right'); }
  });
}

function addAttachment(a) {
  if (S.attachments.some(x => x.type === a.type && x.path === a.path && x.start === a.start)) return;
  S.attachments.push(a); renderAtt();
}
function renderAtt() {
  const box = $('#attBox'); if (!box) return;
  box.innerHTML = S.attachments.map((a, i) => a.type === 'image'
    ? `<span class="chip"><img src="/files/${encodeURIComponent(S.slug)}/${esc(a.path)}" style="height:22px;border:none" alt="">${esc(a.label)}<button class="icon-btn" data-rm="${i}">✕</button></span>`
    : `<span class="chip">⌗ ${esc(a.label)}<button class="icon-btn" data-rm="${i}">✕</button></span>`).join('');
  box.style.display = S.attachments.length ? 'flex' : 'none';
  $$('[data-rm]', box).forEach(b => b.onclick = () => { S.attachments.splice(+b.dataset.rm, 1); renderAtt(); });
}

function setBusy(busy) {
  const b = $('#sendBtn'); if (!b) return;
  b.textContent = busy ? '停止' : '发送'; b.classList.toggle('primary', !busy);
}
function stop() { if (S.ctrl) S.ctrl.abort(); }

async function send(text, kind = 'chat', regenerate = false) {
  if (S.ctrl) return toast('上一条还在生成，可以先点「停止」');
  const input = $('#input');
  text = (text ?? input.value).trim();
  if (!regenerate && !text && !S.attachments.length) return;
  if (!regenerate && input && text === input.value.trim()) { input.value = ''; input.style.height = ''; }
  const body = {
    text, station: S.station, kind, regenerate,
    images: S.attachments.filter(a => a.type === 'image').map(a => a.path),
    attachments: S.attachments.filter(a => a.type === 'code').map(({ path, start, end, text: t }) => ({ path, start, end, text: t })),
  };
  if (!regenerate) { S.attachments = []; renderAtt(); }
  const msgs = S.paper.messages;
  if (regenerate) while (msgs.length && msgs[msgs.length - 1].role === 'assistant') msgs.pop();
  const live = { id: 'live', role: 'assistant', content: '', station: S.station, tools: [], ts: new Date().toISOString() };
  S.ctrl = new AbortController(); setBusy(true);
  let shown = false; let raf = 0;
  const paint = () => {
    raf = 0; const el = $('.msg[data-id="live"]');
    if (!el) return;
    const tools = live.tools.length ? `<details class="tools"><summary>查阅了 ${live.tools.length} 处原文 / 代码 / 图</summary><ul>${live.tools.map(t => `<li>${esc(t)}</li>`).join('')}</ul></details>` : '';
    $('.bubble', el).innerHTML = `${tools}<div class="md cursor">${live.content ? md(live.content) : '<span class="muted">思考中…</span>'}</div>`;
    const box = $('#msgs'); if (box.scrollHeight - box.scrollTop - box.clientHeight < 160) box.scrollTop = box.scrollHeight;
  };
  try {
    await streamPost(`/api/papers/${encodeURIComponent(S.slug)}/chat`, body, ev => {
      if (ev.type === 'user') {
        if (!regenerate) msgs.push(ev.message);
        msgs.push(live); renderMsgs(); shown = true; paint();
      } else if (ev.type === 'text') { live.content += ev.text; if (!raf) raf = requestAnimationFrame(paint); }
      else if (ev.type === 'tool') { live.tools.push(ev.summary); if (!raf) raf = requestAnimationFrame(paint); }
      else if (ev.type === 'error') { live.error = ev.error; }
      else if (ev.type === 'done') { Object.assign(live, ev.message); }
    }, S.ctrl.signal);
  } catch (e) {
    if (e.name !== 'AbortError') { live.error = e.message; toast('出错：' + e.message); }
    else live.content += '\n\n（已停止）';
  } finally {
    S.ctrl = null; setBusy(false);
    if (shown) {
      if (live.id === 'live') {  // 被中断：服务器端会存已生成的部分，这里刷新一次拿到正式 id
        try { const p = await api('/api/papers/' + encodeURIComponent(S.slug)); S.paper.messages = p.messages; } catch { /* */ }
      }
      renderMsgs(); renderStbar(); renderNext();
    }
  }
}

/* ---------------- 右栏：精读笔记 ---------------- */
function sectionTitle(key) { return (S.paper.sections.find(([k]) => k === key) || [key, key])[1]; }
function renderNotes() {
  const el = $('#paneRight');
  const imported = S.notes.imported_from ? `<div class="pad small muted" style="padding-bottom:0">已从 ${esc(S.notes.imported_from)} 读入笔记内容。</div>` : '';
  el.innerHTML = `<div class="notes-head"><h3>精读笔记</h3><span class="save-state" id="saveState">${esc(S.saveState)}</span>
      <button class="btn sm ghost" data-act="collapse" title="全部折叠 / 展开">⇅</button>
      <button class="btn sm" data-act="preview">预览</button></div>${imported}
    <div class="pane-body"><div class="nsecs" id="nsecs">${S.paper.sections.map(([k]) => secHtml(k)).join('')}</div></div>`;
  $('[data-act=preview]', el).onclick = () => headAction('preview');
  $('[data-act=collapse]', el).onclick = () => {
    const allC = S.paper.sections.every(([k]) => S.collapsed[k]);
    S.paper.sections.forEach(([k]) => { S.collapsed[k] = !allC; }); renderNotes();
  };
  bindSecs(el);
}
function secHtml(key) {
  const text = S.notes.sections[key] || ''; const ed = S.editing[key]; const d = S.drafts[key];
  const filled = text.trim() ? 'filled' : '';
  const focus = ST[S.station]?.note === key ? 'focus' : '';
  const isStation = /^s\d$|^basic$|^map$|^code$|^qa$/.test(key);
  let body;
  if (ed) body = `<textarea data-ta="${key}" spellcheck="false">${esc(text)}</textarea><div class="row" style="margin-top:6px"><span class="muted small grow">Markdown；图用 ![说明](figures/fig-03.png)</span><button class="btn sm primary" data-sa="done">完成</button></div>`;
  else body = text.trim() ? `<div class="md">${md(text)}</div>` : `<div class="nsec-empty">${key === 'qa' ? '在讨论里点某条回复下面的「记入问答」，或让 AI 从全部讨论里整理。' : '还没整理。讲完这一站后点「AI 整理」，或者点「编辑」自己写。'}</div>`;
  if (d) body += `<div class="draft"><div class="muted small">AI 草稿${d.streaming ? '（生成中…）' : ''}${d.error ? ' · <span style="color:var(--err)">' + esc(d.error) + '</span>' : ''}</div>
      <div class="md ${d.streaming ? 'cursor' : ''}">${md(d.text)}</div>
      ${d.streaming ? `<div class="row"><button class="btn sm" data-sa="dstop">停止</button></div>` : `<div class="row"><button class="btn sm primary" data-sa="${d.mode === 'append' || text.trim() && key === 'qa' ? 'append' : 'replace'}">${d.mode === 'append' || text.trim() && key === 'qa' ? '追加到这一节' : (text.trim() ? '替换这一节' : '采用')}</button>${text.trim() ? `<button class="btn sm" data-sa="${d.mode === 'append' || key === 'qa' ? 'replace' : 'append'}">${d.mode === 'append' || key === 'qa' ? '替换' : '追加到末尾'}</button>` : ''}<button class="btn sm ghost" data-sa="discard">放弃</button></div>`}</div>`;
  return `<div class="nsec ${filled} ${focus} ${S.collapsed[key] ? 'collapsed' : ''}" data-key="${key}">
    <div class="nsec-h" data-sa="toggle"><span class="st"></span><span class="t">${esc(sectionTitle(key))}</span>
      ${isStation ? `<button class="btn sm ghost" data-sa="ai" title="让 AI 根据讨论和论文整理这一节">✨ AI 整理</button>` : ''}
      <button class="btn sm ghost" data-sa="edit">${ed ? '收起' : '编辑'}</button></div>
    <div class="nsec-b">${body}</div></div>`;
}
function rerenderSec(key) {
  const old = $(`.nsec[data-key="${key}"]`); if (!old) return;
  const t = document.createElement('template'); t.innerHTML = secHtml(key).trim();
  const nu = t.content.firstElementChild; old.replaceWith(nu); bindSecs(nu.parentElement, key);
}
function bindSecs(root, only) {
  $$('.nsec', root).forEach(sec => {
    const key = sec.dataset.key; if (only && key !== only) return;
    $$('[data-sa]', sec).forEach(b => b.onclick = e => {
      e.stopPropagation(); const a = b.dataset.sa;
      if (a === 'toggle') { S.collapsed[key] = !S.collapsed[key]; sec.classList.toggle('collapsed', S.collapsed[key]); }
      if (a === 'edit') { S.editing[key] = !S.editing[key]; S.collapsed[key] = false; rerenderSec(key); if (S.editing[key]) $(`[data-ta="${key}"]`)?.focus(); }
      if (a === 'done') { S.editing[key] = false; rerenderSec(key); flushSave(); }
      if (a === 'ai') draftSection(key);
      if (a === 'dstop') S.drafts[key]?.ctrl?.abort();
      if (a === 'discard') { delete S.drafts[key]; rerenderSec(key); }
      if (a === 'replace' || a === 'append') {
        const d = S.drafts[key]; const cur = S.notes.sections[key] || '';
        S.notes.sections[key] = a === 'append' && cur.trim() ? cur.replace(/\s+$/, '') + '\n\n' + d.text.trim() : d.text.trim();
        delete S.drafts[key]; rerenderSec(key); scheduleSave(0); refreshProgress();
      }
    });
    const ta = $('textarea[data-ta]', sec);
    if (ta) {
      const fit = () => { ta.style.height = 'auto'; ta.style.height = Math.max(140, ta.scrollHeight + 4) + 'px'; };
      fit(); ta.oninput = () => { S.notes.sections[key] = ta.value; fit(); scheduleSave(); };
    }
    $$('.md img', sec).forEach(img => img.onclick = () => lightbox(img.src, img.alt));
  });
}
function appendToSection(key, text) {
  const cur = S.notes.sections[key] || '';
  S.notes.sections[key] = cur.trim() ? cur.replace(/\s+$/, '') + '\n\n' + text : text;
  S.collapsed[key] = false; rerenderSec(key); scheduleSave(0);
  $(`.nsec[data-key="${key}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function setSaveState(s) { S.saveState = s; const el = $('#saveState'); if (el) el.textContent = s; }
function scheduleSave(ms = 900) {
  setSaveState('未保存'); clearTimeout(S.saveTimer);
  S.saveTimer = setTimeout(flushSave, ms);
}
async function flushSave() {
  if (!S.saveTimer && S.saveState !== '未保存') return;
  clearTimeout(S.saveTimer); S.saveTimer = null; setSaveState('保存中…');
  try {
    const r = await api(`/api/papers/${encodeURIComponent(S.slug)}/notes`, { method: 'PUT', json: { sections: S.notes.sections } });
    S.notes.updated = r.updated; delete S.notes.imported_from;
    const d = new Date(); setSaveState(`已保存 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} · 精读笔记.html`);
  } catch (e) { setSaveState('保存失败'); toast('笔记保存失败：' + e.message); }
}
window.addEventListener('beforeunload', e => { if (S.saveState === '未保存') { flushSave(); e.preventDefault(); } });
function refreshProgress() {
  S.paper.progress = S.paper.progress || {};
  S.paper.progress.noted = Object.entries(S.notes.sections).filter(([, v]) => v && v.trim()).map(([k]) => k);
}

async function draftSection(key, msgId) {
  if (S.drafts[key]?.streaming) return;
  const d = { text: '', streaming: true, mode: key === 'qa' ? 'append' : 'replace', ctrl: new AbortController() };
  S.drafts[key] = d; S.collapsed[key] = false; rerenderSec(key);
  $(`.nsec[data-key="${key}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  let raf = 0;
  const paint = () => {
    raf = 0; const box = $(`.nsec[data-key="${key}"] .draft .md`);
    if (box) box.innerHTML = md(d.text);
  };
  try {
    await streamPost(`/api/papers/${encodeURIComponent(S.slug)}/notes/draft`, { target: key, msg_id: msgId }, ev => {
      if (ev.type === 'text') { d.text += ev.text; if (!raf) raf = requestAnimationFrame(paint); }
      if (ev.type === 'error') d.error = ev.error;
      if (ev.type === 'done' && ev.error) d.error = ev.error;
    }, d.ctrl.signal);
  } catch (e) { if (e.name !== 'AbortError') d.error = e.message; }
  d.streaming = false; d.text = d.text.trim();
  rerenderSec(key);
}

/* ---------------- 启动 ---------------- */
(async () => {
  if (location.protocol === 'file:') return;  // 直接双击打开的 HTML：index.html 里已经提示怎么启动
  try { await loadSettings(); } catch (e) {
    $('#app').innerHTML = `<div class="welcome"><h3>连不上后端</h3><p>${esc(e.message)}</p><p>确认启动窗口还开着（双击项目根目录的 <code>start.bat</code>），然后刷新本页。</p></div>`;
    return;
  }
  route();
})();
