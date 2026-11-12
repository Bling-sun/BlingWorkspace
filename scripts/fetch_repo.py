"""把一个代码仓库备成「代码分析」材料：GitHub / Git 链接（浅克隆，没 git 时下载 zip），或本机代码文件夹（只读，不复制）。

    python scripts/fetch_repo.py https://github.com/owner/repo --root repos
    python scripts/fetch_repo.py https://github.com/owner/repo/tree/main/src/pkg     # 指定分支 + 只分析某个子目录
    python scripts/fetch_repo.py owner/repo --ref v1.2.0                             # GitHub 简写 + 标签
    python scripts/fetch_repo.py D:/CODE/my-project --root repos                     # 本机文件夹（不复制，原地只读）
    python scripts/fetch_repo.py repos/owner-repo                                    # 已有分析目录：拉最新、重新分析

分析目录里得到：
  meta.json     kind=repo、来源、提交、语言统计、入口候选、依赖清单、核心模块…
  outline.md    仓库地图：语言分布、目录树、入口、依赖、被引用最多的模块、测试 / CI / 文档
  repo.md       README + 依赖清单原文（给模型读的「正文」）
  symbols.md    每个源文件里的类 / 函数和行号（symbols.json 同一份数据，给网页端「符号」页用）
  code/         克隆下来的代码；本机文件夹不复制，meta.json 的 code_dir 指向原位置

只用标准库；不安装依赖、不运行仓库里的任何脚本。
"""
import argparse
import ast
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

UA = "Bling-Workspace/1.0 (code reader)"

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env", ".env", ".tox", ".nox",
             "dist", "build", "out", "target", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", ".ruff_cache",
             ".next", ".nuxt", ".svelte-kit", ".turbo", "coverage", ".gradle", ".cache", "site-packages",
             "bower_components", ".terraform", "wandb", ".ipynb_checkpoints", "Pods", "DerivedData", ".eggs"}
KEEP_HIDDEN = {".github", ".gitlab", ".circleci", ".devcontainer"}

LANG = {
    ".py": "Python", ".pyi": "Python", ".pyx": "Cython", ".ipynb": "Jupyter",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".vue": "Vue", ".svelte": "Svelte",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala",
    ".c": "C", ".h": "C/C++ 头文件", ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".hxx": "C++", ".cu": "CUDA", ".cuh": "CUDA", ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".m": "Objective-C", ".mm": "Objective-C", ".lua": "Lua", ".r": "R", ".jl": "Julia", ".dart": "Dart",
    ".zig": "Zig", ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".hs": "Haskell", ".ml": "OCaml",
    ".clj": "Clojure", ".groovy": "Groovy", ".gradle": "Groovy", ".sol": "Solidity", ".proto": "Protobuf",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell", ".bat": "Batch", ".cmd": "Batch",
    ".sql": "SQL", ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "SCSS", ".less": "Less",
    ".cmake": "CMake", ".md": "Markdown", ".mdx": "Markdown", ".rst": "reStructuredText", ".txt": "Text",
    ".json": "JSON", ".jsonc": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".ini": "INI", ".cfg": "INI",
    ".xml": "XML", ".csv": "CSV",
}
NAME_LANG = {"Dockerfile": "Dockerfile", "Makefile": "Makefile", "CMakeLists.txt": "CMake", "Jenkinsfile": "Groovy"}
NON_CODE = {"Markdown", "reStructuredText", "Text", "JSON", "YAML", "TOML", "INI", "XML", "CSV", "Jupyter"}
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg", ".pdf", ".zip", ".gz", ".tar", ".tgz",
          ".7z", ".rar", ".whl", ".so", ".dll", ".dylib", ".exe", ".bin", ".pt", ".pth", ".ckpt", ".onnx", ".npz",
          ".npy", ".pkl", ".h5", ".parquet", ".mp4", ".mov", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".otf",
          ".eot", ".jar", ".class", ".o", ".a", ".lib", ".pyc", ".db", ".sqlite", ".safetensors", ".lock"}

MANIFESTS = ("package.json", "pnpm-workspace.yaml", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile",
             "environment.yml", "environment.yaml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
             "build.gradle.kts", "settings.gradle", "CMakeLists.txt", "Makefile", "Dockerfile", "docker-compose.yml",
             "docker-compose.yaml", "compose.yaml", "composer.json", "Gemfile", "mix.exs", "pubspec.yaml",
             "deno.json", "tsconfig.json", "Package.swift", "meson.build", "BUILD", "WORKSPACE", "MODULE.bazel")
CI_FILES = (".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci/config.yml")
ENTRY_NAMES = {"main.py", "__main__.py", "app.py", "server.py", "cli.py", "manage.py", "train.py", "run.py",
               "demo.py", "infer.py", "inference.py", "eval.py", "evaluate.py", "predict.py", "serve.py",
               "index.js", "index.ts", "main.js", "main.ts", "main.tsx", "index.tsx", "app.js", "app.ts",
               "server.js", "server.ts", "cli.js", "cli.ts", "main.go", "main.rs", "lib.rs", "Main.java",
               "main.c", "main.cpp", "main.cc", "Program.cs", "main.dart", "main.swift"}

MAX_WALK = 40000
EXCLUDE = set()  # 绝对路径：分析目录本身放在被分析的文件夹里时，别把它也算进去
MAX_LINE_BYTES = 1_500_000
MAX_SYMBOL_BYTES = 600_000


def log(msg):
    print(msg, flush=True)


# ---------------- 解析输入 ----------------

GH_RE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?"
                   r"(?:/(?:tree|blob|commit)/([^/?#]+)(?:/([^?#]*))?)?/?(?:[?#].*)?$", re.I)
GH_SSH = re.compile(r"^git@github\.com:([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", re.I)
GIT_HTTP = re.compile(r"^(https?://[^/\s]+/[^\s?#]+?)(?:\.git)?(?:/(?:-/)?(?:tree|blob|src)/([^/?#]+)(?:/([^?#]*))?)?/?(?:[?#].*)?$", re.I)
SHORT = re.compile(r"^([A-Za-z0-9][\w.-]*)/([\w.-]+?)(?:\.git)?$")


