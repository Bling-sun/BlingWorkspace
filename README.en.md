# Bling-Workspace

[简体中文](README.md) | **English**

A local workbench for researchers: **paper reading** + **code analysis**. It won't stop at a summary. It reads the material first,
the way someone who already understands it would, then walks you through it one stop at a time — showing the figure whenever it
talks about one, and backing every claim about code with a clickable `code/file:line` reference.

| | Paper reading | Code analysis |
|---|---|---|
| Give it | an arXiv link / PDF / paper or project website | a GitHub / Git URL, or **a folder on your machine** |
| It prepares | PDF, LaTeX source, every figure cropped, the official code | shallow clone (local folders are never copied), language stats, entry-point candidates, symbol index, internal import graph, dependency manifests |
| Stops | six: ① Motivation → ② Architecture → ③ Training → ④ Data → ⑤ Information flow → ⑥ Example (optional ⑦ Results) | seven: Overview → ① Purpose → ② Structure → ③ Entry points → ④ Data → ⑤ Main flow → ⑥ Example → ⑦ Engineering |
| Notes | `精读笔记.html` | `代码分析笔记.html` |
| Protocol | `SKILL.md` | `references/code-reading.md` |

The two are connected: inside a paper workspace, "Read the code with the code analyzer" imports the paper's official code
(re-using the local clone if there is one), and the model maps paper modules to code while explaining structure and flow.

**Quick start:** on Windows double-click `start.bat` (it installs Python if needed); on macOS / Linux run `./start.sh`.

The project folder is named **`Bling-Workspace`**. For a new checkout, use `git clone https://github.com/Bling-sun/BlingWorkspace.git Bling-Workspace`.
The home page offers separate **Paper reader** and **Code analyzer** entries sharing one library, discussions, notes and history.
The browser opens http://127.0.0.1:8765. See [web/README.md](web/README.md). Models: your Claude / ChatGPT subscription via the local
Claude Code / Codex CLI (no API key), or DeepSeek, the Claude API, or any OpenAI-compatible endpoint.

### Analyzing a repository

In the library, switch the importer to **Code repository**:

- **GitHub / Git URL** — `https://github.com/owner/repo`, `…/tree/<branch>/<subdir>`, `owner/repo`, `git@github.com:…`, Gitee / GitLab.
  Optional branch / tag / commit, subdirectory and display name. Without git, GitHub repos are downloaded as a zip.
- **Local folder** — a full path such as `D:\CODE\my-project`. Analyzed in place, read-only: nothing is copied or modified.

When reading a project website, discovered GitHub repositories appear above its text and in Info. Click **Analyze code →** beside a repository to analyze it while retaining its source website association.

The left pane has Overview (size, language bar, entry points, most-imported modules, dependencies, README), Code (tree + syntax-highlighted
viewer; select lines and "attach" or "explain this"), Symbols (searchable classes / functions), Repo map (`outline.md`) and Info
("Re-analyze" pulls the latest commit; discussion and notes are kept). Any `code/path:line` in replies or notes opens and highlights those lines.

```bash
python3 scripts/fetch_repo.py https://github.com/pallets/flask --root repos
python3 scripts/fetch_repo.py https://github.com/owner/repo/tree/main/src/pkg --root repos
python3 scripts/fetch_repo.py D:/CODE/my-project --root repos --title "My project"   # local folder, not copied
python3 scripts/fetch_repo.py repos/pallets-flask                                   # refresh
```

`fetch_repo.py` uses only the standard library and never installs or runs anything from the repository. Entry points and core modules
are heuristics (Python via AST, JS / TS / Go via imports, regex symbols for other languages); the model verifies them before relying on them.

### Downloads, copying and complete record deletion

Configure the code-import proxy in Settings. `auto` uses system/environment/Git proxy settings or a listening local port 7897; set an HTTP proxy explicitly or choose `direct`. Git and ZIP downloads share this setting, with codeload and archive ZIP endpoints available when Git fails.

Reply Copy preserves Markdown. Copy code copies selected lines, or the whole file if no lines are selected. A compatible browser copy method and a manual selection dialog are available when the Clipboard API is blocked.

Delete on a library card or Delete record in the workspace moves the complete reading record into the recycle bin, including its discussions, notes and history. Restore from the library's recycle bin to resume reading. This is a recoverable soft deletion: all local files, original code and PDFs remain in place. Reimporting the same material restores its record too.

### Seven stops for code

