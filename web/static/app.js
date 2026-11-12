/* Bling-Workspace · 前端（无构建，原生 JS）：论文精读 + 代码分析 */
'use strict';

const PAPER_STATIONS = [
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
// 代码仓库的七站（references/code-reading.md）；笔记节 key 与论文共用
const REPO_STATIONS = [
  { id: '0', label: '概览', note: 'basic', prompt: '开始吧：先给项目概览，然后直接讲第 ① 站 定位。' },
  { id: '1', label: '① 定位', note: 's1', prompt: '讲第 ① 站：定位——它解决什么问题、对外接口长什么样、一个最小用法。' },
  { id: '2', label: '② 结构', note: 's2', prompt: '继续，讲第 ② 站：目录和模块结构，画一张文字架构图，指出最该先读的几个文件。' },
  { id: '3', label: '③ 入口', note: 's3', prompt: '继续，讲第 ③ 站：入口和启动链路，配置从哪来。' },
  { id: '4', label: '④ 数据', note: 's4', prompt: '继续，讲第 ④ 站：核心数据结构长什么样，谁创建、谁修改、谁消费。' },
  { id: '5', label: '⑤ 主流程', note: 's5', prompt: '继续，讲第 ⑤ 站：最核心的那条调用链 / 主流程。' },
  { id: '6', label: '⑥ 例子', note: 's6', prompt: '继续，讲第 ⑥ 站：拿一次具体调用，按时间顺序逐函数走一遍，标上文件和行号。' },
  { id: '7', label: '⑦ 工程', note: 's7', prompt: '讲第 ⑦ 站：依赖、测试、CI、代码质量和风险，以及想加一个功能该改哪几处。' },
  { id: 'free', label: '自由讨论', note: 'qa', prompt: '' },
];
let STATIONS = PAPER_STATIONS;
let ST = Object.fromEntries(STATIONS.map(s => [s.id, s]));
// [按钮, 发送的话, 需要用户补全时光标位置]
const PAPER_QUICK = [
  ['没懂，换个讲法', '没懂，换一种讲法。'],
  ['举个例子走一遍', '能不能举一个具体例子，带真实数字走一遍？'],
  ['翻译原文', '把这一站对应的原文段落翻译一下，原文和译文对照着放。'],
  ['和 X 的区别', '这个和  有什么区别？', 5],
  ['接着说', '接着说。'],
];
const REPO_QUICK = [
  ['没懂，换个讲法', '没懂，换一种讲法。'],
  ['谁调用了它', '刚才说的这个函数 / 类在哪些地方被调用？列出调用点（文件:行）和各自的用途。'],
  ['画调用链', '把刚才讲的流程画成一张文字调用链，缩进表示调用层级，标上文件和行号。'],
  ['想改 X 改哪', '如果我想 ，需要改哪几个地方？按顺序列出文件:行和要改什么。', 4],
  ['接着说', '接着说。'],
];
let QUICK = PAPER_QUICK;
let KIND = 'paper';
function setKind(kind) {
  KIND = kind === 'repo' ? 'repo' : 'paper';
  STATIONS = KIND === 'repo' ? REPO_STATIONS : PAPER_STATIONS;
  ST = Object.fromEntries(STATIONS.map(s => [s.id, s]));
  QUICK = KIND === 'repo' ? REPO_QUICK : PAPER_QUICK;
}
const isRepo = () => KIND === 'repo';
const noteLabel = () => (isRepo() ? '代码分析笔记' : '精读笔记');
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
  questionSearch: '', questionFrame: null,
  libFilter: 'all', importType: 'paper', repoMode: 'git', symbols: null, symQuery: '',
};