def parse_target(target):
    """→ {"kind": "github"|"git"|"local"|"workspace", …}"""
    raw = (target or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("缺少仓库地址或文件夹路径")
    p = Path(os.path.expanduser(raw))
    if p.is_dir():
        mj = p / "meta.json"
        if mj.is_file():
            try:
                meta = json.loads(mj.read_text(encoding="utf-8"))
                if meta.get("kind") == "repo":
                    return {"kind": "workspace", "path": p.resolve(), "meta": meta}
            except ValueError:
                pass
        return {"kind": "local", "path": p.resolve()}
    m = GH_RE.match(raw) or GH_SSH.match(raw)
    if m:
        owner, repo = m.group(1), m.group(2)
        ref = m.group(3) if m.re is GH_RE else None
        sub = (m.group(4) or "").strip("/") if m.re is GH_RE else ""
        return {"kind": "github", "owner": owner, "repo": repo, "ref": ref, "subdir": sub,
                "url": f"https://github.com/{owner}/{repo}"}
    if raw.startswith("git@") or raw.endswith(".git") and "://" not in raw:
        name = re.sub(r"\.git$", "", raw.rstrip("/").split("/")[-1].split(":")[-1])
        return {"kind": "git", "url": raw, "clone_url": raw, "repo": name, "ref": None, "subdir": ""}
    m = GIT_HTTP.match(raw)
    if m and re.match(r"https?://", raw):
        base = m.group(1)
        return {"kind": "git", "url": base, "clone_url": base + ".git" if "gitee.com" in base or "gitlab" in base else base,
                "repo": base.rstrip("/").split("/")[-1], "ref": m.group(2), "subdir": (m.group(3) or "").strip("/")}
    m = SHORT.match(raw)
    if m and not re.match(r"^[A-Za-z]:", raw) and not raw.startswith((".", "~")):
        return {"kind": "github", "owner": m.group(1), "repo": m.group(2), "ref": None, "subdir": "",
                "url": f"https://github.com/{m.group(1)}/{m.group(2)}"}
    if re.match(r"^([A-Za-z]:[\\/]|[\\/]|~|\.)", raw):
        raise ValueError(f"本机上没有这个文件夹：{raw}")
    raise ValueError(f"认不出来：{raw}。给 GitHub / Git 链接（https://github.com/owner/repo）或者本机代码文件夹的完整路径")


def slugify(*parts):
    s = "-".join(x for x in parts if x)
    s = re.sub(r"[^\w.-]+", "-", s, flags=re.U).strip("-.").lower()
    return s[:80] or "repo"


# ---------------- 拉代码 ----------------

def http_get(url, timeout=25, limit=300_000_000, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"超过 {limit // 1_000_000} MB 上限")
    return data


def github_api(owner, repo):
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return json.loads(http_get(f"https://api.github.com/repos/{owner}/{repo}", timeout=15, limit=2_000_000, headers=headers))


def git(*args, cwd=None, timeout=300):
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def clone(url, code_dir, ref=None):
    """浅克隆。返回 (状态, 说明)。状态：ok / exists / no-git / failed"""
    if code_dir.exists() and any(code_dir.iterdir()):
        if (code_dir / ".git").exists() and shutil.which("git"):
            if ref:
                fetched = git("-C", str(code_dir), "fetch", "--depth", "1", "origin", ref, timeout=180)
                if fetched.returncode == 0:
                    checked = git("-C", str(code_dir), "checkout", "--detach", "FETCH_HEAD")
                    if checked.returncode == 0:
                        return "exists", f"已更新指定版本（{ref}）"
                return "exists", f"无法更新指定版本 {ref}，沿用本地代码（请核对提交号）"
            r = git("-C", str(code_dir), "pull", "--ff-only", timeout=180)
            return "exists", ("已更新到最新提交" if r.returncode == 0 else "已有代码（拉最新没成功，沿用本地这份）")
        return "exists", "已有代码"
    if not shutil.which("git"):
        return "no-git", "没装 git"
    code_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        if ref:
            r = git("clone", "--depth", "1", "--single-branch", "--branch", ref, url, str(code_dir))
            if r.returncode == 0:
                return "ok", f"已浅克隆（{ref}）"
            shutil.rmtree(code_dir, ignore_errors=True)
            r = git("clone", "--filter=blob:none", "--no-checkout", url, str(code_dir))  # ref 可能是提交号
            if r.returncode == 0 and git("-C", str(code_dir), "checkout", "-q", ref).returncode == 0:
                return "ok", f"已克隆并检出 {ref}"
            shutil.rmtree(code_dir, ignore_errors=True)
            return "failed", f"无法检出指定版本 {ref}"
        r = git("clone", "--depth", "1", "--single-branch", url, str(code_dir))
        if r.returncode == 0:
            return "ok", "已浅克隆" + (f"（没找到 {ref}，用了默认分支）" if ref else "")
        shutil.rmtree(code_dir, ignore_errors=True)
        return "failed", (r.stderr.strip().split("\n") or [""])[-1][:200]
    except subprocess.TimeoutExpired:
        shutil.rmtree(code_dir, ignore_errors=True)
        return "failed", "克隆超时（5 分钟）"


def safe_unzip(data, dest):
    """解 GitHub 的 zip：去掉最外层「repo-ref/」目录，拒绝越界路径。"""
    dest = Path(dest).resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        top = os.path.commonprefix([n.split("/", maxsplit=1)[0] + "/" for n in names]) if names else ""
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = info.filename[len(top):] if top and info.filename.startswith(top) else info.filename
            if not rel:
                continue
            target = (dest / rel).resolve()
            if dest not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def github_zip(owner, repo, ref, code_dir):
    data = http_get(f"https://github.com/{owner}/{repo}/archive/{ref or 'HEAD'}.zip", timeout=120)
    code_dir = Path(code_dir).resolve()
    code_dir.parent.mkdir(parents=True, exist_ok=True)
    # 下载、解压成功后再替换快照；网络失败时保留上一次可读的代码。
    with tempfile.TemporaryDirectory(prefix=".bling-download-", dir=code_dir.parent) as tmp:
        stage = Path(tmp).resolve()
        if stage.parent != code_dir.parent:
            raise ValueError("下载暂存目录越界")
        content, backup = stage / "content", stage / "previous"
        safe_unzip(data, content)
        if not content.is_dir() or not any(content.iterdir()):
            raise ValueError("仓库压缩包没有可读文件")
        if code_dir.exists():
            code_dir.rename(backup)
        try:
            content.rename(code_dir)
        except OSError:
            if backup.exists():
                backup.rename(code_dir)
            raise


def local_git_info(path):
    info = {}
    if shutil.which("git"):
        for key, args in (("commit", ["rev-parse", "HEAD"]), ("branch", ["rev-parse", "--abbrev-ref", "HEAD"]),
                          ("remote", ["remote", "get-url", "origin"])):
            try:
                r = git("-C", str(path), *args, timeout=15)
                if r.returncode == 0 and r.stdout.strip():
                    info[key] = r.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
    if not info:  # 没 git 命令：直接看 .git/HEAD
        head = Path(path) / ".git" / "HEAD"
        if head.is_file():
            t = head.read_text(encoding="utf-8", errors="ignore").strip()
            if t.startswith("ref:"):
                info["branch"] = t.split("/")[-1]
                ref = Path(path) / ".git" / t[4:].strip()
                if ref.is_file():
                    info["commit"] = ref.read_text(encoding="utf-8", errors="ignore").strip()
            else:
                info["commit"] = t
    if info.get("remote"):
        info["remote"] = re.sub(r"https://[^@/]+@", "https://", info["remote"])  # 别把 token 记下来
    return info


# ---------------- 分析 ----------------

def read_text(f, limit=None):
    try:
        with open(f, "rb") as fh:
            data = fh.read(limit) if limit else fh.read()
    except OSError:
        return ""
    if b"\x00" in data[:4096]:
        return ""
    return data.decode("utf-8", errors="ignore")


def lang_of(f):
    return NAME_LANG.get(f.name) or LANG.get(f.suffix.lower())


def walk(base):
    """→ [(相对路径, Path, 字节数)]，跳过依赖 / 构建 / 隐藏目录。"""
    out = []
    for dp, dns, fns in os.walk(base):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and (not d.startswith(".") or d in KEEP_HIDDEN)
                        and not d.endswith(".egg-info") and str(Path(dp, d).resolve()) not in EXCLUDE)
        for fn in sorted(fns):
            if fn.startswith(".") and fn not in (".gitlab-ci.yml", ".travis.yml"):
                continue
            f = Path(dp) / fn
            try:
                size = f.stat().st_size
            except OSError:
                continue
            out.append((f.relative_to(base).as_posix(), f, size))
            if len(out) >= MAX_WALK:
                return out, True
    return out, False