| Stop | After this stop you can tell someone |
|---|---|
| Overview | What it is, who it's for, tech stack, size, maturity signals, how to run it |
| ① Purpose | What problem it solves, how you'd do it without it, what its interface looks like (CLI / library API / HTTP / UI) |
| ② Structure | How directories and modules are layered, who depends on whom, the 3–5 files to read first |
| ③ Entry points | What happens between running the command / sending the request and the core objects being ready; where config comes from |
| ④ Data | Fields and types of the core data structures; who creates, mutates and consumes them |
| ⑤ Main flow | The central call chain: order, loops, concurrency, error handling, hot spots |
| ⑥ Example | One concrete call traced function by function, each step with file:line |
| ⑦ Engineering | Dependencies, tests, CI, deployment; risks and tech debt; where to change things to add a feature |

### Paper websites

Public paper/project websites and documentation sites are supported too. Paste a complete HTTP(S) URL into the importer, or run
`python scripts/fetch_paper.py https://nerfies.github.io/ --no-clone`. Website materials include `website.md`, page snapshots, an outline,
source URLs, images and resource links (up to 5 same-host pages and 20 images by default; `--max-pages 1..20`, `--max-images 0..100`).

## Six stops for papers: what you can say after each one

| Stop | After this stop you can tell someone |
|---|---|
| ① Motivation | What problem it solves, where earlier approaches got stuck, and the key bet the authors made |
| ② Architecture | What every box in the overview figure is, where data goes in and comes out; how many frames the model sees and how many steps it outputs |
| ③ Training | What the loss pushes the model to learn, how many stages there are, and which parameters each stage updates |
| ④ Data | What one training sample actually looks like: fields, shapes, units, one row of real values. More than the dataset's name |
| ⑤ Information flow | How to follow an input all the way to the output, tensor shape at every step, what runs once and what loops |
| ⑥ Example | One concrete task, walked through in time order against the code |

## House rules (each one came from feedback while reading real papers)

- **Show the figure.** Saying "see Figure 3" doesn't help: you can't see it. The agent looks at the figure itself first,
  then tells you what the figure is and how to read it.
- **Write formulas so they read without a renderer.** Unicode formula + a symbol table + one set of small numbers plugged in.
- **If you didn't get it, explain it differently instead of saying the same thing longer**: real numbers → shrink to toy size
  and step through → first show why the naive approach fails → an everyday analogy plus a mapping table back to the paper.
- **Basics first, design details second.** Who made it, what goes in and what comes out, what's open-sourced. Skip the paper's sales pitch.
- **Keep sources apart.** What the paper says, what the code shows, and what the agent is guessing are labelled separately;
  places where the code disagrees with the paper get pointed out.
- **Code is read-only.** The official repo is cloned to compare against, not to install or run.

## Install

**Claude Code** (installed as a skill, it kicks in when you say "read this paper with me"):

```bash
git clone https://github.com/Bling-sun/BlingWorkspace.git ~/.claude/skills/bling-workspace
pip install pymupdf
```

**Other AI agents** (Cursor / Codex / Copilot / your own agent): clone it into your project and have the agent read `SKILL.md` for papers, `references/code-reading.md` for code.
There's an `AGENTS.md` at the repo root, so agents that pick that file up automatically need no extra setup.

