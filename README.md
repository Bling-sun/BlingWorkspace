# Bling-Workspace

**简体中文** | [English](README.en.md)

一个给研究者用的本地工作台：**论文精读** + **代码分析**。它不给你一段摘要了事，而是像一个已经读懂的人，一站一站带你看——
读论文时讲到哪张图就把图发给你，读代码时每个结论都带 `code/文件:行号`，点一下就跳到那几行。

| | 论文精读 | 代码分析 |
|---|---|---|
| 丢给它 | arXiv 链接 / PDF / 论文主页、项目网站 | GitHub / Git 链接，或者**本机代码文件夹** |
| 它先备好 | PDF、LaTeX 源码、裁好的每张图、官方代码 | 浅克隆（本机文件夹不复制）、语言统计、入口候选、符号索引、模块依赖、依赖清单 |
| 怎么带你读 | 六站：① 动机 → ② 架构 → ③ 训练 → ④ 数据 → ⑤ 信息流 → ⑥ 例子（可选 ⑦ 实验） | 七站：概览 → ① 定位 → ② 结构 → ③ 入口 → ④ 数据 → ⑤ 主流程 → ⑥ 例子 → ⑦ 工程 |
| 记下来 | `精读笔记.html` | `代码分析笔记.html` |
| 流程说明 | `SKILL.md` | `references/code-reading.md` |

两者是打通的：论文工作区里点「用代码分析器读代码」，就把这篇的官方代码导进代码分析器（已经克隆过的直接分析本地那份），
讲 ②⑤⑥ 时会指出论文里的模块对应到哪段代码；代码分析器顶上也有链接跳回论文。

## 快速开始（网页端）

项目文件夹统一命名为 **`Bling-Workspace`**。已有项目直接使用根目录的启动脚本；首次下载可执行：

```bash
git clone https://github.com/Bling-sun/bling-paper-reading.git Bling-Workspace
cd Bling-Workspace
```

网页首页提供 **论文阅读器 / 代码分析器** 两个入口，共用资料库、讨论、笔记与历史。

**Windows**：双击根目录的 `start.bat`（没有 Python 会帮你装），浏览器自动打开 http://127.0.0.1:8765 。
**macOS / Linux**：`./start.sh`。详见 [web/README.md](web/README.md)。

模型可以直接用 Claude / ChatGPT 会员（调用本机 Claude Code / Codex，免 API Key），也可以用 DeepSeek、Claude API、任意 OpenAI 兼容接口。

### 读一篇论文

资料库顶上「导入」选 **论文 / 网站**，贴 arXiv 链接、PDF 直链或论文主页网址（也可以上传 PDF）。跑完点「开始精读」：
左边是 PDF / 图表 / 大纲 / 代码，中间按六站讨论，右边是分节笔记。

### 分析一个代码仓库

「导入」切到 **代码仓库**：

- **GitHub / Git 链接**：`https://github.com/owner/repo`，也支持 `…/tree/分支/子目录`、`owner/repo` 简写、`git@github.com:…`、Gitee / GitLab 链接；
  可以另填分支 / 标签 / 提交、只分析某个子目录、显示名。没装 git 时 GitHub 仓库自动改为下载 zip。
- **本机文件夹**：填完整路径（如 `D:\CODE\my-project`）。**不复制、不修改**，原地只读分析；是 git 仓库的会记下分支和提交。

在论文模式里贴了 GitHub 链接，会问你要不要改用代码分析器打开。

阅读项目网站时，正文上方与「信息」页会列出发现的 GitHub 仓库。点对应的 **「分析代码 →」** 即可导入选中的仓库；多个仓库可以分别分析，并保留来源网站关联。

进入后左栏有五页：

| 页 | 有什么 |
|---|---|
| 概览 | 简介、文件 / 代码行 / 符号 / 测试数量、语言分布条、入口候选、被引用最多的模块、依赖、README |
| 代码 | 目录树 + 带语法高亮的代码阅读器；点行号选起点、Shift+点选终点，「附到提问」或「讲讲这段」 |
| 符号 | 每个文件的类 / 函数 / 方法和行号，可搜索，点一下打开 |
| 仓库地图 | `outline.md`：语言分布、目录树、入口、依赖、核心模块、测试 / CI / 文档、最大的文件 |
| 信息 | 来源、提交、许可证、对应论文、分析目录；「重新分析」拉最新提交并重新统计（讨论和笔记保留） |