PY_MAIN = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", re.M)
RX = {
    "JavaScript": [
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"), "class"),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(interface|type|enum)\s+([A-Za-z_$][\w$]*)"), None),
    ],
    "Go": [
        (re.compile(r"^func\s+(?:\(\s*\w*\s*\*?\s*(\w+)[^)]*\)\s*)?(\w+)\s*\("), "func"),
        (re.compile(r"^type\s+(\w+)\s+(struct|interface)\b"), None),
    ],
    "Rust": [
        (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?(?:const\s+)?fn\s+(\w+)"), "fn"),
        (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(struct|enum|trait|mod)\s+(\w+)"), None),
        (re.compile(r"^\s*impl(?:<[^>]*>)?\s+(?:([\w:]+)(?:<[^>]*>)?\s+for\s+)?([\w:]+)"), "impl"),
    ],
    "Java": [
        (re.compile(r"^\s*(?:public|protected|private|abstract|final|static|sealed|\s)*(class|interface|enum|record)\s+(\w+)"), None),
        (re.compile(r"^\s+(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?[\w<>\[\],.? ]+\s+(\w+)\s*\([^;]*$"), "method"),
    ],
    "C++": [
        (re.compile(r"^\s*(?:template\s*<[^>]*>\s*)?(class|struct|namespace)\s+(\w+)\s*(?::[^{;]*)?\{?\s*$"), None),
        (re.compile(r"^(?!\s)(?!(?:if|for|while|switch|return|else|do|case)\b)[\w:<>,*&~\s]*?\b([A-Za-z_~][\w:~]*)\s*\([^;]*\)\s*(?:const)?\s*(?:noexcept)?\s*(?:override)?\s*\{?\s*$"), "function"),
    ],
}
RX["TypeScript"] = RX["Vue"] = RX["Svelte"] = RX["JavaScript"]
RX["Kotlin"] = [(re.compile(r"^\s*(?:data\s+|sealed\s+|abstract\s+|open\s+)?(class|interface|object)\s+(\w+)"), None),
                (re.compile(r"^\s*(?:override\s+|private\s+|internal\s+|suspend\s+)*fun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)\s*\("), "fun")]
RX["C#"] = RX["Java"]
RX["Scala"] = RX["Kotlin"]
RX["C"] = RX["C/C++ 头文件"] = RX["CUDA"] = RX["C++"]


def py_symbols(text):
    tree = ast.parse(text)
    out = []

    def args_of(fn):
        a = [x.arg for x in fn.args.posonlyargs + fn.args.args]
        if fn.args.vararg:
            a.append("*" + fn.args.vararg.arg)
        a += [x.arg for x in fn.args.kwonlyargs]
        if fn.args.kwarg:
            a.append("**" + fn.args.kwarg.arg)
        return ", ".join(a)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append({"name": node.name, "kind": "def", "line": node.lineno, "sig": f"({args_of(node)})"})
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)[:80] if hasattr(ast, "unparse") else ""
            out.append({"name": node.name, "kind": "class", "line": node.lineno, "sig": f"({bases})" if bases else ""})
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append({"name": f"{node.name}.{sub.name}", "kind": "method", "line": sub.lineno,
                                "sig": f"({args_of(sub)})"})
    return out