The only dependencies are Python 3 and [PyMuPDF](https://pymupdf.readthedocs.io/). You need access to arxiv.org and github.com;
Hugging Face being unreachable is fine.

`SKILL.md` and `references/code-reading.md` are written in Chinese. Any modern LLM agent reads it fine and will still talk to you in your own language.

## Usage

```
Read this paper with me: https://arxiv.org/abs/2410.24164
Walk me through π0 and put it under ~/papers
Skip to the data: what does one training sample actually look like?
Take one concrete example and walk the inference through the code
```

The first reply is "basics + stop ①". Every stop ends by asking whether to continue. You can interrupt with questions any time,
jump to another stop, ask it to "translate the introduction" (original and translation side by side), or ask it to
"turn this into a document" (the reading notes are already there).

## What you get for each paper

```
papers/pi0-vision-language-action/
├── paper.pdf         the paper
├── source/           LaTeX source from arXiv
├── paper.tex         the source flattened into one file (\input expanded, comments and references removed); trusted for formulas and tables
├── paper.txt         PDF text, page by page
├── outline.md        line numbers of every section and equation in paper.tex, so the agent can jump around
├── meta.json         title, authors, dates, abstract, code and project-page links
├── figures/          one PNG per figure and table; index.md has captions and where each is cited; _contact.png shows them all at once
├── code/             the official code (shallow clone)
└── 精读笔记.html      reading notes: the gist of each stop, the figures used, the questions you asked
```

In a project laid out like [research-workflow](https://github.com/skJack/research-workflow) (the current directory has `related_work/`),
papers go to `related_work/<slug>/` and code goes to `复现/<repo>/code`. If the paper folder already has a `figures/`
you curated yourself, the auto-cropped figures go to `figures-auto/` and yours are left alone.

## Make it fit you: profile.md

```bash
cp profile.example.md profile.md
```

Both paper and code walkthroughs adapt to it. Write down your field, what you already know (it'll mention those in one line), what needs groundwork first, and what kind of
scenarios you like for examples. It works without one too: the first time it reaches stop ⑥ it asks what scenario to use and
writes the answer down for you. `profile.md` is in `.gitignore`, so it never gets committed.

## Use the scripts on their own

```bash
python3 scripts/fetch_paper.py 2410.24164 --dest ~/papers/pi0             # pull everything
python3 scripts/fetch_paper.py ~/papers/pi0 --code https://github.com/Physical-Intelligence/openpi   # add the code repo when the paper doesn't link it
python3 scripts/extract_figures.py ~/papers/pi0                              # re-crop all figures and tables
python3 scripts/crop.py ~/papers/pi0/figures/fig-03.png --grid               # overlay a grid to locate the part you want to zoom into
python3 scripts/crop.py ~/papers/pi0/paper.pdf --page 4 0.08 0.06 0.92 0.3 -o eq.png   # crop a region of a PDF page (equation, table)
```

Input can be an arXiv ID or link (abs, pdf, alphaxiv and Hugging Face Papers links all work), a direct PDF link, a local PDF
(a renamed arXiv PDF is recognised by the arXiv stamp on its first page, so the source still gets pulled), or a paper folder
you already have (only what's missing gets filled in). The scripts print their progress in Chinese.

## Known limitations

- **Figure cropping** locates captions and applies layout rules. It's been tested on common templates (single column,
  two column, IEEE, NeurIPS / ICLR, journals) and gets figures right nearly all the time; tables are less reliable.
  A bad crop is obvious in `_contact.png`; re-crop it with `crop.py`. The agent also checks before it uses a figure.
- **LaTeX source** only exists for arXiv papers. For PDFs from elsewhere only the extracted text is available, so formulas and tables are rougher.
- **Finding the code** checks the abstract, the arXiv comment, links on the PDF's first page, Hugging Face Papers and the project page.
  When the paper never mentions its code (e.g. π0 → openpi), the agent has to search and add it with `--code`.

## Files

| Path | What it is |
|---|---|
| `SKILL.md` | The reading protocol for the agent: what each stop covers, how to handle figures and formulas, how to re-explain when something didn't land |
| `AGENTS.md` | One-page pointer for agents that read it automatically |
| `references/examples.md` | Examples of what each stop looks like when it's done well |
| `references/code-reading.md` | The code-reading protocol: seven stops, how to cite code locations and draw text diagrams |
| `references/notes-template.html` / `code-notes-template.html` | Templates for paper notes / code-analysis notes (HTML) |
| `web/` | Web app: library (papers, websites, repositories), import, read, discuss by stops, notes, history, export HTML |
| `profile.example.md` | Template for your profile (copy to `profile.md`) |
| `scripts/fetch_paper.py` | Downloads PDF / LaTeX / metadata, flattens the source, builds the outline, finds and shallow-clones the official code, runs figure extraction |
| `scripts/extract_figures.py` | Crops every figure and table out of the PDF by caption, writes `index.md` and a contact sheet |
| `scripts/crop.py` | Zooms into part of a figure, crops equations from a PDF page, or re-crops a bad figure |
| `scripts/fetch_repo.py` | Clones a GitHub / Git repo (or points at a local folder), computes languages, entry points, symbols and the import graph, writes the repo map |
| `tests/` | `python -m unittest discover -s tests` (no network, no model calls) |

## Updating GitHub

The remote repository is [Bling-sun/BlingWorkspace](https://github.com/Bling-sun/BlingWorkspace); the local folder remains `Bling-Workspace`.
On Windows, double-click `push_to_github.bat` to commit local changes, push to `main`, and verify the remote commit.
Run `push_to_github.bat -Check` for a check without committing or pushing. The default proxy is `http://127.0.0.1:7897`; override it with `-Proxy "http://127.0.0.1:PORT"`.
Use `-Message "Your message"` to supply a commit message. Local materials, notes, profiles and configuration are excluded; the script stops if the remote has unmerged changes.

## Related

- [kelip-slide](https://github.com/skJack/kelip-slide): turn a paper you understand into an HTML slide deck for explaining it
- [research-workflow](https://github.com/skJack/research-workflow): a project layout for doing research with agents (literature, reproduction, experiments)

## License

MIT