/* ---------------- 小工具 ---------------- */
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem('bling:' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('bling:' + k, JSON.stringify(v)); } catch { /* 无痕模式等 */ } },
};
S.libFilter = ['all', 'paper', 'repo'].includes(store.get('libFilter')) ? store.get('libFilter') : 'all';
S.importType = store.get('importType', 'paper') === 'repo' ? 'repo' : 'paper';
$('#themeSelect').value = ['sage', 'paper', 'dark'].includes(store.get('theme')) ? store.get('theme') : 'sage';
document.documentElement.dataset.theme = $('#themeSelect').value;
$('#themeSelect').onchange = e => { document.documentElement.dataset.theme = e.target.value; store.set('theme', e.target.value); };
function toast(msg, ms = 2600) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, ms);
}
async function copyContent(text) {
  if (await BlingClipboard.copyText(text)) return toast('已复制');
  openModal('复制内容', `<p>浏览器未允许自动复制，内容已选中，请按 Ctrl+C（Mac：⌘C）。</p><textarea id="manualCopy" rows="12" readonly aria-label="待复制内容">${esc(text)}</textarea>`, body => {
    const field = $('#manualCopy', body); field.focus(); field.select();
  });
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
function md(text, slug = S.slug, opts = {}) {
  const html = DOMPurify.sanitize(marked.parse(text || ''), { ADD_ATTR: ['target'] });
  const t = document.createElement('template'); t.innerHTML = html;
  t.content.querySelectorAll('img').forEach(img => {
    const src = img.getAttribute('src') || '';
    const rel = !/^(https?:|data:|\/)/.test(src);
    if (rel && opts.imgBase !== undefined) {  // README 里的相对图片：GitHub 仓库指到 raw，其他去掉
      if (opts.imgBase) img.setAttribute('src', opts.imgBase + src.replace(/^\.\//, '')); else { img.remove(); return; }
    } else if (rel && slug) img.setAttribute('src', `/files/${encodeURIComponent(slug)}/${src.replace(/^\.\//, '')}`);
    img.setAttribute('loading', 'lazy');
  });
  t.content.querySelectorAll('a[href]').forEach(a => { a.target = '_blank'; a.rel = 'noopener'; });
  // `code/路径:行号` → 点击在左栏打开并高亮那几行
  t.content.querySelectorAll('code').forEach(c => {
    if (c.closest('pre')) return;
    const ref = parseCodeRef(c.textContent);
    if (!ref) return;
    c.classList.add('code-ref'); c.dataset.refPath = ref.path;
    if (ref.line) { c.dataset.refLine = ref.line; if (ref.end) c.dataset.refEnd = ref.end; }
    c.title = '在左侧打开' + (ref.line ? ` · 第 ${ref.line}${ref.end ? '–' + ref.end : ''} 行` : '');
  });
  return t.innerHTML;
}
function parseCodeRef(text) {
  if (!S.slug || !(isRepo() || S.paper?.code_root)) return null;
  const s = (text || '').trim().replace(/^\.\//, '');
  let m = s.match(/^(code\/[^\s:`()]+?)(?::(\d+)(?:\s*[-–~]\s*(\d+))?)?$/);
  if (!m && isRepo()) {  // 模型偶尔省略 code/ 前缀：src/app.py:12
    m = s.match(/^([\w@-][\w.@/-]*\.[A-Za-z0-9]{1,8})(?::(\d+)(?:\s*[-–~]\s*(\d+))?)?$/);
    if (m && !/^(https?|www)\b/i.test(m[1]) && (m[1].includes('/') || m[2])) {
      const sub = S.paper?.meta?.subdir;
      m = [m[0], 'code/' + (sub && !m[1].startsWith(sub + '/') ? sub + '/' : '') + m[1], m[2], m[3]];
    } else m = null;
  }
  if (!m) return null;
  return { path: m[1].replace(/\/$/, ''), line: m[2] ? +m[2] : null, end: m[3] ? +m[3] : null };
}
document.addEventListener('click', e => {
  const c = e.target.closest('.code-ref');
  if (!c || !S.slug) return;
  e.preventDefault();
  openFileAt(c.dataset.refPath, c.dataset.refLine ? +c.dataset.refLine : null, c.dataset.refEnd ? +c.dataset.refEnd : null);
});

/* ---------------- 轻量语法高亮（无依赖；按扩展名选一组规则） ---------------- */
const KW = {
  py: 'and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield match case self cls',
  js: 'break case catch class const continue debugger default delete do else export extends false finally for from function if import in instanceof let new null return super switch this throw true try typeof undefined var void while with yield async await of static get set interface type enum implements private public protected readonly declare namespace abstract as keyof',
  go: 'break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var nil true false iota',
  rust: 'as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while Some None Ok Err',
  c: 'auto break case char const continue default do double else enum extern float for goto if inline int long register return short signed sizeof static struct switch typedef union unsigned void volatile while class namespace template typename public private protected virtual override new delete this true false nullptr using bool constexpr',
  java: 'abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for if implements import instanceof int interface long native new package private protected public return short static super switch synchronized this throw throws try void volatile while true false null var val fun when object data sealed override suspend string using namespace async await let func struct',
  sh: 'if then else elif fi for while until do done case esac function in return export local readonly echo exit set unset source alias param',
  sql: 'select from where join left right inner outer on group by order having insert into values update set delete create table index primary key foreign references drop alter as and or not null is in like limit distinct union all case when then else end local function return if end',
  json: 'true false null',
};
const Q3D = '"'.repeat(3), Q3S = "'".repeat(3);
const HL_RULES = {
  py: { kw: 'py', line: '#', str: [Q3D, Q3S, '"', "'"], dec: true },
  js: { kw: 'js', line: '//', block: ['/*', '*/'], str: ['`', '"', "'"], dec: true },
  go: { kw: 'go', line: '//', block: ['/*', '*/'], str: ['`', '"', "'"] },
  rust: { kw: 'rust', line: '//', block: ['/*', '*/'], str: ['"'] },
  c: { kw: 'c', line: '//', block: ['/*', '*/'], str: ['"', "'"], pre: true },
  java: { kw: 'java', line: '//', block: ['/*', '*/'], str: [Q3D, '"', "'"], dec: true },
  sh: { kw: 'sh', line: '#', str: ['"', "'"] },
  sql: { kw: 'sql', line: '--', block: ['/*', '*/'], str: ["'", '"'] },
  json: { kw: 'json', str: ['"'] },
  conf: { line: '#', str: ['"', "'"] },
  css: { block: ['/*', '*/'], str: ['"', "'"] },
  html: { block: ['<!--', '-->'], str: ['"', "'"], tag: true },
};
const EXT_HL = { py: 'py', pyi: 'py', pyx: 'py', js: 'js', mjs: 'js', cjs: 'js', jsx: 'js', ts: 'js', tsx: 'js', mts: 'js', vue: 'html', svelte: 'html',
  go: 'go', rs: 'rust', c: 'c', h: 'c', cc: 'c', cpp: 'c', cxx: 'c', hpp: 'c', hh: 'c', cu: 'c', cuh: 'c', m: 'c', mm: 'c', proto: 'c',
  java: 'java', kt: 'java', kts: 'java', scala: 'java', cs: 'java', dart: 'java', swift: 'java', groovy: 'java', gradle: 'java', php: 'java',
  sh: 'sh', bash: 'sh', zsh: 'sh', ps1: 'sh', rb: 'sh', pl: 'sh', r: 'sh', jl: 'sh', lua: 'sql', sql: 'sql',
  json: 'json', jsonc: 'js', yaml: 'conf', yml: 'conf', toml: 'conf', ini: 'conf', cfg: 'conf', env: 'conf', dockerfile: 'sh', makefile: 'sh', cmake: 'sh',
  css: 'css', scss: 'css', less: 'css', html: 'html', htm: 'html', xml: 'html', svg: 'html' };
const _hlCache = {};
function hlRegex(key) {
  if (_hlCache[key]) return _hlCache[key];
  const r = HL_RULES[key];
  const e = x => x.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
  const com = [];
  if (r.block) com.push(e(r.block[0]) + '[\\s\\S]*?(?:' + e(r.block[1]) + '|$(?![\\s\\S]))');
  if (r.line) com.push(e(r.line) + '[^\\n]*');
  const str = (r.str || []).map(q => (q.length === 3 ? e(q) + '[\\s\\S]*?(?:' + e(q) + '|$(?![\\s\\S]))'
    : q === '`' ? '`(?:\\\\[\\s\\S]|[^\\\\`])*`?' : e(q) + '(?:\\\\.|[^\\\\' + e(q) + '\\n])*' + e(q) + '?'));
  const parts = [];
  if (com.length) parts.push(`(?<com>${com.join('|')})`);
  if (str.length) parts.push(`(?<str>${str.join('|')})`);
  if (r.pre) parts.push('(?<dec>^[ \\t]*#[ \\t]*\\w+)');
  if (r.dec) parts.push('(?<dec>@[A-Za-z_][\\w.]*)');
  if (r.tag) parts.push('(?<kw></?[A-Za-z][\\w:-]*|/?>)');
  parts.push('(?<num>\\b(?:0[xX][\\da-fA-F_]+|\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?)\\b)');
  if (r.kw) parts.push(`(?<kw>\\b(?:${KW[r.kw].split(' ').map(e).join('|')})\\b)`);
  if (['conf', 'json'].includes(key)) parts.push('(?<fn>^[ \\t-]*[\\w.-]+(?=\\s*[:=]))');
  else if (!['html', 'css'].includes(key)) parts.push('(?<fn>\\b[A-Za-z_$][\\w$]*(?=\\s*\\())');
  return (_hlCache[key] = new RegExp(parts.join('|'), 'gm'));
}
/* → 每行一段 HTML；不认识的语言 / 太大的文件只做转义 */
function highlightLines(text, path) {
  const name = (path || '').split('/').pop().toLowerCase();
  const ext = ['dockerfile', 'makefile'].includes(name) ? name : (name.includes('.') ? name.split('.').pop() : '');
  const key = EXT_HL[ext];
  if (!key || text.length > 600000) return text.split('\n').map(esc);
  const rx = hlRegex(key); rx.lastIndex = 0;
  const lines = ['']; let last = 0; let m;
  const push = (seg, cls) => {
    seg.split('\n').forEach((piece, i) => {
      if (i) lines.push('');
      if (piece) lines[lines.length - 1] += cls ? `<span class="tk-${cls}">${esc(piece)}</span>` : esc(piece);
    });
  };
  while ((m = rx.exec(text))) {
    if (!m[0]) { rx.lastIndex++; continue; }
    if (m.index > last) push(text.slice(last, m.index));
    push(m[0], Object.keys(m.groups).find(k => m.groups[k] !== undefined));
    last = m.index + m[0].length;
  }
  if (last < text.length) push(text.slice(last));
  return lines;
}

/* GitHub 风格的语言色（语言名 → 颜色），没有的按名字散列取一个 */
const LANG_COLORS = { Python: '#3572A5', JavaScript: '#e5c33a', TypeScript: '#3178c6', Go: '#00ADD8', Rust: '#dea584', Java: '#b07219',
  'C++': '#f34b7d', C: '#6e6e6e', 'C/C++ 头文件': '#a0789a', 'C#': '#178600', CUDA: '#3A4E3A', Shell: '#89e051', PowerShell: '#2b5797', Batch: '#9bbf2c',
  HTML: '#e34c26', CSS: '#563d7c', SCSS: '#c6538c', Less: '#1d365d', Vue: '#41b883', Svelte: '#ff3e00', Kotlin: '#A97BFF', Swift: '#F05138',
  Ruby: '#701516', PHP: '#4F5D95', Scala: '#c22d40', Dart: '#00B4AB', Lua: '#2c2d72', R: '#198CE7', Julia: '#a270ba', SQL: '#e38c00',
  'Objective-C': '#438eff', Dockerfile: '#384d54', Makefile: '#427819', CMake: '#DA3434', Cython: '#c9b23a', Protobuf: '#6b9b7a', Groovy: '#4298b8' };
function langColor(name) {
  if (LANG_COLORS[name]) return LANG_COLORS[name];
  let h = 0; for (const ch of name || '') h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 45% 52%)`;
}
function langBar(langs, legend = 3) {
  if (!langs || !langs.length) return '';
  const bar = `<div class="langbar" role="img" aria-label="语言分布：${esc(langs.slice(0, 4).map(l => l.name + ' ' + l.pct + '%').join('，'))}">${langs.map(l => `<span style="width:${Math.max(l.pct, 0.8)}%;background:${langColor(l.name)}" title="${esc(l.name)} ${l.pct}%"></span>`).join('')}</div>`;
  const leg = legend ? `<div class="langleg">${langs.slice(0, legend).map(l => `<span><i style="background:${langColor(l.name)}"></i>${esc(l.name)} <span class="muted">${l.pct}%</span></span>`).join('')}</div>` : '';
  return bar + leg;
}
const fmtNum = n => (n == null ? '' : n >= 10000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1) + 'k' : n.toLocaleString());
function lightbox(src, cap) {
  const lb = $('#lightbox'); $('img', lb).src = src; $('p', lb).textContent = cap || ''; lb.hidden = false;
}
$('#lightbox').addEventListener('click', () => { $('#lightbox').hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('#lightbox').hidden = true; closeModal(); } });

function openModal(title, html, onMount) {
  $('#modalTitle').textContent = title; $('#modalBody').innerHTML = html; $('#modal').hidden = false;
  if (onMount) onMount($('#modalBody'));
}
function closeModal() { $('#modal').hidden = true; $('#modalBody').innerHTML = ''; $('#modal .modal-card').classList.remove('history-modal'); }
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal' || e.target.closest('[data-close]')) closeModal(); });

/* ---------------- 历史与复习 ---------------- */
const HISTORY_REASONS = { analysis: '分析记录', existing: '已有记录', before_regenerate: '重新生成前', before_delete: '删除前备份', notes: '笔记保存', before_notes: '笔记修改前', draft: '笔记草稿' };
async function openHistory() {
  const slug = S.slug;
  try {
    const r = await api(`/api/papers/${encodeURIComponent(slug)}/history`);
    openModal('分析历史 · 回看与对比', `
      <p class="muted small">每次分析及笔记修改都会保留本地版本。重新生成、删除消息前的内容也可在这里回看；历史版本只读。</p>
      <div class="history-controls"><input id="historySearch" aria-label="搜索历史" placeholder="搜索提问或记录类型…">
      <select id="historyMode" aria-label="查看内容"><option value="answer">本次分析 / 回答</option><option value="discussion">完整讨论</option><option value="notes">${noteLabel()}</option><option value="draft">笔记草稿</option></select></div>
      <p id="historyCount" class="small muted"></p>
      <div class="history-grid">${['a', 'b'].map((side, i) => `<section class="history-side"><label class="field"><span>${i ? '版本 B · 对比' : '版本 A · 回看'}</span><select id="history-${side}" aria-label="版本 ${side.toUpperCase()}"></select></label><div id="history-meta-${side}" class="small muted"></div><article id="history-body-${side}" class="md history-body"></article></section>`).join('')}</div>`, body => {
        $('#modal .modal-card').classList.add('history-modal');
        const cache = new Map();
        let generation = 0;
        const show = async () => {
          const current = ++generation;
          await Promise.all(['a', 'b'].map(async side => {
            const id = $(`#history-${side}`, body).value;
            const pane = $(`#history-body-${side}`, body);
            const meta = $(`#history-meta-${side}`, body);
            if (!id) { pane.innerHTML = '<p class="muted">还没有匹配的历史记录。分析完成后会自动出现在这里。</p>'; meta.textContent = ''; return; }
            pane.textContent = '正在读取…';
            try {
              if (!cache.has(id)) cache.set(id, await api(`/api/papers/${encodeURIComponent(slug)}/history/${encodeURIComponent(id)}`));
              if (generation !== current || !body.isConnected) return;
              const version = cache.get(id); const mode = $('#historyMode', body).value;
              meta.textContent = `${new Date(version.created).toLocaleString()} · ${HISTORY_REASONS[version.reason] || version.reason} · ${version.model || '未记录模型'} · ${version.messages.length} 条消息`;
              if (mode === 'notes') {
                pane.innerHTML = (S.paper.sections || []).map(([key, title]) => version.notes?.sections?.[key] ? `<h3>${esc(title)}</h3>${md(version.notes.sections[key], slug)}` : '').join('') || '<p class="muted">这一版还没有整理笔记。</p>';
              } else if (mode === 'draft') {
                pane.innerHTML = version.draft ? md(version.draft.text, slug) + (version.draft.error ? `<p class="err">${esc(version.draft.error)}</p>` : '') : '<p class="muted">这一版没有笔记草稿。</p>';
              } else {
                const messages = mode === 'answer' ? version.messages.slice(-2) : version.messages;
                pane.innerHTML = messages.map(m => `<section class="history-message"><div class="history-role">${m.role === 'user' ? '提问' : '分析'} · ${esc(ST[m.station]?.label || '讨论')} · ${esc(fmtTime(m.ts))}</div>${md(m.content, slug)}${m.error ? `<p class="err">${esc(m.error)}</p>` : ''}</section>`).join('') || '<p class="muted">没有讨论内容。</p>';
              }
            } catch (e) { pane.textContent = '读取失败：' + e.message; }
          }));
        };
        const fill = () => {
          const q = $('#historySearch', body).value.trim().toLowerCase();
          const items = r.items.filter(item => !q || `${item.title} ${HISTORY_REASONS[item.reason] || item.reason}`.toLowerCase().includes(q));
          $('#historyCount', body).textContent = `共保留 ${r.items.length} 个版本${q ? `，匹配 ${items.length} 个` : ''} · 保存在资料目录的 history 文件夹`;
          ['a', 'b'].forEach((side, index) => {
            const select = $(`#history-${side}`, body); const previous = select.value;
            select.innerHTML = items.map(item => `<option value="${esc(item.id)}">${esc(fmtTime(item.created))} · ${esc(HISTORY_REASONS[item.reason] || item.reason)} · ${esc(item.title)}</option>`).join('');
            if (items.some(item => item.id === previous)) select.value = previous;
            else if (items.length) select.value = items[Math.min(index, items.length - 1)].id;
            select.onchange = show;
          });
          show();
        };
        $('#historySearch', body).oninput = fill;
        $('#historyMode', body).onchange = show;
        fill();
      });
  } catch (e) { toast('读取历史失败：' + e.message); }
}

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
    <h4>下载网络</h4>
    <label class="field"><span>代码导入代理</span><input id="sProxy" value="${esc(s.network_proxy || 'auto')}" placeholder="auto 或 http://127.0.0.1:7897"></label>
    <p class="hint">auto 自动沿用系统 / 环境 / Git 代理，或检测本机 7897 端口；填 direct 强制直连。Git 克隆和 ZIP 下载使用同一设置。</p>
    <h4>资料目录</h4>
    <div class="grid2"><label class="field"><span>论文 / 网站目录（每份资料一个子目录）</span><input id="sRoot" value="${esc(s.papers_root)}"></label>
    <label class="field"><span>代码分析目录（每个仓库一个子目录）</span><input id="sRepos" value="${esc(s.repos_root || '')}"></label></div>
    <p class="hint">相对路径按项目根目录算。本机文件夹分析时代码不复制，这里只放分析结果、讨论和笔记。</p>
    <h4>用户画像 profile.md <span class="muted small">（论文和代码讲解都按它调整：熟的一句带过、不熟的先铺垫、⑥ 用什么场景举例）</span></h4>
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
        use_tools: $('#sTools').checked, network_proxy: $('#sProxy').value.trim() || 'auto', papers_root: $('#sRoot').value.trim(), repos_root: $('#sRepos').value.trim(),
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
async function route() {
  if (S.slug && (S.saveTimer || ['未保存', '保存失败'].includes(S.saveState))) await flushSave();
  const m = location.hash.match(/^#\/p\/(.+)$/);
  if (S.ctrl) { S.ctrl.abort(); S.ctrl = null; }
  if (m) openPaper(decodeURIComponent(m[1])); else showLibrary();
}
window.addEventListener('hashchange', route);

/* ================= 资料库：论文 / 网站 / 代码仓库 ================= */
const LIB_FILTERS = [['all', '全部'], ['paper', '论文 · 网站'], ['repo', '代码库']];
async function showLibrary() {
  S.slug = null; S.paper = null; setKind('paper');
  $('#crumbs').innerHTML = '资料库';
  document.title = 'Bling-Workspace';
  const app = $('#app');
  app.innerHTML = `<div class="library"><div class="lib-inner">
    <div class="lib-hero">
      <div><span class="hero-eyebrow">YOUR LOCAL RESEARCH DESK</span><h1>Bling-Workspace</h1><p class="muted">从论文里的想法，读到代码里的实现。</p></div>
      <div class="hero-modes" aria-hidden="true"><span class="mode-pill paper">读论文 · 六站</span><span class="mode-pill repo">读代码 · 七站</span></div>
    </div>
    <div class="workspace-entries" aria-label="选择阅读方式">
      <button class="workspace-entry paper ${S.importType === 'paper' ? 'on' : ''}" data-entry="paper"><span class="entry-icon" aria-hidden="true">↗</span><span><strong>论文阅读器</strong><span>论文、PDF 与项目网站 · 六站精读</span></span><span class="entry-arrow" aria-hidden="true">→</span></button>
      <button class="workspace-entry repo ${S.importType === 'repo' ? 'on' : ''}" data-entry="repo"><span class="entry-icon" aria-hidden="true">&lt;/&gt;</span><span><strong>代码分析器</strong><span>GitHub 链接与本地项目 · 七站带读</span></span><span class="entry-arrow" aria-hidden="true">→</span></button>
    </div>
    <section class="importer" id="importer"></section>
    <div class="lib-tools"><div class="seg" id="libFilter">${LIB_FILTERS.map(([k, v]) => `<button data-f="${k}" class="${S.libFilter === k ? 'on' : ''}">${v}</button>`).join('')}</div>
      <input id="q" placeholder="搜索标题、作者、仓库、语言" value="${esc(S.query)}"><span class="muted small grow" id="count"></span><button class="btn sm" id="trashBtn">回收站</button></div>
    <div id="cards"></div>
    <p class="muted small lib-roots" id="rootLine"></p></div></div>`;
  renderImporter();
  $$('[data-entry]').forEach(b => b.onclick = () => {
    S.importType = b.dataset.entry; store.set('importType', S.importType); renderImporter();
    $('#importer').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    $('#impTarget')?.focus({ preventScroll: true });
  });
  $('#trashBtn').onclick = openTrash;
  $('#q').oninput = e => { S.query = e.target.value; renderCards(); };
  $$('#libFilter button').forEach(b => b.onclick = () => {
    S.libFilter = b.dataset.f; store.set('libFilter', S.libFilter);
    $$('#libFilter button').forEach(x => x.classList.toggle('on', x === b)); renderCards();
  });
  try {
    const r = await api('/api/papers'); S.papers = r.papers; S.root = r.root;
    $('#rootLine').innerHTML = `论文 / 网站目录：<code>${esc(r.root)}</code> · 代码分析目录：<code>${esc(r.repos_root)}</code>（设置里可改）`;
  } catch (e) { toast('读取资料库失败：' + e.message); }
  renderCards();
}

const GH_URL = /^(?:https?:\/\/)?(?:www\.)?(github\.com|gitee\.com|gitlab\.com)\/[\w.-]+\/[\w.-]+/i;
function renderImporter() {
  const el = $('#importer'); if (!el) return;
  const type = S.importType; const mode = S.importMode; const rmode = S.repoMode;
  $$('[data-entry]').forEach(b => { b.classList.toggle('on', b.dataset.entry === type); b.setAttribute('aria-pressed', String(b.dataset.entry === type)); });
  const typeSeg = `<div class="imp-type" role="tablist">${[['paper', '论文 / 网站', '读'], ['repo', '代码仓库', '{ }']].map(([k, v, ic]) =>
    `<button role="tab" aria-selected="${k === type}" data-type="${k}" class="${k === type ? 'on' : ''}"><span class="ic">${ic}</span>${v}</button>`).join('')}</div>`;
  let body;
  if (type === 'repo') {
    const main = rmode === 'local'
      ? `<input type="text" id="impTarget" placeholder="本机代码文件夹的完整路径，如 D:\\CODE\\my-project">`
      : `<input type="text" id="impTarget" placeholder="https://github.com/owner/repo，也可以是 …/tree/分支/子目录、owner/repo、Gitee / GitLab 链接">`;
    body = `<p class="lead">${rmode === 'local'
      ? '分析电脑上已有的项目：<strong>不复制、不修改</strong>，原地只读；git 仓库会记下当前分支和提交。'
      : '浅克隆到分析目录（没装 git 时自动下载 zip），统计语言、找入口、建符号索引和模块依赖，然后按七站带你读。'}</p>
      <div class="seg">${[['git', 'GitHub / Git 链接'], ['local', '本机文件夹']].map(([k, v]) => `<button data-rmode="${k}" class="${k === rmode ? 'on' : ''}">${v}</button>`).join('')}</div>
      <div class="imp-main">${main}<button class="btn primary" id="impGo">分析代码</button></div>
      <div class="imp-more repo">
        ${rmode === 'git' ? '<input id="impRef" placeholder="分支 / 标签 / 提交（可选）">' : ''}
        <input id="impSub" placeholder="只分析某个子目录（可选，如 src/core）">
        <input id="impTitle" placeholder="显示名（可选）">
      </div>`;
  } else {
    const main = {
      link: `<input type="text" id="impTarget" placeholder="网站网址（如 robotwin-platform.github.io）、arXiv 链接或 ID、PDF 直链">`,
      pdf: `<label class="dropzone" id="drop"><input type="file" id="impFile" accept="application/pdf" hidden><span id="dropText">把 PDF 拖到这里，或点击选择文件</span></label>`,
      dir: `<input type="text" id="impTarget" placeholder="本机上已有的论文目录（完整路径），只补缺的材料">`,
    }[mode];
    body = `<p class="lead">粘贴完整网址即可导入正文、图片和资源链接；网站最多抓取 5 个同站页面。论文支持 PDF、LaTeX 和图表。</p>
      <div class="seg">${[['link', 'arXiv / 链接'], ['pdf', '上传 PDF'], ['dir', '已有目录']].map(([k, v]) => `<button data-mode="${k}" class="${k === mode ? 'on' : ''}">${v}</button>`).join('')}</div>
      <div class="imp-main">${main}<button class="btn primary" id="impGo">导入</button></div>
      <div class="imp-more">
        <input id="impCode" placeholder="官方代码仓库（可选：论文里没写、自己搜到的时候填）">
        <input id="impSlug" placeholder="目录名（可选）">
        <label class="check"><input type="checkbox" id="impNoClone">只找代码链接，不克隆</label>
      </div>`;
  }
  el.className = 'importer ' + type;
  el.innerHTML = `<div class="imp-head"><h2>导入</h2>${typeSeg}</div>${body}<div id="jobBox"></div>`;
  $$('[data-type]', el).forEach(b => b.onclick = () => { S.importType = b.dataset.type; store.set('importType', S.importType); renderImporter(); });
  $$('[data-mode]', el).forEach(b => b.onclick = () => { S.importMode = b.dataset.mode; renderImporter(); });
  $$('[data-rmode]', el).forEach(b => b.onclick = () => { S.repoMode = b.dataset.rmode; renderImporter(); });
  const drop = $('#drop', el);
  if (drop) {
    const f = $('#impFile', el);
    f.onchange = () => { $('#dropText').textContent = f.files[0] ? `已选：${f.files[0].name}` : '把 PDF 拖到这里，或点击选择文件'; };
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) { f.files = e.dataTransfer.files; f.onchange(); } };
  }
  const t = $('#impTarget', el); if (t) t.onkeydown = e => { if (e.key === 'Enter') doImport(); };
  $$('input', el).forEach(i => { if (!i.getAttribute('aria-label')) i.setAttribute('aria-label', i.placeholder || i.id); });
  $('#impGo', el).onclick = doImport;
  if (S.job) renderJob($('#jobBox', el), S.job);
}