def rx_symbols(text, lang):
    out = []
    pats = RX.get(lang)
    if not pats:
        return out
    for i, line in enumerate(text.split("\n"), 1):
        if len(line) > 300:
            continue
        for rx, kind in pats:
            m = rx.match(line)
            if not m:
                continue
            g = [x for x in m.groups() if x]
            if kind is None:  # (类型词, 名字)
                k, name = (g[0], g[1]) if len(g) >= 2 else ("type", g[0])
            elif kind == "func" and len(g) == 2:  # Go 方法：(接收者类型, 方法名)
                k, name = "method", f"{g[0]}.{g[1]}"
            elif kind == "impl":
                k, name = "impl", " for ".join(g[::-1]) if len(g) == 2 else g[0]
            else:
                k, name = kind, g[-1]
            if name in ("if", "for", "while", "switch", "return", "catch", "sizeof", "defined"):
                continue
            out.append({"name": name, "kind": k, "line": i, "sig": ""})
            break
        if len(out) >= 120:
            break
    return out


def module_name(rel):
    """Python 文件 → 可能的模块名（同时给 src/ 布局去掉前缀的版本）。"""
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    names = [".".join(parts)] if parts else []
    for pre in ("src", "lib", "python"):
        if len(parts) > 1 and parts[0] == pre:
            names.append(".".join(parts[1:]))
    return names


def py_imports(text, rel):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    pkg = rel[:-3].split("/")[:-1] if not rel.endswith("__init__.py") else rel.split("/")[:-1]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                up = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                base = ".".join(up + ([base] if base else []))
            out.append(base)
            out += [f"{base}.{a.name}" if base else a.name for a in node.names if a.name != "*"]
    return out