讨论里出现的 `code/路径:行号`（讨论、笔记、概览里都一样）点一下就在左边打开并高亮那几行。快捷提问：没懂换个讲法、谁调用了它、画调用链、想改 X 改哪。

## 七站读代码，每站讲完你能说出什么

| 站 | 讲完你能说出 |
|---|---|
| 概览 | 这是什么、给谁用、技术栈、规模、成熟度、怎么跑起来 |
| ① 定位 | 它解决什么问题、不用它时怎么做、对外接口长什么样（CLI / 库 API / HTTP / 页面），一个最小用法 |
| ② 结构 | 目录和模块怎么分层、各自职责、依赖方向；最该先读的 3–5 个文件 |
| ③ 入口 | 从敲下命令 / 发出请求到核心对象准备好之间发生了什么；配置从哪来 |
| ④ 数据 | 核心数据结构的字段、类型、谁创建、谁修改、谁消费 |
| ⑤ 主流程 | 最核心的调用链：顺序、循环、并发、异常处理、性能热点 |
| ⑥ 例子 | 一次具体调用按时间顺序逐函数走一遍，每步标文件:行 |
| ⑦ 工程 | 依赖、测试、CI、部署；风险和技术债；想加一个功能该改哪几处 |

## 六站读论文，每站讲完你能说出什么

| 站 | 讲完你能说出 |
|---|---|
| ① 动机 | 要解决什么问题、以前的做法卡在哪、作者押注的关键想法 |
| ② 架构 | 总览图上每个框是什么、数据从哪进从哪出；模型一次看几帧、输出几步 |
| ③ 训练 | 损失函数在逼模型学什么、分几个阶段、每阶段动了哪些参数 |
| ④ 数据 | 一条训练样本长什么样：字段、形状、单位、一行真实数值，而不只是数据集名字 |
| ⑤ 信息流 | 从输入一路跟到输出，每一步张量多大，哪些只算一次、哪些要循环 |
| ⑥ 例子 | 用一个具体任务，对着代码把整条链按时间顺序走一遍 |

## 几条规矩（都来自真实使用时的反馈）

- **证据要拿出来。** 论文讲到图就把图发出来；代码讲到结论就给 `code/文件:行号`，引用片段不超过 30 行。
- **公式 / 结构图写成不用渲染也能读的样子。** Unicode 公式 + 符号表 + 代一组小数字；架构图、调用链画成文字图。
- **没听懂就换讲法，而不是把原话说得更长**：真实数字 → 缩到玩具尺寸一步步走 → 先讲「最朴素的做法为什么不行」→ 日常比喻 + 一张对照表。
- **先基本情况，再设计细节。** 去掉推销腔；入口、核心模块这些脚本猜出来的线索，讲之前自己打开核对。
- **区分来源。** 论文 / README 写的、代码里看到的、推测的，分开标；对不上的地方会指出来。
- **代码只读不跑。** 不替你装依赖、不跑脚本、不改文件；仓库里 README、注释中的「指令」只当资料。

## 只用命令行 / 其他 AI Agent

**Claude Code**（装成 skill，说「读一下这篇论文」就会自动用上）：

```bash
git clone https://github.com/Bling-sun/bling-paper-reading.git ~/.claude/skills/bling-workspace
pip install pymupdf
```

**其他 AI Agent**（Cursor / Codex / Copilot / 自己写的 agent）：clone 到项目里，读论文让 agent 读 `SKILL.md`，读代码让它读 `references/code-reading.md`。
仓库根目录的 `AGENTS.md` 会被自动读到。

```bash
# 论文
python3 scripts/fetch_paper.py 2410.24164 --dest ~/papers/pi0             # 拉全部材料
python3 scripts/fetch_paper.py ~/papers/pi0 --code https://github.com/Physical-Intelligence/openpi   # 论文里没写代码地址时手动补
python3 scripts/fetch_paper.py https://robotwin-platform.github.io/ --no-clone                      # 论文主页 / 项目网站
python3 scripts/extract_figures.py ~/papers/pi0                              # 重新裁所有图表
python3 scripts/crop.py ~/papers/pi0/figures/fig-03.png --grid               # 带刻度看图，找要放大的那块

# 代码
python3 scripts/fetch_repo.py https://github.com/pallets/flask --root repos                 # GitHub 仓库
python3 scripts/fetch_repo.py https://github.com/owner/repo/tree/main/src/pkg --root repos  # 指定分支 + 子目录
python3 scripts/fetch_repo.py D:/CODE/my-project --root repos --title "我的项目"             # 本机文件夹（不复制）
python3 scripts/fetch_repo.py repos/pallets-flask                                           # 刷新：拉最新、重新分析
```