async function doImport() {
  const fd = new FormData();
  let kind = S.importType;
  if (kind === 'paper' && S.importMode === 'link') {
    const t = $('#impTarget').value.trim();
    if (GH_URL.test(t) && !/arxiv|\.pdf($|\?)/i.test(t) && confirm('这是一个代码仓库链接。用「代码分析器」打开它吗？\n（取消则按网站导入）')) {
      S.importType = 'repo'; S.repoMode = 'git'; renderImporter(); $('#impTarget').value = t; kind = 'repo';
    }
  }
  if (kind === 'repo') {
    const t = $('#impTarget').value.trim(); if (!t) return toast(S.repoMode === 'local' ? '先填文件夹路径' : '先填仓库链接');
    fd.append('type', 'repo'); fd.append('target', t);
    if ($('#impRef')) fd.append('ref', $('#impRef').value.trim());
    fd.append('subdir', $('#impSub').value.trim()); fd.append('title', $('#impTitle').value.trim());
  } else if (S.importMode === 'pdf') {
    const f = $('#impFile').files[0]; if (!f) return toast('先选一个 PDF');
    fd.append('pdf', f);
  } else {
    const t = $('#impTarget').value.trim(); if (!t) return toast('先填链接 / ID / 路径');
    fd.append('target', t);
  }
  if (kind !== 'repo') {
    fd.append('code', $('#impCode').value.trim());
    fd.append('slug', $('#impSlug').value.trim());
    if ($('#impNoClone').checked) fd.append('no_clone', '1');
  }
  $('#impGo').disabled = true;
  try {
    const job = await api('/api/import', { method: 'POST', body: fd });
    job.kind = kind;
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
    ${j.status === 'done' && j.slug ? `<a class="btn primary" href="#/p/${encodeURIComponent(j.slug)}">${j.kind === 'repo' ? '开始分析' : '开始精读'} →</a>` : ''}</div>`;
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
  const st = p.kind === 'repo' ? REPO_STATIONS : PAPER_STATIONS;
  const talked = new Set(p.talked || []); if (talked.has('0')) talked.add('1');
  const noted = new Set(p.noted || []);
  return st.slice(1, 8).map(s => `<span class="st-dot ${noted.has(s.note) ? 'noted' : talked.has(s.id) ? 'talked' : ''}" title="${s.label}">${s.label[0]}</span>`).join('');
}

function repoSource(p) {
  if (p.source === 'local') return `本机 · ${esc(p.local_path || '')}`;
  const u = (p.source_url || '').replace(/^https?:\/\/(www\.)?/, '');
  return esc(u) + (p.branch ? ` · ${esc(p.branch)}` : '');
}
async function deleteRecord(slug, title) {
  if (S.ctrl) return toast('请先停止当前生成，再删除记录');
  if (S.saveState === '保存中…') return toast('请等待笔记保存完成后再删除记录');
  openModal('删除整份阅读记录', `<p>将 <strong>${esc(title)}</strong> 从资料库移入回收站。</p><p>这份资料的全部讨论、笔记和历史一起移除，可在回收站恢复。本地源码、PDF 和记录文件保留。</p><div class="row"><span class="grow"></span><button class="btn" data-close>取消</button><button class="btn danger" id="deleteRecordConfirm">移入回收站</button></div>`, body => {
    $('#deleteRecordConfirm', body).onclick = async e => {
      e.target.disabled = true;
      try {
        if (S.slug === slug) {
          await flushSave();
          if (S.saveState === '保存失败') throw new Error('笔记尚未保存，请先保存后再删除');
        }
        await api(`/api/papers/${encodeURIComponent(slug)}`, { method: 'DELETE' });
        S.papers = S.papers.filter(p => p.slug !== slug);
        closeModal();
        if (S.slug === slug) { S.slug = null; S.paper = null; S.notes = null; location.hash = '#/'; }
        else renderCards();
        toast('整份记录已移入回收站，可恢复');
      } catch (err) { toast('删除失败：' + err.message); if (e.target.isConnected) e.target.disabled = false; }
    };
  });
}
async function openTrash() {
  try {
    const { items } = await api('/api/trash');
    openModal('回收站', `<p class="muted small">删除的整份阅读记录保留在本机，恢复后可以继续讨论、查看笔记与历史。</p>${items.length ? items.map(item => `<div class="trash-row"><div class="grow"><strong>${esc(item.title)}</strong><div class="muted small">${esc(fmtTime(item.deleted_at))} · ${item.kind === 'repo' ? '代码分析' : '论文 / 网站'}</div></div><button class="btn sm" data-restore="${esc(item.id)}">恢复</button></div>`).join('') : '<p class="muted">回收站为空。</p>'}`, body => {
      $$('[data-restore]', body).forEach(b => b.onclick = async () => {
        b.disabled = true;
        try {
          await api(`/api/trash/${encodeURIComponent(b.dataset.restore)}/restore`, { method: 'POST' });
          S.papers = (await api('/api/papers')).papers; renderCards(); await openTrash(); toast('已恢复整份阅读记录');
        } catch (err) { toast('恢复失败：' + err.message); if (b.isConnected) b.disabled = false; }
      });
    });
  } catch (err) { toast('读取回收站失败：' + err.message); }
}
function cardHtml(p) {
  const foot = `<div class="row"><div class="stations">${stationDots(p.progress)}</div><span class="grow"></span><span class="muted small">${p.progress.messages ? `${p.progress.messages} 条讨论 · ` : ''}${fmtTime(p.mtime)}</span><button class="icon-btn danger" data-delete-record aria-label="删除 ${esc(p.title)} 的整份记录">删除</button></div>`;
  if (p.kind === 'repo') {
    return `<article class="card repo" data-slug="${esc(p.slug)}" tabindex="0">
      <div class="card-top"><span class="kind-badge repo">代码库</span><span class="muted small src">${repoSource(p)}</span></div>
      <h3>${esc(p.title)}</h3>
      ${p.summary ? `<p class="abs">${esc(p.summary)}</p>` : ''}
      ${langBar(p.languages, 3)}
      <div class="row wrap">${p.stars != null ? `<span class="chip">★ ${fmtNum(p.stars)}</span>` : ''}<span class="chip">${fmtNum(p.n_files)} 文件</span><span class="chip">代码 ${fmtNum(p.n_code_lines)} 行</span>${p.commit ? `<span class="chip mono">${esc(p.commit.slice(0, 7))}</span>` : ''}${p.paper_title ? `<span class="chip" title="${esc(p.paper_title)}">论文代码</span>` : ''}</div>
      ${foot}</article>`;
  }
  return `<article class="card" data-slug="${esc(p.slug)}" tabindex="0">
      <div class="card-top"><span class="kind-badge ${p.kind === 'website' ? 'site' : 'paper'}">${p.kind === 'website' ? '网站' : '论文'}</span><span class="muted small src">${esc(authorsLine(p))}${p.published ? ' · ' + esc(p.published.slice(0, 10)) : ''}</span></div>
      <h3>${esc(p.title)}</h3>
      ${p.summary ? `<p class="abs">${esc(p.summary)}</p>` : ''}
      <div class="row wrap">${p.arxiv_id ? `<span class="chip">arXiv ${esc(p.arxiv_id)}</span>` : ''}
        <span class="chip">图表 ${p.figures}</span>${p.has_latex ? '<span class="chip">LaTeX</span>' : ''}${p.code ? '<span class="chip">有代码</span>' : ''}</div>
      ${foot}</article>`;
}
function renderCards() {
  const box = $('#cards'); if (!box) return;
  const q = S.query.trim().toLowerCase();
  const f = S.libFilter;
  const list = S.papers.filter(p => (f === 'all' || (f === 'repo') === (p.kind === 'repo'))
    && (!q || [p.title, p.arxiv_id, p.source_url, p.local_path, p.summary, ...(p.authors || []), ...(p.languages || []).map(l => l.name), ...(p.topics || [])]
      .join(' ').toLowerCase().includes(q)));
  const nr = S.papers.filter(p => p.kind === 'repo').length;
  $('#count').textContent = `${list.length} 项 · 论文 / 网站 ${S.papers.length - nr} · 代码库 ${nr}`;
  if (!list.length) {
    box.className = '';
    box.innerHTML = S.papers.length && (q || f !== 'all')
      ? '<div class="empty-lib"><h3>没有匹配的资料</h3><p>换个关键词，或者切到「全部」。</p></div>'
      : `<div class="empty-lib"><h3>${f === 'repo' ? '还没有代码库' : '还没有资料'}</h3><p>${f === 'repo'
        ? '在上面切到「代码仓库」，贴一个 GitHub 链接试试，比如 <code>https://github.com/pallets/flask</code>；或者填本机项目文件夹。'
        : '在上面贴一个 arXiv 链接试试，比如 <code>https://arxiv.org/abs/2410.24164</code>（π0）；读代码就切到「代码仓库」。'}</p></div>`;
    return;
  }
  box.className = 'cards';
  box.innerHTML = list.map(cardHtml).join('');
  $$('.card', box).forEach(c => {
    c.onclick = () => { location.hash = '#/p/' + encodeURIComponent(c.dataset.slug); };
    const del = $('[data-delete-record]', c);
    del.onclick = e => { e.stopPropagation(); const p = S.papers.find(p => p.slug === c.dataset.slug); deleteRecord(p.slug, p.title); };
    c.onkeydown = e => { if (e.target === c && e.key === 'Enter') c.onclick(); };
  });
}

/* ================= 工作台 ================= */
function codeHome() {
  const sub = S.paper?.meta?.subdir;
  return isRepo() && sub ? `code/${sub}` : 'code';
}
async function openPaper(slug) {
  const app = $('#app');
  const fresh = S.slug !== slug;
  app.innerHTML = '<div class="welcome"><span class="spinner"></span></div>';
  try { S.paper = await api('/api/papers/' + encodeURIComponent(slug)); }
  catch (e) { app.innerHTML = `<div class="welcome"><h3>打不开这份资料</h3><p>${esc(e.message)}</p><a class="btn" href="#/">回资料库</a></div>`; return; }
  const P = S.paper; setKind(P.kind);
  if (fresh) {
    Object.assign(S, { slug, attachments: [], editing: {}, drafts: {}, saveState: '', questionSearch: '', file: null, sel: null, symbols: null, symQuery: '',
      filePath: codeHome(), leftTab: store.get(isRepo() ? 'leftTab:repo' : 'leftTab', isRepo() ? 'overview' : 'pdf') });
  }
  S.notes = P.notes;
  if (!isRepo() && !P.meta.code_dir && !P.code_root && S.filePath.startsWith('code')) S.filePath = '';
  const talked = talkedSet();
  S.station = store.get('station:' + slug, null) || STATIONS.find(s => s.id !== 'free' && !talked.has(s.id))?.id || 'free';
  if (!ST[S.station]) S.station = '0';
  const m = P.meta;
  document.title = (m.title || slug) + (isRepo() ? ' · 代码分析' : ' · 精读');
  $('#crumbs').innerHTML = `<a href="#/">资料库</a> / ${isRepo() ? '代码库' : m.kind === 'website' ? '网站' : '论文'} / ${esc(m.title || slug)}`;
  let sub, extra = '';
  if (isRepo()) {
    const src = m.source_url || m.remote_url;
    sub = [src ? `<a href="${esc(src)}" target="_blank" rel="noopener">${esc(src.replace(/^https?:\/\/(www\.)?/, ''))}</a>` : esc(m.local_path || ''),
      m.subdir ? `子目录 ${esc(m.subdir)}` : '', m.branch ? esc(m.branch) : '', m.commit ? `<code>${esc(m.commit.slice(0, 7))}</code>` : '',
      (m.languages || []).slice(0, 2).map(l => esc(l.name)).join(' / '),
      m.paper_title && m.from_paper ? `<a href="#/p/${encodeURIComponent(m.from_paper)}">论文：${esc(m.paper_title)}</a>` : ''].filter(Boolean).join(' · ');
    extra = '<button class="btn sm hide-m" data-act="reanalyze" title="拉最新提交（克隆的仓库）并重新统计；讨论和笔记保留">重新分析</button>';
  } else {
    sub = [esc(authorsLine(m, 4)), m.published ? esc(m.published.slice(0, 10)) : '', m.arxiv_id ? `<a href="https://arxiv.org/abs/${esc(m.arxiv_id)}" target="_blank">arXiv ${esc(m.arxiv_id)}</a>` : '', m.official_code ? `<a href="${esc(m.official_code)}" target="_blank">代码</a>` : ''].filter(Boolean).join(' · ');
    if (P.repo_slug) extra = `<a class="btn sm hide-m" href="#/p/${encodeURIComponent(P.repo_slug)}" title="这篇的代码已经在代码分析器里">代码分析 →</a>`;
    else if (P.code_root || m.official_code) extra = '<button class="btn sm hide-m" data-act="analyze" title="把官方代码导入代码分析器，按七站读代码">用代码分析器读代码</button>';
  }
  app.innerHTML = `<div class="ws ${isRepo() ? 'is-repo' : 'is-paper'}">
    <div class="ws-head">
      <a class="btn ghost sm" href="#/" title="回资料库">←</a>
      <span class="kind-badge ${isRepo() ? 'repo' : m.kind === 'website' ? 'site' : 'paper'} hide-m">${isRepo() ? '代码库' : m.kind === 'website' ? '网站' : '论文'}</span>
      <div class="grow"><h2>${esc(m.title || slug)}</h2><div class="sub">${sub}</div></div>
      <span class="small muted hide-m">讨论自动保存到本机</span>
      ${extra}
      <button class="btn sm danger" data-act="delete-record">删除记录</button>
      <button class="btn sm" data-act="history">历史 / 对比</button>
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
    <nav class="mtabs">${[['left', isRepo() ? '代码' : '材料'], ['center', '讨论'], ['right', '问题 / 笔记']].map(([k, v]) => `<button data-m="${k}">${v}</button>`).join('')}</nav>
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

/* 后台任务弹窗：完成后跳到新资料，或刷新当前的 */
function jobModal(title, job, onDone) {
  openModal(title, '<div id="mjob"></div>');
  watchJob(job, () => $('#mjob'), async j => { if (j.status === 'done' && onDone) onDone(j); });
}
async function headAction(act) {
  const slug = encodeURIComponent(S.slug);
  if (act === 'delete-record') return deleteRecord(S.slug, S.paper.meta.title || S.slug);
  if (act === 'history') { await flushSave(); return openHistory(); }
  if (act === 'preview') { await flushSave(); window.open(`/api/papers/${slug}/notes/view`, '_blank'); }
  if (act === 'analyze') return analyzePaperCode();
  if (act === 'reanalyze') {
    try {
      const job = await api(`/api/papers/${slug}/reanalyze`, { method: 'POST' }); job.kind = 'repo';
      jobModal('重新分析代码', job, () => { S.symbols = null; openPaper(S.slug); toast('已重新分析'); });
    } catch (e) { toast('重新分析失败：' + e.message); }
  }
  if (act === 'export') {
    await flushSave();
    const nf = S.paper.note_file || '精读笔记.html';
    openModal(`导出${noteLabel()}（HTML）`, `
      <p style="margin-top:0">导出成一个<strong>单文件 HTML</strong>：图片都内嵌在文件里，发给别人、换台电脑直接用浏览器打开；浏览器里「打印 → 另存为 PDF」也能得到排好版的 PDF。</p>
      <p class="muted small">资料目录里一直有一份随时更新的 <code>${esc(nf)}</code>${isRepo() ? '' : '（图用相对路径，和 figures/ 放在一起时打开）'}。</p>
      <label class="check" style="margin:12px 0 6px"><input type="checkbox" id="exT">附上完整讨论记录（折叠在文末）</label>
      <label class="check"><input type="checkbox" id="exS" checked>同时在资料目录保存一份 <code>${esc(noteLabel())}-导出.html</code></label>
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
async function analyzePaperCode(url) {
  try {
    const job = await api(`/api/papers/${encodeURIComponent(S.slug)}/analyze-code`, { method: 'POST', json: typeof url === 'string' ? { url } : {} }); job.kind = 'repo';
    jobModal('用代码分析器打开官方代码', job, j => { if (j.slug) { closeModal(); location.hash = '#/p/' + encodeURIComponent(j.slug); } });
  } catch (e) { toast(e.message); }
}

/* ---------------- 左栏：材料 ---------------- */
const LEFT_TABS = [['pdf', 'PDF / 网页正文'], ['figs', '图表'], ['outline', '大纲'], ['files', '代码 / 文件'], ['info', '信息']];
const REPO_TABS = [['overview', '概览'], ['files', '代码'], ['symbols', '符号'], ['outline', '仓库地图'], ['info', '信息']];
function leftTabs() { return isRepo() ? REPO_TABS : LEFT_TABS; }
function renderLeft() {
  const el = $('#paneLeft'); if (!el) return; const P = S.paper;
  if (!leftTabs().some(([k]) => k === S.leftTab)) S.leftTab = leftTabs()[0][0];
  const n = (P.figures || []).filter(f => f.file).length;
  const count = k => (k === 'figs' ? ` <span class="muted small">${n}</span>` : k === 'symbols' && P.meta.n_symbols ? ` <span class="muted small">${fmtNum(P.meta.n_symbols)}</span>` : '');
  el.innerHTML = `<div class="pane-tabs">${leftTabs().map(([k, v]) => `<button data-tab="${k}" class="${S.leftTab === k ? 'on' : ''}">${v}${count(k)}</button>`).join('')}</div>
    <div class="pane-body" id="leftBody">
      ${isRepo() ? '' : `<iframe class="pdf-frame" id="pdfFrame" ${P.has_pdf ? `src="/files/${encodeURIComponent(S.slug)}/paper.pdf#view=FitH"` : ''} ${S.leftTab === 'pdf' ? '' : 'hidden'} title="PDF"></iframe>`}
      <div id="leftOther" ${S.leftTab === 'pdf' ? 'hidden' : ''}></div>
    </div>`;
  $$('.pane-tabs button', el).forEach(b => b.onclick = () => {
    if (b.dataset.tab === 'files' && S.leftTab === 'files' && S.file) { S.file = null; }  // 再点一次「代码」回到目录
    S.leftTab = b.dataset.tab; store.set(isRepo() ? 'leftTab:repo' : 'leftTab', S.leftTab); switchLeft();
  });
  switchLeft();
}
function switchLeft() {
  $$('#paneLeft .pane-tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.leftTab));
  const pdf = S.leftTab === 'pdf';
  const frame = $('#pdfFrame'); if (frame) frame.hidden = !pdf;
  const o = $('#leftOther'); o.hidden = pdf;
  if (pdf) {
    if (S.paper.meta.kind === 'website') {
      frame.hidden = true; o.hidden = false; renderWebsite(o);
    } else if (!S.paper.has_pdf) {
      frame.hidden = true; o.hidden = false; o.innerHTML = '<div class="pad muted">没有 paper.pdf</div>';
    }
    return;
  }
  ({ figs: renderFigs, outline: renderOutline, files: renderFiles, info: renderInfo, overview: renderOverview, symbols: renderSymbols })[S.leftTab](o);
}
function pdfPage(page) {
  S.leftTab = 'pdf'; switchLeft(); showMobile('left');
  const f = $('#pdfFrame'); f.src = `/files/${encodeURIComponent(S.slug)}/paper.pdf#page=${page}&view=FitH`;
}

function figLabel(f) { return (f.kind === 'table' ? '表 ' : '图 ') + f.num; }
async function renderWebsite(o) {
  const slug = S.slug;
  o.innerHTML = '<div class="pad muted">正在读取网页正文…</div>';
  try {
    const r = await api(`/api/papers/${encodeURIComponent(slug)}/text?path=website.md`);
    if (S.slug !== slug || S.leftTab !== 'pdf') return;
    // Escape first: imported HTML and Markdown never execute in this view.
    const links = githubResources(S.paper.meta);
    o.innerHTML = `<div class="pad">${links.length ? `<section class="repo-resources"><strong>从项目网站继续读代码</strong><p class="small muted">已发现 ${links.length} 个 GitHub 仓库链接，选择一份进入代码分析器。</p>${links.map(u => `<div class="resource-row"><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace('https://github.com/', ''))}</a><button class="btn sm" data-analyze-url="${esc(u)}">分析代码 →</button></div>`).join('')}</section>` : ''}<p class="muted">网站正文快照 · ${(S.paper.meta.sources || []).length} 页 · 资源链接见「信息」</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere;font:inherit">${esc(r.text)}</pre></div>`;
    bindRepoResources(o);
  } catch (e) { o.innerHTML = `<div class="pad muted">${esc(e.message)}</div>`; }
}
function renderFigs(o) {
  const figs = S.paper.figures || [];
  if (!figs.length) {
    if (S.paper.meta.kind === 'website') {
      o.innerHTML = '<div class="pad muted">没有可显示的网页图片。下载限制及失败原因见「信息」；可重新导入网站刷新材料。</div>';
    } else {
      o.innerHTML = `<div class="pad muted">没有裁出图表。<button class="btn sm" data-act="refig">重新裁图</button></div>`; bindRefig(o);
    }
    return;
  }
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
  if (S.paper.meta.kind === 'website') {
    $$('[data-act=contact], [data-act=refig], [data-fa=pdf], .tag.warn', o).forEach(b => b.hidden = true);
    $$('.fig .info .row .muted', o).forEach(b => b.textContent = '网页原图');
  }
}
function bindRefig(o) {
  const b = $('[data-act=refig]', o); if (!b) return;
  b.onclick = async () => {
    const job = await api(`/api/papers/${encodeURIComponent(S.slug)}/refigures`, { method: 'POST' });
    jobModal('重新裁图', job, async () => { const p = await api('/api/papers/' + encodeURIComponent(S.slug)); S.paper.figures = p.figures; S.paper.fig_dir = p.fig_dir; renderLeft(); });
  };
}

function renderOutline(o) {
  o.innerHTML = `<div class="pad md">${S.paper.outline ? md(S.paper.outline) : `<p class="muted">没有 outline.md</p>`}</div>`;
}

/* ---------------- 代码仓库：概览 / 符号 ---------------- */
function readmeImgBase(m) {
  const mm = (m.source_url || m.remote_url || '').match(/github\.com\/([\w.-]+)\/([\w.-]+?)(?:\.git)?$/i);
  if (!mm) return '';
  const ref = m.commit || m.branch || m.default_branch || 'HEAD';
  return `https://raw.githubusercontent.com/${mm[1]}/${mm[2]}/${ref}/${m.subdir ? m.subdir + '/' : ''}`;
}
async function renderOverview(o) {
  const m = S.paper.meta; const pre = codeHome() + '/';
  const stat = (n, l) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`;
  const ents = (m.entry_points || []).slice(0, 8);
  const mods = (m.top_modules || []).slice(0, 8);
  const deps = Object.entries(m.dependencies || {});
  o.innerHTML = `<div class="pad overview">
    ${m.summary ? `<p class="ov-summary">${esc(m.summary)}</p>` : ''}
    <div class="stats">${stat(fmtNum(m.n_files), '文件')}${stat(fmtNum(m.n_code_lines), '代码行')}${stat(fmtNum(m.n_symbols || 0), '符号')}${stat(fmtNum(m.tests?.files || 0), '测试文件')}</div>
    ${langBar(m.languages, 6)}
    <div class="row wrap" style="margin-top:10px">${m.stars != null ? `<span class="chip">★ ${fmtNum(m.stars)}</span>` : ''}${m.license ? `<span class="chip">${esc(m.license)}</span>` : ''}${(m.topics || []).slice(0, 6).map(t => `<span class="chip">${esc(t)}</span>`).join('')}${(m.ci || []).length ? '<span class="chip">有 CI</span>' : ''}${m.archived ? '<span class="chip warn">已归档</span>' : ''}</div>
    <h4>入口候选 <span class="muted small">脚本按规则猜的，点开核对</span></h4>
    ${ents.length ? `<ul class="ov-list">${ents.map(e => `<li><code class="code-ref" data-ref-path="${esc(pre + e.path)}" data-ref-line="${e.line}">${esc(e.path)}:${e.line}</code><span class="muted small">${esc(e.reason)}</span></li>`).join('')}</ul>` : '<p class="muted small">没识别出明显入口（可能是一个库，入口在使用方）。</p>'}
    ${(m.bins || []).length ? `<p class="small">声明的命令：${m.bins.slice(0, 8).map(b => `<code>${esc(b.name)}</code> → <code>${esc(b.target)}</code>`).join('，')}</p>` : ''}
    ${mods.length ? `<h4>被引用最多的模块 <span class="muted small">核心候选</span></h4><ul class="ov-list">${mods.map(x => `<li><code class="code-ref" data-ref-path="${esc(pre + x.path.replace(/\/$/, ''))}">${esc(x.path)}</code><span class="muted small">被 ${x.imported_by} 个文件引用</span></li>`).join('')}</ul>` : ''}
    ${deps.length ? `<h4>依赖</h4>${deps.slice(0, 6).map(([f, d]) => `<p class="small dep"><code class="code-ref" data-ref-path="${esc(pre + f)}">${esc(f)}</code> ${d.slice(0, 24).map(x => `<span class="tag">${esc(x)}</span>`).join(' ')}${d.length > 24 ? ` <span class="muted">… 共 ${d.length} 个</span>` : ''}</p>`).join('')}` : ''}
    <div class="row" style="margin:16px 0 4px"><button class="btn sm primary" data-ov="start">▶ 从概览开始讲</button><button class="btn sm" data-ov="map">看仓库地图</button></div>
    <h4>README</h4><div class="md readme" id="ovReadme"><p class="muted">${m.readme ? '读取中…' : '仓库里没有 README。'}</p></div></div>`;
  $('[data-ov=start]', o).onclick = () => { setStation('0', false); showMobile('center'); send(ST['0'].prompt, 'station'); };
  $('[data-ov=map]', o).onclick = () => { S.leftTab = 'outline'; switchLeft(); };
  if (!m.readme) return;
  const slug = S.slug;
  try {
    const r = await api(`/api/papers/${encodeURIComponent(slug)}/text?path=${encodeURIComponent(pre + m.readme)}`);
    if (S.slug !== slug || S.leftTab !== 'overview') return;
    const box = $('#ovReadme', o);
    box.innerHTML = /\.(md|markdown)$/i.test(m.readme) || !m.readme.includes('.') ? md(r.text, slug, { imgBase: readmeImgBase(m) }) : `<pre>${esc(r.text)}</pre>`;
    $$('img', box).forEach(img => img.onclick = () => lightbox(img.src, img.alt));
  } catch (e) { $('#ovReadme', o).innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}

const SYM_KIND = { class: '类', def: '函数', method: '方法', function: '函数', func: '函数', fn: '函数', fun: '函数', struct: '结构', interface: '接口',
  type: '类型', enum: '枚举', trait: 'trait', impl: 'impl', mod: '模块', namespace: '命名空间', record: 'record', object: 'object' };
async function renderSymbols(o) {
  if (!S.symbols) {
    o.innerHTML = '<div class="pad muted">读取符号索引…</div>';
    try { S.symbols = await api(`/api/papers/${encodeURIComponent(S.slug)}/symbols`); } catch (e) { o.innerHTML = `<div class="pad muted">${esc(e.message)}</div>`; return; }
    if (S.leftTab !== 'symbols') return;
  }
  const files = Object.entries(S.symbols.files || {});
  o.innerHTML = `<div class="sym-bar"><input type="search" id="symQ" placeholder="搜索类 / 函数 / 文件名…" value="${esc(S.symQuery || '')}" aria-label="搜索符号"><span class="muted small" id="symCount"></span></div><div id="symList" class="sym-list"></div>`;
  const draw = () => {
    const q = (S.symQuery || '').trim().toLowerCase(); let shown = 0; const LIMIT = 600; const out = [];
    for (const [f, syms] of files) {
      const fileHit = !q || f.toLowerCase().includes(q);
      const hits = fileHit ? syms : syms.filter(x => x.name.toLowerCase().includes(q));
      if (!hits.length) continue;
      if (shown >= LIMIT) break;
      out.push(`<div class="sym-file"><button class="sym-fname" data-p="${esc(f)}">${esc(f)}</button><span class="muted small">${hits.length}</span></div>`);
      for (const x of hits.slice(0, q ? 200 : 40)) {
        out.push(`<button class="sym ${x.kind === 'method' ? 'sub' : ''}" data-p="${esc(f)}" data-l="${x.line}"><span class="sym-k k-${esc(x.kind)}">${esc(SYM_KIND[x.kind] || x.kind)}</span><span class="sym-n">${esc(x.name)}<span class="muted">${esc(x.sig || '')}</span></span><span class="muted small">L${x.line}</span></button>`);
        shown++;
      }
      if (!q && hits.length > 40) out.push(`<div class="muted small sym-more">… 还有 ${hits.length - 40} 个，搜索名字看全部</div>`);
    }
    if (!$('#symList', o)) return;
    $('#symList', o).innerHTML = out.join('') || `<div class="pad muted">${files.length ? '没有匹配的符号。' : '没有提取到符号（可能是不支持的语言，或者文件太大）。'}</div>`;
    $('#symCount', o).textContent = q ? `匹配 ${shown}${shown >= LIMIT ? '+' : ''}` : `${files.length} 个文件`;
    $$('[data-p]', $('#symList', o)).forEach(b => b.onclick = () => openFileAt(S.symbols.prefix.replace(/\/$/, '') + '/' + b.dataset.p, b.dataset.l ? +b.dataset.l : null));
  };
  $('#symQ', o).oninput = e => { S.symQuery = e.target.value; draw(); };
  draw();
}

/* ---------------- 代码 / 文件 ---------------- */
async function renderFiles(o) {
  const slug = encodeURIComponent(S.slug);
  if (S.file) return renderFileView(o);
  const home = isRepo() ? codeHome() : 'code';
  const roots = isRepo() ? [[home, '代码'], ['', '分析目录']] : [['code', '代码'], ['', '论文目录']];
  const inCode = p => p === home || p.startsWith('code/') || p === 'code';
  o.innerHTML = `<div class="code-nav">${roots.map(([p, l]) => `<button class="btn sm ${(p ? inCode(S.filePath) : !inCode(S.filePath)) ? 'primary' : ''}" data-root="${p}">${l}</button>`).join('')}
      <span class="muted small grow" id="crumb"></span>${!isRepo() && (S.paper.code_root || S.paper.meta.official_code) ? `<button class="btn sm ghost" data-act="analyze" title="在代码分析器里按七站读这份代码">代码分析器 →</button>` : ''}</div><ul class="tree" id="tree"><li class="muted">读取中…</li></ul>`;
  $$('[data-root]', o).forEach(b => b.onclick = () => { S.filePath = b.dataset.root; renderFiles(o); });
  const an = $('[data-act=analyze]', o); if (an) an.onclick = () => (S.paper.repo_slug ? (location.hash = '#/p/' + encodeURIComponent(S.paper.repo_slug)) : analyzePaperCode());
  let r; const gen = S.filesGen = (S.filesGen || 0) + 1;
  try { r = await api(`/api/papers/${slug}/tree?path=${encodeURIComponent(S.filePath)}`); } catch (e) { r = { error: e.message, items: [] }; }
  if (gen !== S.filesGen || S.file || !$('#tree', o)) return;  // 等待期间已经打开了别的文件 / 换了目录
  if (r.error) {
    $('#tree', o).innerHTML = `<li class="muted" style="cursor:default;display:block">${esc(r.error)}${!isRepo() && S.filePath.startsWith('code') ? '<br><br>论文里没找到官方代码时，可以自己搜到仓库地址补上：<div class="row" style="margin-top:8px"><input id="codeUrl" placeholder="https://github.com/…"><button class="btn sm primary" id="codeGo">克隆</button></div>' : ''}${isRepo() ? '<br><br>代码目录可能被移动或删除了，点顶上的「重新分析」或回资料库重新导入。' : ''}</li>`;
    const go = $('#codeGo', o);
    if (go) go.onclick = async () => {
      const url = $('#codeUrl').value.trim(); if (!url) return;
      const job = await api(`/api/papers/${slug}/code`, { method: 'POST', json: { url } });
      jobModal('补官方代码', job, async () => { S.paper = await api('/api/papers/' + slug); renderFiles(o); });
    };
    return;
  }
  $('#crumb', o).textContent = r.path || (isRepo() ? '分析目录' : '论文目录');
  const parent = S.filePath.includes('/') ? S.filePath.slice(0, S.filePath.lastIndexOf('/')) : '';
  const atTop = !S.filePath || S.filePath === 'code';
  const items = (atTop ? [] : [{ name: '..', path: parent, dir: true, up: true }]).concat(r.items);
  $('#tree', o).innerHTML = items.map((it, i) => `<li data-i="${i}" tabindex="0"><span class="ic">${it.up ? '↑' : it.dir ? '▸' : fileIcon(it.name)}</span><span class="grow">${esc(it.name)}</span>${it.size != null ? `<span class="muted small">${it.size > 1024 ? (it.size / 1024).toFixed(0) + ' KB' : it.size + ' B'}</span>` : ''}</li>`).join('') || '<li class="muted">空目录</li>';
  $$('#tree li[data-i]', o).forEach(li => {
    li.onclick = () => {
      const it = items[li.dataset.i];
      if (it.dir) { S.filePath = it.path; renderFiles(o); }
      else if (/\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(it.name)) lightbox(`/api/papers/${slug}/raw?path=${encodeURIComponent(it.path)}`, it.path);
      else if (/\.pdf$/i.test(it.name)) window.open(`/api/papers/${slug}/raw?path=${encodeURIComponent(it.path)}`, '_blank');
      else openFile(it.path, o);
    };
    li.onkeydown = e => { if (e.key === 'Enter') li.onclick(); };
  });
}
function fileIcon(name) {
  const ext = (name.split('.').pop() || '').toLowerCase();
  if (EXT_HL[ext] || ['md', 'rst', 'txt'].includes(ext)) return `<i class="fdot" style="background:${langColor({ py: 'Python', js: 'JavaScript', ts: 'TypeScript', tsx: 'TypeScript', go: 'Go', rs: 'Rust', java: 'Java', cpp: 'C++', cc: 'C++', c: 'C', h: 'C', cu: 'CUDA', sh: 'Shell', html: 'HTML', css: 'CSS', vue: 'Vue', kt: 'Kotlin', rb: 'Ruby', md: 'Markdown' }[ext] || ext)}"></i>`;
  return '·';
}
async function openFile(path, o, focus) {
  try {
    S.filesGen = (S.filesGen || 0) + 1;
    const r = await api(`/api/papers/${encodeURIComponent(S.slug)}/text?path=${encodeURIComponent(path)}`);
    S.file = r; S.sel = focus || null;
    if (r.path.includes('/')) S.filePath = r.path.slice(0, r.path.lastIndexOf('/'));
    renderFileView(o || $('#leftOther'), !!focus);
  } catch (e) { toast('打不开：' + e.message); }
}
/* 从讨论 / 符号 / 概览跳到某个文件的某几行 */
async function openFileAt(path, line, end) {
  if (!S.slug) return;
  S.leftTab = 'files'; store.set(isRepo() ? 'leftTab:repo' : 'leftTab', 'files');
  switchLeft(); showMobile('left');
  const o = $('#leftOther');
  const focus = line ? { a: line, b: end && end >= line ? Math.min(end, line + 400) : line } : null;
  if (S.file && S.file.path === path) { S.sel = focus; renderFileView(o, !!focus); return; }
  if (/\/$/.test(path) || !/\.[\w]+$/.test(path.split('/').pop()) && !/^(Makefile|Dockerfile|LICENSE|README)$/i.test(path.split('/').pop())) {
    try {  // 目录
      const r = await api(`/api/papers/${encodeURIComponent(S.slug)}/tree?path=${encodeURIComponent(path.replace(/\/$/, ''))}`);
      if (!r.error) { S.file = null; S.filePath = path.replace(/\/$/, ''); return renderFiles(o); }
    } catch { /* 当文件试 */ }
  }
  await openFile(path, o, focus);
}
function renderFileView(o, scrollToSel) {
  const lines = S.file.text.split('\n');
  const html = S.file.big ? lines.map(esc) : highlightLines(S.file.text, S.file.path);
  o.innerHTML = `<div class="code-bar"><button class="btn sm" data-act="back" title="返回目录">←</button><strong class="grow fpath">${esc(S.file.path)}</strong>
      <span class="muted" id="selInfo"></span>
      <button class="btn sm" data-act="copy-code">复制代码</button>
      <button class="btn sm" data-act="explain" title="附上选中的行，让 AI 讲解">讲讲这段</button>
      <button class="btn sm primary" data-act="attach">附到提问</button></div>
    <pre class="codeview hl">${html.map((l, i) => `<span class="l" data-n="${i + 1}"><span class="n">${i + 1}</span>${l}</span>`).join('')}</pre>`;
  const upd = () => {
    const [a, b] = S.sel ? [Math.min(S.sel.a, S.sel.b), Math.max(S.sel.a, S.sel.b)] : [0, -1];
    $$('.codeview .l', o).forEach(l => { const n = +l.dataset.n; l.classList.toggle('sel', n >= a && n <= b); });
    $('#selInfo', o).textContent = S.sel ? `已选 L${a}–${b}（${b - a + 1} 行）` : `共 ${lines.length} 行 · 点行号选起点，Shift+点选终点`;
  };
  $$('.codeview .n', o).forEach(n => n.onclick = e => {
    const k = +n.parentElement.dataset.n;
    S.sel = e.shiftKey && S.sel ? { a: S.sel.a, b: k } : { a: k, b: k }; upd();
  });
  $('[data-act=copy-code]', o).onclick = () => {
    const selected = S.sel ? lines.slice(Math.min(S.sel.a, S.sel.b) - 1, Math.max(S.sel.a, S.sel.b)).join('\n') : S.file.text;
    copyContent(selected);
  };
  $('[data-act=back]', o).onclick = () => { S.file = null; renderFiles(o); };
  const attach = () => {
    let a = 1, b = lines.length;
    if (S.sel) { a = Math.min(S.sel.a, S.sel.b); b = Math.max(S.sel.a, S.sel.b); }
    if (b - a > 400) { b = a + 399; toast('一次最多附 400 行，已截到 L' + a + '–' + b); }
    addAttachment({ type: 'code', path: S.file.path, start: a, end: b, text: lines.slice(a - 1, b).join('\n'), label: `${S.file.path.split('/').pop()}:${a}–${b}` });
    showMobile('center');
  };
  $('[data-act=attach]', o).onclick = attach;
  $('[data-act=explain]', o).onclick = () => {
    if (!S.sel) return toast('先点行号选中要讲的几行（Shift+点选终点）');
    attach(); send(isRepo() ? '讲讲附上的这段代码：它在整个项目里扮演什么角色、被谁调用、关键几行在干什么。' : '讲讲附上的这段代码，对应论文里的哪一部分？关键几行在干什么。');
  };
  upd();
  if (scrollToSel && S.sel) {
    const el = $(`.codeview .l[data-n="${Math.min(S.sel.a, S.sel.b)}"]`, o);
    if (el) requestAnimationFrame(() => { const body = $('#leftBody'); body.scrollTop = Math.max(0, el.offsetTop - body.clientHeight / 3); });
  }
}

function renderInfo(o) {
  const m = S.paper.meta;
  if (isRepo()) {
    const row = (k, v) => (v ? `<tr><th>${k}</th><td>${v}</td></tr>` : '');
    const src = m.source_url || m.remote_url;
    o.innerHTML = `<div class="pad">
      <h3 style="margin-top:0">${esc(m.title)}</h3>
      ${m.summary ? `<p>${esc(m.summary)}</p>` : ''}
      <table class="kv">${row('来源', src ? `<a href="${esc(src)}" target="_blank" rel="noopener">${esc(src)}</a>` : '')}
        ${row('本机文件夹', m.local_path ? `<code>${esc(m.local_path)}</code>（只读分析，不复制）` : '')}
        ${row('代码位置', `<code>${esc(S.paper.code_root || '找不到')}</code>`)}
        ${row('子目录', m.subdir ? `<code>${esc(m.subdir)}</code>` : '')}
        ${row('分支 / 提交', [m.branch, m.commit ? `<code>${esc(m.commit)}</code>` : ''].filter(Boolean).join(' · '))}
        ${row('许可证', esc(m.license || ''))}
        ${row('最近推送', esc((m.pushed_at || '').slice(0, 10)))}
        ${row('分析于', esc(m.fetched || ''))}
        ${row('对应论文', m.from_paper ? `<a href="#/p/${encodeURIComponent(m.from_paper)}">${esc(m.paper_title || m.from_paper)}</a>` : '')}
        ${row('依赖清单', (m.manifests || []).map(f => `<code>${esc(f)}</code>`).join(' '))}
        ${row('CI', (m.ci || []).map(f => `<code>${esc(f)}</code>`).join(' '))}
        ${row('文档', (m.docs || []).slice(0, 8).map(f => `<code>${esc(f)}</code>`).join(' '))}</table>
      ${(m.largest || []).length ? `<h4>最大的源文件</h4><ul class="ov-list">${m.largest.slice(0, 8).map(x => `<li><code class="code-ref" data-ref-path="${esc(codeHome() + '/' + x.path)}">${esc(x.path)}</code><span class="muted small">${fmtNum(x.lines)} 行</span></li>`).join('')}</ul>` : ''}
      ${(m.warnings || []).length ? `<h4>导入记录</h4><ul>${m.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
      <h4>分析目录</h4><p><code style="word-break:break-all">${esc(S.paper.path)}</code></p>
      <p class="muted small">讨论、笔记、历史版本都存在分析目录里；代码只读，网页端和模型都不会改动它。</p>
      <button class="btn sm" data-act="reanalyze">重新分析</button></div>`;
    $('[data-act=reanalyze]', o).onclick = () => headAction('reanalyze');
    return;
  }
  const links = m.links || {};
  const linkList = Object.entries(links).flatMap(([k, v]) => Array.isArray(v) ? v.slice(0, 4).map(x => [k, x.url]) : []);
  o.innerHTML = `<div class="pad">
    <h3 style="margin-top:0">${esc(m.title)}</h3>
    <p class="muted small">${esc((m.authors || []).join('、'))}</p>
    <div class="row wrap" style="margin:8px 0 14px">${m.published ? `<span class="chip">${esc(m.published.slice(0, 10))}</span>` : ''}${m.arxiv_id ? `<span class="chip">arXiv ${esc(m.arxiv_id)}</span>` : ''}${m.pdf_pages ? `<span class="chip">${m.pdf_pages} 页</span>` : ''}<span class="chip">${m.has_latex ? '有 LaTeX 源码' : '无 LaTeX 源码'}</span>${m.fetched ? `<span class="chip">拉取于 ${esc(m.fetched)}</span>` : ''}</div>
    ${m.summary ? `<h4>摘要</h4><p style="text-align:justify">${esc(m.summary)}</p>` : ''}
    ${m.comment || m.journal_ref ? `<p class="muted small">${esc([m.journal_ref, m.comment].filter(Boolean).join(' · '))}</p>` : ''}
    <h4>代码</h4><p>${m.official_code ? `<a href="${esc(m.official_code)}" target="_blank">${esc(m.official_code)}</a> <span class="muted small">（来自${esc(m.official_code_from || '')}）</span><br><span class="muted small">本地：${esc(S.paper.code_root || '没克隆')}</span>` : '<span class="muted">没找到官方代码，可以在「代码 / 文件」里补。</span>'}</p>
    ${S.paper.repo_slug ? `<p><a class="btn sm" href="#/p/${encodeURIComponent(S.paper.repo_slug)}">在代码分析器里继续 →</a></p>` : (S.paper.code_root || m.official_code) ? '<p><button class="btn sm" data-act="analyze">用代码分析器读这份代码</button> <span class="muted small">按概览 → 结构 → 入口 → 主流程…七站读代码</span></p>' : ''}
    ${linkList.length ? `<h4>链接</h4><ul>${linkList.map(([k, u]) => `<li><span class="tag">${esc(k)}</span> <a href="${esc(u)}" target="_blank">${esc(u)}</a></li>`).join('')}</ul>` : ''}
    ${(m.sources || []).length ? `<h4>已抓取页面</h4><ul>${m.sources.map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></li>`).join('')}</ul>` : ''}
    ${(m.warnings || []).length ? `<h4>导入记录</h4><ul>${m.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}
    <h4>材料目录</h4><p><code style="word-break:break-all">${esc(S.paper.path)}</code></p></div>`;
  const an = $('[data-act=analyze]', o); if (an) an.onclick = analyzePaperCode;
  const codeLinks = githubResources(m);
  if (codeLinks.length) {
    const section = document.createElement('section'); section.className = 'repo-resources';
    section.innerHTML = `<strong>代码仓库 · 直接分析</strong>${codeLinks.map(u => `<div class="resource-row"><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace('https://github.com/', ''))}</a><button class="btn sm" data-analyze-url="${esc(u)}">分析代码 →</button></div>`).join('')}`;
    $('.pad', o).append(section); bindRepoResources(o);
  }
}

function githubResources(meta) {
  const candidates = [meta.official_code, ...Object.values(meta.links || {}).flat().map(x => typeof x === 'string' ? x : x?.url)];
  return [...new Set(candidates.filter(u => typeof u === 'string' && /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(?:\/?(?:[?#].*)?|\/tree\/[^\s]+)$/i.test(u)))];
}
function bindRepoResources(el) {
  $$('[data-analyze-url]', el).forEach(b => b.onclick = () => analyzePaperCode(b.dataset.analyzeUrl));
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
        <textarea id="input" rows="2" placeholder="${isRepo() ? '问任何关于这个仓库的问题，或在左侧选中几行代码附上…' : '问任何问题，或复述你的理解让它判对错…'}  （Enter 发送，Shift+Enter 换行）"></textarea>
        <div class="bar"><div class="quick">${QUICK.map(([l], i) => `<button class="chip" data-q="${i}">${l}</button>`).join('')}</div><span class="grow"></span>
          <button class="btn sm" id="questionIndexBtn">问题索引</button><button class="btn primary" id="sendBtn">发送</button></div></div></div>`;
  renderStbar(); renderMsgs(); renderNext(); renderAtt();
  $('#msgs').addEventListener('scroll', queueQuestionSync, { passive: true });
  $('#questionIndexBtn').onclick = () => {
    showMobile('right');
    $('#questionIndex').open = true;
    $('#questionSearch').focus({ preventScroll: true });
  };
  const input = $('#input');
  input.oninput = () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 220) + 'px'; };
  input.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } };
  $('#sendBtn').onclick = () => S.ctrl ? stop() : send();
  $$('[data-q]', el).forEach(b => b.onclick = () => {
    const [, text, pos] = QUICK[b.dataset.q];
    if (pos != null) { input.value = text; input.focus(); input.setSelectionRange(pos, pos); } else send(text);
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
  if (cur.id !== 'free' && !t.has(cur.id)) html += `<button class="btn primary sm" data-go="${cur.id}">▶ ${cur.id === '0' ? (isRepo() ? '开始：项目概览 + ① 定位' : '开始：基本情况 + ① 动机') : '开讲 ' + cur.label}</button>`;
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
  const tools = (m.tools || []).length ? `<details class="tools"><summary>查阅了 ${m.tools.length} 处${isRepo() ? '代码 / 文件' : '原文 / 代码 / 图'}</summary><ul>${m.tools.map(t => `<li>${esc(t)}</li>`).join('')}</ul></details>` : '';
  const body = m.role === 'user' ? `<div class="bubble">${esc(m.content)}${att}</div>`
    : `<div class="bubble">${tools}<div class="md">${md(m.content)}</div>${m.error ? `<div class="err">出错了：${esc(m.error)}</div>` : ''}</div>`;
  const acts = m.role === 'user'
    ? `<button class="icon-btn" data-ma="del" title="删除">删除</button>`
    : `<button class="icon-btn" data-ma="copy">复制</button><button class="icon-btn" data-ma="qa" title="把这组问答压成一条记进笔记「问答」">记入问答</button>${last ? '<button class="icon-btn" data-ma="regen">重新生成</button>' : ''}<button class="icon-btn" data-ma="del">删除</button>`;
  return `<div class="msg ${m.role} ${last ? 'last' : ''}" tabindex="-1" data-id="${esc(m.id)}" data-st="${esc(m.station)}">
    <div class="mhead">${m.role === 'user' ? '' : '<strong>AI</strong>'}<span>${esc(st)}</span><span>${fmtTime(m.ts)}</span></div>${body}<div class="macts">${acts}</div></div>`;
}
function renderMsgs(keepScroll) {
  const box = $('#msgs'); const msgs = S.paper.messages;
  if (!msgs.length) {
    const mock = S.settings?.provider === 'mock';
    const m = S.paper.meta;
    box.innerHTML = isRepo() ? `<div class="welcome"><h3>代码材料已经就绪</h3>
      <p class="small">${fmtNum(m.n_files)} 个文件 · 代码 ${fmtNum(m.n_code_lines)} 行 · 入口候选 ${(m.entry_points || []).length} 个 · 符号 ${fmtNum(m.n_symbols || 0)} 个</p>
      <ol class="route">${REPO_STATIONS.slice(0, 8).map(s => `<li>${esc(s.label)}</li>`).join('')}</ol>
      <p>一次讲一站，每个结论都带 <code>code/文件:行号</code>，点一下就在左边打开那几行。随时可以打断提问，或者在左侧选中代码让它讲。</p>
      ${mock ? '<p class="err" style="text-align:left">现在是演示模式，回复是占位的。到右上角「设置」里选好模型再开始。</p>' : ''}
      <button class="btn primary" data-start>▶ 开始：项目概览 + ① 定位</button></div>`
      : `<div class="welcome"><h3>材料已经就绪</h3>
      <p>按 SKILL.md 的六站带读：① 动机 → ② 架构 → ③ 训练 → ④ 数据 → ⑤ 信息流 → ⑥ 例子走一遍（可选 ⑦ 实验）。每站讲完会问要不要继续，随时可以打断提问。</p>
      ${mock ? '<p class="err" style="text-align:left">现在是演示模式，回复是占位的。到右上角「设置」里填上模型和 API Key 再开始。</p>' : ''}
      <button class="btn primary" data-start>▶ 开始：基本情况 + ① 动机</button></div>`;
    $('[data-start]', box).onclick = () => { setStation('0', false); send(ST['0'].prompt, 'station'); };
    renderQuestionIndex();
    return;
  }
  const previousScroll = box.scrollTop;
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  box.innerHTML = msgs.map((m, i) => msgHtml(m, i, msgs.length)).join('');
  bindMsgs(box);
  box.scrollTop = !keepScroll || atBottom ? box.scrollHeight : previousScroll;
  renderQuestionIndex();
}

/* 侧栏索引来自已保存的用户消息，重开资料时自动恢复。 */
function renderQuestionIndex() {
  const list = $('#questionList'); if (!list) return;
  const questions = (S.paper?.messages || []).filter(m => m.role === 'user');
  const query = S.questionSearch.trim().toLowerCase();
  const entries = questions.map((m, i) => ({ m, number: i + 1,
    title: (m.content || ((m.images || []).length ? '关于附图的提问' : '关于所附资料的提问')).replace(/\s+/g, ' ').trim() }));
  const shown = entries.filter(({ m, title }) => !query || `${title} ${ST[m.station]?.label || ''}`.toLowerCase().includes(query));
  $('#questionCount').textContent = query ? `${shown.length} / ${questions.length}` : questions.length;
  list.innerHTML = shown.map(({ m, number, title }) => `<li><button class="question-link" data-question="${esc(m.id)}" title="${esc(title)}"><span class="question-number">${number}</span><span class="question-copy"><span class="question-title">${esc(title)}</span><span class="question-meta">${esc(ST[m.station]?.label || '讨论')} · ${esc(fmtTime(m.ts))}</span></span></button></li>`).join('')
    || `<li class="small muted question-empty">${questions.length ? '没有匹配的问题。' : '提问后会自动生成索引，点击即可回看。'}</li>`;
  $$('[data-question]', list).forEach(button => button.onclick = () => jumpToQuestion(button.dataset.question));
  queueQuestionSync();
}
function jumpToQuestion(id) {
  const box = $('#msgs');
  const target = $$('.msg.user', box).find(el => el.dataset.id === id);
  if (!target) return toast('该问题已不在当前讨论中，可在历史中回看。');
  showMobile('center');
  if (ST[target.dataset.st]) setStation(target.dataset.st, false);
  $$('.question-focus', box).forEach(el => el.classList.remove('question-focus'));
  target.classList.add('question-focus');
  target.focus({ preventScroll: true });
  box.scrollTo({ top: Math.max(0, target.offsetTop - 12), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  markCurrentQuestion(id);
}
function markCurrentQuestion(id) {
  $$('#questionList [data-question]').forEach(button => {
    if (button.dataset.question === id) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  });
}
function queueQuestionSync() {
  if (S.questionFrame) cancelAnimationFrame(S.questionFrame);
  S.questionFrame = requestAnimationFrame(() => {
    S.questionFrame = null;
    const box = $('#msgs'); if (!box || !box.clientHeight) return;
    const questions = $$('.msg.user', box);
    const current = questions.filter(el => el.offsetTop <= box.scrollTop + 40).pop() || questions[0];
    if (current) markCurrentQuestion(current.dataset.id);
  });
}
function bindMsgs(box) {
  $$('.md img, [data-zoom]', box).forEach(img => img.onclick = () => lightbox(img.src, img.alt));
  $$('[data-ma]', box).forEach(b => b.onclick = async () => {
    const el = b.closest('.msg'); const id = el.dataset.id; const m = S.paper.messages.find(x => x.id === id);
    const act = b.dataset.ma;
    if (act === 'copy') { if (m) await copyContent(m.content); }
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
    const tools = live.tools.length ? `<details class="tools"><summary>查阅了 ${live.tools.length} 处${isRepo() ? '代码 / 文件' : '原文 / 代码 / 图'}</summary><ul>${live.tools.map(t => `<li>${esc(t)}</li>`).join('')}</ul></details>` : '';
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
      renderMsgs(true); renderStbar(); renderNext();
    }
  }
}

/* ---------------- 右栏：精读笔记 ---------------- */
function sectionTitle(key) { return (S.paper.sections.find(([k]) => k === key) || [key, key])[1]; }
function renderNotes() {
  const el = $('#paneRight');
  const imported = S.notes.imported_from ? `<div class="pad small muted" style="padding-bottom:0">已从 ${esc(S.notes.imported_from)} 读入笔记内容。</div>` : '';
  el.innerHTML = `<details class="question-index" id="questionIndex" ${store.get('questionIndexOpen', true) ? 'open' : ''}>
      <summary><strong>问题索引</strong><span class="chip" id="questionCount">0</span><span class="muted small">点击跳转</span></summary>
      <div class="question-index-body"><input type="search" id="questionSearch" aria-label="搜索问题索引" placeholder="搜索问题或站点…" value="${esc(S.questionSearch)}"><nav aria-label="讨论问题索引"><ol id="questionList"></ol></nav></div>
    </details><div class="notes-head"><h3>${noteLabel()}</h3><span class="save-state" id="saveState">${esc(S.saveState)}</span>
      <button class="btn sm ghost" data-act="collapse" title="全部折叠 / 展开">⇅</button>
      <button class="btn sm" data-act="preview">预览</button></div>${imported}
    <div class="pane-body"><div class="nsecs" id="nsecs">${S.paper.sections.map(([k]) => secHtml(k)).join('')}</div></div>`;
  $('[data-act=preview]', el).onclick = () => headAction('preview');
  $('[data-act=collapse]', el).onclick = () => {
    const allC = S.paper.sections.every(([k]) => S.collapsed[k]);
    S.paper.sections.forEach(([k]) => { S.collapsed[k] = !allC; }); renderNotes();
  };
  bindSecs(el);
  $('#questionIndex').ontoggle = e => store.set('questionIndexOpen', e.target.open);
  $('#questionSearch').oninput = e => { S.questionSearch = e.target.value; renderQuestionIndex(); };
  renderQuestionIndex();
}
function secHtml(key) {
  const text = S.notes.sections[key] || ''; const ed = S.editing[key]; const d = S.drafts[key];
  const filled = text.trim() ? 'filled' : '';
  const focus = ST[S.station]?.note === key ? 'focus' : '';
  const isStation = /^s\d$|^basic$|^map$|^code$|^qa$/.test(key);
  let body;
  if (ed) body = `<textarea data-ta="${key}" spellcheck="false">${esc(text)}</textarea><div class="row" style="margin-top:6px"><span class="muted small grow">${isRepo() ? 'Markdown；代码位置写 `code/路径:行号`，预览里可点击跳转' : 'Markdown；图用 ![说明](figures/fig-03.png)'}</span><button class="btn sm primary" data-sa="done">完成</button></div>`;
  else body = text.trim() ? `<div class="md">${md(text)}</div>` : `<div class="nsec-empty">${key === 'qa' ? '在讨论里点某条回复下面的「记入问答」，或让 AI 从全部讨论里整理。' : key === 'code' && isRepo() ? '讲过几站后点「AI 整理」，生成一张关键文件索引。' : '还没整理。讲完这一站后点「AI 整理」，或者点「编辑」自己写。'}</div>`;
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
  if (!S.saveTimer && !['未保存', '保存失败'].includes(S.saveState)) return;
  clearTimeout(S.saveTimer); S.saveTimer = null; setSaveState('保存中…');
  try {
    const r = await api(`/api/papers/${encodeURIComponent(S.slug)}/notes`, { method: 'PUT', json: { sections: S.notes.sections } });
    S.notes.updated = r.updated; delete S.notes.imported_from;
    const d = new Date(); setSaveState(`已保存 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} · ${S.paper?.note_file || '精读笔记.html'}`);
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