JS_IMPORT = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(\s*|require\s*\(\s*|import\s+)['"](\.{1,2}/[^'"]+)['"]""")
JS_EXT = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte", "/index.ts", "/index.tsx", "/index.js", "/index.jsx")


def resolve_js(rel, spec, files):
    base = Path(rel).parent
    target = os.path.normpath((base / spec).as_posix()).replace("\\", "/")
    for ext in JS_EXT:
        if target + ext in files:
            return target + ext
    return None


def analyze(base, focus=""):
    base = Path(base).resolve()
    root = (base / focus).resolve() if focus else base
    if root != base and base not in root.parents:
        raise ValueError("子目录必须位于代码仓库内")
    if not root.is_dir():
        raise ValueError(f"仓库里没有子目录 {focus}")
    files, truncated = walk(root)
    rel_set = {r for r, _, _ in files}
    langs = defaultdict(lambda: {"files": 0, "lines": 0})
    dir_stats = defaultdict(lambda: {"files": 0, "lines": 0, "langs": Counter()})
    manifests, ci, docs, tests, entries, licenses = [], [], [], [], [], []
    symbols, big = {}, []
    py_mods, py_imp, js_imp = {}, {}, {}
    go_mod = None
    n_lines = 0
    for rel, f, size in files:
        parts = rel.split("/")
        depth = len(parts) - 1
        name = parts[-1]
        lang = lang_of(f)
        top = parts[0] if depth else "（根目录）"
        dir_stats[top]["files"] += 1
        if name in MANIFESTS or re.fullmatch(r"requirements[\w.-]*\.txt", name) or name.endswith((".csproj", ".sln")):
            if depth <= 2:
                manifests.append(rel)
        if rel.startswith(".github/workflows/") or rel in CI_FILES:
            ci.append(rel)
        if re.match(r"(?i)^(license|licence|copying)(\.|$)", name) and depth == 0:
            licenses.append(rel)
        if depth == 0 and re.match(r"(?i)^(contributing|changelog|history|changes)\b", name):
            docs.append(rel)
        if parts[0].lower() in ("docs", "doc", "documentation") and lang in ("Markdown", "reStructuredText"):
            docs.append(rel)
        if any(p.lower() in ("tests", "test", "__tests__", "spec", "testing") for p in parts[:-1]) or \
                re.match(r"(test_.*\.py|.*_test\.(py|go)|.*\.(test|spec)\.[jt]sx?|.*Tests?\.(java|kt|cs))$", name):
            tests.append(rel)
        if not lang or f.suffix.lower() in BINARY:
            continue
        text = read_text(f) if size <= MAX_LINE_BYTES else ""
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        langs[lang]["files"] += 1
        langs[lang]["lines"] += lines
        n_lines += lines
        dir_stats[top]["lines"] += lines
        if lang not in NON_CODE:
            dir_stats[top]["langs"][lang] += lines
            big.append((lines, rel))
        if not text:
            continue
        # 入口
        reason = None
        if lang == "Python" and PY_MAIN.search(text):
            line = text[:PY_MAIN.search(text).start()].count("\n") + 1
            reason = ("if __name__ == '__main__'", line)
        elif lang == "Go" and re.search(r"^package\s+main\b", text, re.M) and re.search(r"^func\s+main\s*\(", text, re.M):
            reason = ("package main · func main()", text[:re.search(r"^func\s+main\s*\(", text, re.M).start()].count("\n") + 1)
        elif lang in ("Java", "C#", "Kotlin") and re.search(r"static\s+(?:void|async\s+Task)\s+[Mm]ain\s*\(|^fun\s+main\s*\(", text, re.M):
            m = re.search(r"static\s+(?:void|async\s+Task)\s+[Mm]ain\s*\(|^fun\s+main\s*\(", text, re.M)
            reason = ("main()", text[:m.start()].count("\n") + 1)
        elif lang in ("C", "C++", "CUDA") and re.search(r"^\s*int\s+main\s*\(", text, re.M):
            reason = ("int main()", text[:re.search(r"^\s*int\s+main\s*\(", text, re.M).start()].count("\n") + 1)
        elif lang == "Rust" and (rel.endswith("src/main.rs") or "/src/bin/" in "/" + rel):
            reason = ("Rust 二进制入口", 1)
        elif name in ENTRY_NAMES and depth <= 2:
            reason = ("常见入口文件名", 1)
        if reason:
            entries.append({"path": rel, "line": reason[1], "kind": lang, "reason": reason[0]})
        # 符号
        if size <= MAX_SYMBOL_BYTES and lang not in NON_CODE:
            syms = []
            if lang == "Python":
                try:
                    syms = py_symbols(text)
                except (SyntaxError, ValueError, RecursionError):
                    syms = []
            else:
                syms = rx_symbols(text, lang)
            if syms:
                symbols[rel] = syms[:150]
        # 依赖关系
        if lang == "Python":
            for mn in module_name(rel):
                py_mods.setdefault(mn, rel)
            py_imp[rel] = py_imports(text, rel)
        elif lang in ("JavaScript", "TypeScript", "Vue", "Svelte"):
            js_imp[rel] = [r for r in (resolve_js(rel, s, rel_set) for s in JS_IMPORT.findall(text)) if r]
        if name == "go.mod" and depth == 0:
            m = re.search(r"^module\s+(\S+)", text, re.M)
            go_mod = m.group(1) if m else None

    # 内部依赖图：谁被引用最多
    edges = defaultdict(set)
    for rel, imps in py_imp.items():
        here = ".".join(rel.split("/")[:-1])  # 脚本目录在 sys.path 上时的同目录导入（import context）
        for imp in imps:
            for cand in ([imp, f"{here}.{imp}"] if here else [imp]):
                parts = cand.split(".")
                tgt = next((py_mods[".".join(parts[:k])] for k in range(len(parts), 0, -1) if ".".join(parts[:k]) in py_mods), None)
                if tgt and tgt != rel:
                    edges[rel].add(tgt)
                    break
    for rel, tgts in js_imp.items():
        edges[rel].update(t for t in tgts if t != rel)
    if go_mod:
        for rel, f, size in files:
            if rel.endswith(".go") and size <= MAX_SYMBOL_BYTES:
                for imp in re.findall(r'"(' + re.escape(go_mod) + r'/[^"]+)"', read_text(f)):
                    d = imp[len(go_mod) + 1:]
                    if any(r.startswith(d + "/") for r in rel_set):
                        edges[rel].add(d + "/")
    indeg = Counter(t for tgts in edges.values() for t in tgts)
    importers = defaultdict(list)
    for src, tgts in edges.items():
        for t in tgts:
            importers[t].append(src)
    top_modules = [{"path": p, "imported_by": n, "imports": len(edges.get(p, ())), "examples": sorted(importers[p])[:6]}
                   for p, n in indeg.most_common(20)]

    code_langs = sorted(((k, v) for k, v in langs.items() if k not in NON_CODE), key=lambda kv: -kv[1]["lines"])
    total_code = sum(v["lines"] for _, v in code_langs) or 1
    languages = [{"name": k, "files": v["files"], "lines": v["lines"], "pct": round(100 * v["lines"] / total_code, 1)}
                 for k, v in code_langs]
    other = sorted(((k, v) for k, v in langs.items() if k in NON_CODE), key=lambda kv: -kv[1]["files"])
    top_dirs = sorted(({"name": k, "files": v["files"], "lines": v["lines"],
                        "lang": v["langs"].most_common(1)[0][0] if v["langs"] else ""} for k, v in dir_stats.items()),
                      key=lambda x: -x["lines"])[:30]

    def entry_score(e):
        p = e["path"]
        s = 0 if e["reason"] != "常见入口文件名" else 2
        s += p.count("/")
        aside = {"test", "tests", "testing", "example", "examples", "demos", "scripts", "tools", "benchmark",
                 "benchmarks", "bench", "docs", "sample", "samples", "third_party", "vendor"}
        s += 3 if any(x in aside for x in p.lower().split("/")[:-1]) or p.split("/")[-1].startswith("test") else 0
        return s

    entries.sort(key=lambda e: (entry_score(e), e["path"]))
    readme = next((r for r, _, _ in files if r.count("/") == 0 and re.match(r"(?i)^readme(\.(md|rst|txt|markdown))?$", r)), None)
    return {
        "files": files, "truncated": truncated, "languages": languages,
        "other_files": [{"name": k, "files": v["files"]} for k, v in other],
        "n_files": len(files), "n_lines": n_lines, "n_code_lines": sum(v["lines"] for _, v in code_langs),
        "manifests": manifests[:40], "ci": ci[:20], "docs": docs[:40], "licenses": licenses,
        "tests": {"files": len(tests), "examples": tests[:12]}, "entry_points": entries[:30],
        "symbols": symbols, "top_modules": top_modules, "top_dirs": top_dirs,
        "largest": [{"path": r, "lines": n} for n, r in sorted(big, reverse=True)[:12]],
        "readme": readme, "n_edges": sum(len(v) for v in edges.values()),
    }


def parse_manifests(root, manifests):
    """依赖名字 + 脚本 + 声明的命令行入口。只读文件，不执行。"""
    deps, scripts, bins = {}, {}, []
    for rel in manifests:
        f = root / rel
        name = f.name
        text = read_text(f, 400_000)
        if not text:
            continue
        try:
            if name == "package.json":
                j = json.loads(text)
                d = list((j.get("dependencies") or {}).keys())
                dd = list((j.get("devDependencies") or {}).keys())
                if d or dd:
                    deps[rel] = d + [f"{x}（dev）" for x in dd]
                if j.get("scripts"):
                    scripts[rel] = j["scripts"]
                b = j.get("bin")
                if isinstance(b, str):
                    bins.append({"name": j.get("name", ""), "target": b, "from": rel})
                elif isinstance(b, dict):
                    bins += [{"name": k, "target": v, "from": rel} for k, v in b.items()]
                if j.get("main"):
                    bins.append({"name": "main", "target": j["main"], "from": rel})
            elif re.fullmatch(r"requirements[\w.-]*\.txt", name):
                deps[rel] = [re.split(r"[<>=!~;\[ ]", l.strip(), maxsplit=1)[0] for l in text.splitlines()
                             if l.strip() and not l.strip().startswith(("#", "-"))]
            elif name in ("pyproject.toml", "Cargo.toml") and tomllib:
                t = tomllib.loads(text)
                proj = t.get("project") or {}
                d = [re.split(r"[<>=!~;\[ ]", x, maxsplit=1)[0] for x in proj.get("dependencies") or []]
                d += list(((t.get("tool") or {}).get("poetry") or {}).get("dependencies", {}).keys())
                d += list((t.get("dependencies") or {}).keys())
                if d:
                    deps[rel] = [x for x in d if x and x.lower() != "python"]
                for k, v in (proj.get("scripts") or {}).items():
                    bins.append({"name": k, "target": v, "from": rel})
                for b in t.get("bin") or []:
                    bins.append({"name": b.get("name", ""), "target": b.get("path", ""), "from": rel})
            elif name == "go.mod":
                d = re.findall(r"^\s*([\w./-]+\.[\w./-]+)\s+v[\w.+-]+", text, re.M)
                if d:
                    deps[rel] = d
            elif name == "setup.py":
                m = re.search(r"install_requires\s*=\s*\[(.*?)\]", text, re.S)
                if m:
                    deps[rel] = [re.split(r"[<>=!~;\[ ]", x, maxsplit=1)[0] for x in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))]
                for k, v in re.findall(r"['\"]([\w.-]+)\s*=\s*([\w.:]+)['\"]", text):
                    if ":" in v:
                        bins.append({"name": k, "target": v, "from": rel})
            elif name in ("environment.yml", "environment.yaml"):
                d = re.findall(r"^\s*-\s*([A-Za-z0-9_.-]+)", text, re.M)
                if d:
                    deps[rel] = d
        except (ValueError, TypeError, AttributeError) as e:
            deps.setdefault(rel, [f"（解析失败：{e}）"])
    return {k: v[:80] for k, v in deps.items()}, scripts, bins[:30]


def first_paragraph(md_text):
    for block in re.split(r"\n\s*\n", md_text or ""):
        b = block.strip()
        if not b or b.startswith(("#", "!", "<", "[!", "|", "```", "[![", "---", "===")):
            continue
        b = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", b)
        b = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", b)
        b = re.sub(r"<[^>]+>", "", b).strip()
        if len(b) > 30:
            return re.sub(r"\s+", " ", b)[:400]
    return ""


def tree_lines(root, max_depth=3, max_entries=260):
    lines = []

    def rec(d, depth, prefix):
        try:
            items = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except OSError:
            return
        items = [x for x in items if x.name not in SKIP_DIRS and (not x.name.startswith(".") or x.name in KEEP_HIDDEN)
                 and str(x.resolve()) not in EXCLUDE]
        for i, x in enumerate(items):
            if len(lines) >= max_entries:
                return
            last = i == len(items) - 1
            lines.append(prefix + ("└── " if last else "├── ") + x.name + ("/" if x.is_dir() else ""))
            if x.is_dir() and depth < max_depth:
                rec(x, depth + 1, prefix + ("    " if last else "│   "))
        if len(lines) >= max_entries and not lines[-1].endswith("…"):
            lines.append(prefix + "…（更多用 list_dir 看）")

    rec(root, 1, "")
    return lines


# ---------------- 写材料 ----------------

def write_outputs(dest, meta, an, code_root):
    focus = meta.get("subdir") or ""
    root = code_root / focus if focus else code_root
    pre = "code/" + (focus + "/" if focus else "")

    # outline.md：仓库地图
    o = [f"# {meta['title']} · 仓库地图", ""]
    src = meta.get("source_url") or meta.get("local_path") or ""
    o.append(f"- 来源：{src}" + (f"（子目录 `{focus}`）" if focus else ""))
    if meta.get("commit"):
        o.append(f"- 提交：`{meta['commit'][:12]}`" + (f" · 分支 {meta['branch']}" if meta.get("branch") else ""))
    o.append(f"- 规模：{an['n_files']} 个文件 · 代码 {an['n_code_lines']:,} 行（全部文本 {an['n_lines']:,} 行）"
             + ("（文件太多，只统计了前 4 万个）" if an["truncated"] else ""))
    if meta.get("description"):
        o.append(f"- 简介：{meta['description']}")
    o += ["", "## 语言分布", "", "| 语言 | 文件 | 行数 | 占比 |", "|---|---:|---:|---:|"]
    o += [f"| {l['name']} | {l['files']} | {l['lines']:,} | {l['pct']}% |" for l in an["languages"][:12]]
    if an["other_files"]:
        o += ["", "文档 / 配置：" + "、".join(f"{x['name']} {x['files']}" for x in an["other_files"][:8])]
    o += ["", "## 目录树（3 层）", "", "```", f"{pre.rstrip('/')}/"] + tree_lines(root) + ["```"]
    if an["top_dirs"]:
        o += ["", "## 顶层目录", "", "| 目录 | 文件 | 代码行 | 主要语言 |", "|---|---:|---:|---|"]
        o += [f"| `{d['name']}` | {d['files']} | {d['lines']:,} | {d['lang']} |" for d in an["top_dirs"][:20]]
    o += ["", "## 入口候选", ""]
    o += [f"- `{pre}{e['path']}:{e['line']}` — {e['reason']}" for e in an["entry_points"][:20]] or ["- 没识别出明显入口（可能是库，入口在使用方）"]
    if meta.get("bins"):
        o += ["", "声明的命令 / 主模块："] + [f"- `{b['name']}` → `{b['target']}`（{b['from']}）" for b in meta["bins"][:15]]
    if meta.get("scripts"):
        o += ["", "## 脚本（package.json）", ""]
        for f, sc in meta["scripts"].items():
            o += [f"- {f}："] + [f"  - `{k}`: `{v}`" for k, v in list(sc.items())[:15]]
    if an["top_modules"]:
        o += ["", "## 被引用最多的内部模块（核心候选）", "", "| 模块 | 被几个文件引用 | 它引用几个 | 例如被谁引用 |", "|---|---:|---:|---|"]
        o += [f"| `{pre}{m['path']}` | {m['imported_by']} | {m['imports']} | {'、'.join('`' + x + '`' for x in m['examples'][:3])} |"
              for m in an["top_modules"][:15]]
    if meta.get("dependencies"):
        o += ["", "## 依赖", ""]
        o += [f"- `{f}`：{'、'.join(d[:30])}{' …' if len(d) > 30 else ''}" for f, d in meta["dependencies"].items()]
    o += ["", "## 测试 / CI / 文档", "",
          f"- 测试文件：{an['tests']['files']} 个" + (f"，如 {'、'.join('`' + x + '`' for x in an['tests']['examples'][:5])}" if an["tests"]["examples"] else ""),
          "- CI：" + ("、".join(f"`{x}`" for x in an["ci"]) or "无"),
          "- 文档：" + ("、".join(f"`{x}`" for x in an["docs"][:12]) or "无"),
          "- 许可证：" + (meta.get("license") or "、".join(an["licenses"]) or "没找到 LICENSE")]
    if an["largest"]:
        o += ["", "## 最大的源文件", ""] + [f"- `{pre}{x['path']}` · {x['lines']:,} 行" for x in an["largest"][:10]]
    (dest / "outline.md").write_text("\n".join(o) + "\n", encoding="utf-8")

    # repo.md：README + 依赖清单原文
    r = [f"# {meta['title']}", "", f"来源：{src}", ""]
    if an["readme"]:
        r += [f"## README（{an['readme']}）", "", read_text(root / an["readme"], 60_000)[:40_000], ""]
    else:
        r += ["## README", "", "（仓库里没有 README）", ""]
    r += ["## 依赖清单原文", ""]
    for rel in an["manifests"][:12]:
        t = read_text(root / rel, 20_000)[:5000]
        if t:
            lang = {"package.json": "json", "pyproject.toml": "toml", "Cargo.toml": "toml", "go.mod": ""}.get(Path(rel).name, "")
            r += [f"### {rel}", "", "```" + lang, t.rstrip(), "```", ""]
    (dest / "repo.md").write_text("\n".join(r), encoding="utf-8")

    # symbols.md / symbols.json
    s = [f"# 符号索引（{len(an['symbols'])} 个文件；路径相对 {pre or 'code/'}）", ""]
    for rel in sorted(an["symbols"]):
        s.append(f"## {pre}{rel}")
        s += [f"- L{x['line']} {x['kind']} `{x['name']}{x.get('sig', '')}`" for x in an["symbols"][rel]]
        s.append("")
    (dest / "symbols.md").write_text("\n".join(s), encoding="utf-8")
    (dest / "symbols.json").write_text(json.dumps({"prefix": pre, "files": an["symbols"]}, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="把一个代码仓库（GitHub / Git 链接或本机文件夹）备成代码分析材料")
    ap.add_argument("target", help="GitHub / Git 链接、owner/repo、本机代码文件夹，或已有的分析目录")
    ap.add_argument("--root", help="分析目录的上一级（目录名自动生成）")
    ap.add_argument("--dest", help="分析目录完整路径")
    ap.add_argument("--slug", help="目录名")
    ap.add_argument("--ref", help="分支 / 标签 / 提交号（默认仓库默认分支）")
    ap.add_argument("--subdir", help="只分析仓库里的某个子目录")
    ap.add_argument("--from-paper", help="从哪篇论文的工作区跳过来的（论文目录名，记进 meta.json）")
    ap.add_argument("--paper-title", help="那篇论文的标题")
    ap.add_argument("--title", help="显示名（默认用仓库名 / 文件夹名）")
    args = ap.parse_args()

    try:
        t = parse_target(args.target)
    except ValueError as e:
        sys.exit(f"  ✗ {e}")
    prev = {}
    if t["kind"] == "workspace":  # 刷新已有分析目录
        prev = t["meta"]
        dest = t["path"]
        src = prev.get("source")
        if src == "local":
            t = {"kind": "local", "path": Path(prev.get("local_path") or prev.get("code_dir"))}
        elif src == "github":
            t = parse_target(prev["source_url"])
        else:
            t = {"kind": "git", "url": prev.get("source_url"), "clone_url": prev.get("clone_url") or prev.get("source_url"),
                 "repo": prev.get("title"), "ref": None, "subdir": ""}
        t["ref"] = args.ref or prev.get("ref") or t.get("ref")
        t["subdir"] = args.subdir if args.subdir is not None else (prev.get("subdir") or t.get("subdir") or "")
    else:
        if args.ref:
            t["ref"] = args.ref
        if args.slug and (args.slug in (".", "..") or re.search(r'[\\/:*?"<>|]', args.slug)):
            sys.exit("  ✗ 目录名不能包含路径分隔符或特殊字符")
        if args.subdir is not None:
            t["subdir"] = args.subdir.strip("/\\")
        if args.title and not args.slug:
            slug = slugify(args.title)
        elif t["kind"] == "github":
            slug = args.slug or slugify(t["owner"], t["repo"], t["subdir"].split("/")[-1] if t.get("subdir") else "")
        elif t["kind"] == "git":
            slug = args.slug or slugify(t["repo"], t["subdir"].split("/")[-1] if t.get("subdir") else "")
        else:
            slug = args.slug or slugify(t["path"].name, (t.get("subdir") or "").split("/")[-1])
        if args.dest:
            dest = Path(args.dest).expanduser()
        else:
            root = Path(args.root or "repos").expanduser()
            dest = root / slug
            src_key = t.get("url") or str(t.get("path"))
            n = 2
            while (dest / "meta.json").exists():  # 同名目录是另一个仓库：换个名字
                try:
                    old = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
                except ValueError:
                    old = {}
                if (old.get("source_url") or old.get("local_path")) == src_key and old.get("subdir", "") == t.get("subdir", ""):
                    prev = old
                    break
                dest = root / f"{slug}-{n}"
                n += 1
    dest = dest.resolve()
    if t["kind"] == "local":
        source = Path(t["path"]).resolve()
        if dest == source or dest in source.parents:
            sys.exit("  ✗ 分析目录不能覆盖代码文件夹或它的上级目录，换一个 --root / --dest")
    created = not dest.exists()
    dest.mkdir(parents=True, exist_ok=True)

    def fail(msg):  # 新建的目录导入失败：删掉，免得资料库里多一个空条目
        if created:
            shutil.rmtree(dest, ignore_errors=True)
        sys.exit(f"  ✗ {msg}")

    log(f"  → {dest}")

    warnings = []
    meta = {"kind": "repo", "fetched": datetime.date.today().isoformat(), "subdir": t.get("subdir") or "",
            "ref": t.get("ref")}
    for key in ("from_paper", "paper_title"):
        if getattr(args, key) or prev.get(key):
            meta[key] = getattr(args, key) or prev.get(key)

    if t["kind"] == "local":
        code_root = Path(t["path"]).resolve()
        if not code_root.is_dir():
            fail(f"文件夹不存在：{code_root}")
        if dest == code_root:
            fail("分析目录不能就是被分析的代码文件夹，换一个 --root")
        for d in [dest, *dest.parents]:  # 比如分析 Bling-Workspace 自己：跳过 repos/ 和 papers/
            if code_root in d.parents:
                EXCLUDE.add(str(d))
        gi = local_git_info(code_root)
        meta.update(source="local", local_path=str(code_root), source_url=None, title=code_root.name,
                    commit=gi.get("commit"), branch=gi.get("branch"), remote=gi.get("remote"))
        if gi.get("remote"):
            m = GH_RE.match(gi["remote"]) or GH_SSH.match(gi["remote"])
            if m:
                meta["remote_url"] = f"https://github.com/{m.group(1)}/{m.group(2)}"
        log(f"  ✓ 本机文件夹（只读分析，不复制）：{code_root}")
    else:
        code_root = dest / "code"
        title = t["repo"]
        meta.update(source=t["kind"], source_url=t["url"], title=title)
        if t["kind"] == "github":
            meta["owner"] = t["owner"]
            try:
                g = github_api(t["owner"], t["repo"])
                meta.update(title=g.get("name") or title, description=g.get("description") or "",
                            stars=g.get("stargazers_count"), forks=g.get("forks_count"),
                            license=((g.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", "") or None,
                            topics=g.get("topics") or [], homepage=g.get("homepage") or "",
                            default_branch=g.get("default_branch"), pushed_at=g.get("pushed_at"),
                            archived=g.get("archived", False))
                log(f"  ✓ GitHub：{t['owner']}/{meta['title']} · ★ {meta.get('stars')} · {meta.get('description') or '无简介'}")
            except (urllib.error.URLError, OSError, ValueError) as e:
                warnings.append(f"GitHub API 读不到（{e}），不影响分析代码")
                log(f"  · GitHub API 读不到（{e}），继续克隆")
        clone_url = t.get("clone_url") or (t["url"] + ".git")
        meta["clone_url"] = clone_url
        state, note = clone(clone_url, code_root, t.get("ref"))
        if state == "exists" and t["kind"] == "github" and not (code_root / ".git").exists():
            try:
                github_zip(t["owner"], t["repo"], t.get("ref"), code_root)
                note = "已刷新 zip 代码快照（没有 git 历史）"
            except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as e:
                warnings.append(f"刷新 zip 失败，沿用之前的代码快照：{e}")
                note = "刷新失败，沿用之前的代码快照"
        if state in ("no-git", "failed") and t["kind"] == "github":
            log(f"  · git 克隆不可用（{note}），改为下载 zip…")
            try:
                shutil.rmtree(code_root, ignore_errors=True)
                github_zip(t["owner"], t["repo"], t.get("ref"), code_root)
                state, note = "ok", "已下载 zip（没有 git 历史）"
                warnings.append("用 zip 下载的代码，没有 git 历史；装了 git 后重新导入可以拿到提交号")
            except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as e:
                fail(f"克隆和 zip 下载都失败了：{note} / {e}。检查网络或代理，或者先手动 git clone，再把文件夹路径填进来。")
        elif state in ("no-git", "failed"):
            fail(f"克隆失败：{note}。检查链接和网络，或者先手动 git clone，再把文件夹路径填进来。")
        log(f"  ✓ 代码：{note} → {code_root}")
        gi = local_git_info(code_root) if (code_root / ".git").exists() else {}
        meta.update(commit=gi.get("commit"), branch=gi.get("branch") if gi.get("branch") != "HEAD" else t.get("ref"))
    meta["code_dir"] = str(code_root)
    if args.title or prev.get("custom_title"):
        meta["title"] = meta["custom_title"] = args.title or prev["custom_title"]

    log("  … 分析目录结构、语言、入口、符号、模块依赖")
    try:
        an = analyze(code_root, meta["subdir"])
    except ValueError as e:
        fail(str(e))
    root = code_root / meta["subdir"] if meta["subdir"] else code_root
    deps, scripts, bins = parse_manifests(root, an["manifests"])
    readme_text = read_text(root / an["readme"], 60_000) if an["readme"] else ""
    meta.update(
        title=meta.get("title") + (f" / {meta['subdir']}" if meta["subdir"] else ""),
        summary=meta.get("description") or first_paragraph(readme_text),
        languages=an["languages"], other_files=an["other_files"], n_files=an["n_files"], n_lines=an["n_lines"],
        n_code_lines=an["n_code_lines"], manifests=an["manifests"], dependencies=deps, scripts=scripts, bins=bins,
        entry_points=an["entry_points"], top_modules=an["top_modules"], top_dirs=an["top_dirs"],
        tests=an["tests"], ci=an["ci"], docs=an["docs"], readme=an["readme"], largest=an["largest"],
        n_symbol_files=len(an["symbols"]), n_symbols=sum(len(v) for v in an["symbols"].values()),
        official_code=meta.get("source_url") or meta.get("remote_url"),
        authors=[meta["owner"]] if meta.get("owner") else [],
        published=(meta.get("pushed_at") or "")[:10],
        warnings=warnings + (["文件超过 4 万个，只统计了前 4 万个"] if an["truncated"] else []),
    )
    if not meta.get("license") and an["licenses"]:
        meta["license"] = an["licenses"][0]
    write_outputs(dest, meta, an, code_root)
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    lang_line = " · ".join(f"{l['name']} {l['pct']}%" for l in an["languages"][:4]) or "没识别出源代码"
    log(f"  ✓ {an['n_files']} 个文件 · 代码 {an['n_code_lines']:,} 行 · {lang_line}")
    log(f"  ✓ 入口候选 {len(an['entry_points'])} 个 · 符号 {meta['n_symbols']} 个（{meta['n_symbol_files']} 个文件）"
        f" · 内部依赖 {an['n_edges']} 条 · 依赖清单 {len(an['manifests'])} 个")
    log("  ✓ meta.json · outline.md · repo.md · symbols.md")
    log("下一步：读 outline.md（仓库地图）和 repo.md（README），再按 references/code-reading.md 七站开讲。")


if __name__ == "__main__":
    main()