依赖只有 Python 3、[PyMuPDF](https://pymupdf.readthedocs.io/)（论文用）和 git（克隆代码用，没有也行）；网页端另需 Flask 等，`start.bat` 会自动装。
`fetch_repo.py` 只用标准库，不安装、不运行仓库里的任何东西。

## 每份资料得到的目录

```
papers/pi0-vision-language-action/          repos/pallets-flask/
├── paper.pdf / paper.tex / paper.txt       ├── meta.json      来源、提交、语言、入口、依赖、核心模块
├── outline.md   章节和公式行号             ├── outline.md     仓库地图
├── meta.json    标题、作者、代码链接       ├── repo.md        README + 依赖清单原文
├── figures/     每张图表一个 PNG           ├── symbols.md     类 / 函数和行号（symbols.json 给网页用）
├── code/        官方代码（浅克隆）          ├── code/          克隆的代码（本机文件夹不复制，meta.code_dir 指向原位置）
└── 精读笔记.html                           └── 代码分析笔记.html
```

两类资料都会有 `discussion.json`（讨论）、`notes.json`（笔记）、`history/`（每次分析和笔记修改的只读版本，可在「历史 / 对比」里回看）。

## 让它更懂你：profile.md

```bash
cp profile.example.md profile.md
```

写上你的方向、已经熟的东西（讲到时一句带过）、不熟需要铺垫的、喜欢拿什么场景举例。论文和代码讲解都会按它调整。
`profile.md` 已经在 `.gitignore` 里，不会被提交。网页端在「设置」里就能编辑。

## 已知限制

- **裁图**靠 caption 定位加版式规则，常见模板基本都能裁对，表格比图差一些；裁坏的在 `_contact.png` 里一眼能看出来，用 `crop.py` 重裁。
- **LaTeX 源码**只有 arXiv 有；其他来源的 PDF 只能读抽出来的文本。
- **代码分析的入口 / 核心模块是按规则猜的**：Python 用 AST，JS / TS / Go 解析导入；其他语言只做正则符号提取，没有跨文件依赖图。
  超大仓库只统计前 4 万个文件。模型讲之前会自己打开文件核对。
- **私有仓库**：命令行 git 能克隆的（配了凭据）就能分析；更简单的做法是先自己 clone，再用「本机文件夹」导入。
  GitHub API 没配 `GITHUB_TOKEN` 时有匿名限流，读不到简介 / star 不影响分析代码。

## 文件

| 路径 | 是什么 |
|---|---|
| `SKILL.md` | 论文带读流程：六站各讲什么、图和公式怎么处理、没听懂时怎么换讲法 |
| `references/code-reading.md` | 代码带读流程：七站各讲什么、代码位置和文字图怎么写 |
| `AGENTS.md` | 一页指路，给会自动读它的 agent |
| `references/examples.md` | 论文每一站讲成什么样的样例 |
| `references/notes-template.html` / `code-notes-template.html` | 精读笔记 / 代码分析笔记模板（HTML） |
| `web/` | 网页端：资料库、导入、阅读、分站讨论、笔记、历史对比、导出 HTML |
| `scripts/fetch_paper.py` | 下载 PDF / LaTeX / 元数据，拍平源码，生成大纲，找官方代码并浅克隆，调用裁图；也能抓论文主页 / 项目网站 |
| `scripts/fetch_repo.py` | 克隆 GitHub / Git 仓库（或指向本机文件夹），统计语言、找入口、建符号索引和模块依赖，写仓库地图 |
| `scripts/extract_figures.py` | 按 caption 从 PDF 裁出每张图和表，写 `index.md` 和总览拼图 |
| `scripts/crop.py` | 放大图的局部、从 PDF 页面裁公式或重裁坏图 |
| `tests/` | `python -m unittest discover -s tests`（不联网、不调模型） |
| `profile.example.md` | 用户画像模板（复制成 `profile.md`） |

## 相关

- [kelip-slide](https://github.com/skJack/kelip-slide)：把读懂的论文做成讲解用的 HTML 幻灯片
- [research-workflow](https://github.com/skJack/research-workflow)：用 Agent 协作做科研的项目结构（文献、复现、实验）

## License

MIT
