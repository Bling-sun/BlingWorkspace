# 把本目录推到 https://github.com/Bling-sun/bling-paper-reading
# 由 push_to_github.bat 调用（优先用 Codex 自带的 PowerShell 7 和 git，和 D:\Personal Plan 里能成功上传的脚本同一套做法）。
# 提交说明自动生成；想自己写：push_to_github.bat "说明文字"。只检查不上传：push_to_github.bat -Check
param([string]$Message = '', [switch]$Check)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # PowerShell 7：git 非 0 退出码由下面自己判断
Set-Location -LiteralPath $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$RemoteUrl = 'https://github.com/Bling-sun/bling-paper-reading.git'
$RepoPage = 'https://github.com/Bling-sun/bling-paper-reading'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }

# ---------- 选 git ----------
# 1) Codex 自带的 git（这台电脑上用它推送能成功）
# 2) 已安装 Git 的 mingw64\bin\git.exe 本体（不经过 cmd\git.exe 启动器）
# 3) PATH 里的 git
function Find-Git {
    # 用 [IO.Path]::Combine / [IO.File]::Exists：Join-Path、Test-Path 碰到不存在的盘符（比如没有 D 盘）会直接报错
    $c = @()
    if ($env:USERPROFILE) { $c += [System.IO.Path]::Combine($env:USERPROFILE, '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\mingw64\bin\git.exe') }
    $onPath = Get-Command git -ErrorAction SilentlyContinue
    $roots = @('D:\Git', $env:ProgramFiles, $env:LOCALAPPDATA)
    if ($onPath) { $roots = @([System.IO.Path]::GetDirectoryName([System.IO.Path]::GetDirectoryName($onPath.Source))) + $roots }
    foreach ($root in $roots) {
        if (-not $root) { continue }
        foreach ($sub in @('mingw64\bin\git.exe', 'Git\mingw64\bin\git.exe', 'Programs\Git\mingw64\bin\git.exe')) {
            $c += [System.IO.Path]::Combine($root, $sub)
        }
    }
    if ($onPath) { $c += $onPath.Source }
    foreach ($p in $c) { if ($p -and [System.IO.File]::Exists($p)) { return $p } }
    return $null
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArguments)
    & $script:Git --no-pager -c maintenance.auto=false @GitArguments
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArguments[0]) 失败（退出码 $LASTEXITCODE）" }
}

# 提交说明里不能有控制字符（git 会拒绝 NUL）；双引号在 Windows PowerShell 5.1 传参时会出错，换成单引号
function Get-SafeText([string]$t) {
    if (-not $t) { return '' }
    return ((($t -replace "`r", '') -replace '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '') -replace [char]0xFFFD, '' -replace '"', "'").Trim()
}

try {
    Say ''
    Say '==== 上传到 GitHub：Bling-sun/bling-paper-reading ====' 'Cyan'
    $script:Git = Find-Git
    if (-not $script:Git) {
        Start-Process 'https://git-scm.com/download/win'
        throw '没找到 git。请先安装 Git（默认选项一路下一步），装完重新双击 push_to_github.bat。'
    }
    Say "git：$script:Git"

    # 不该进仓库的东西
    $must = @('kelip-paper-reading-main/', 'Claude outputs/', '.venv/', 'web/config.json', 'web/_uploads/', 'papers/', 'profile.md', '__pycache__/')
    $gi = if (Test-Path .gitignore) { Get-Content .gitignore -Encoding UTF8 } else { @() }
    $add = $must | Where-Object { $gi -notcontains $_ }
    if ($add) { throw (".gitignore 缺少这些规则，为安全起见不上传：" + ($add -join '、')) }

    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.git'))) {
        Invoke-Git init -b main
    }
    Invoke-Git config core.autocrlf true
    Invoke-Git config core.safecrlf false
    Invoke-Git config core.quotepath false

    $remotes = @(& $script:Git --no-pager remote)
    if ($remotes -contains 'origin') {
        $origin = (& $script:Git --no-pager remote get-url origin | Out-String).Trim()
        if ($origin -notin @($RemoteUrl, ($RemoteUrl -replace '\.git$', ''), 'git@github.com:Bling-sun/bling-paper-reading.git')) {
            throw "origin 指向 $origin，不是 Bling-sun/bling-paper-reading，没有上传。"
        }
    } else {
        Invoke-Git remote add origin $RemoteUrl
    }

    & $script:Git --no-pager config user.name *> $null
    if ($LASTEXITCODE -ne 0) { Invoke-Git config user.name Bling-sun }
    & $script:Git --no-pager config user.email *> $null
    if ($LASTEXITCODE -ne 0) { Invoke-Git config user.email Bling-sun@users.noreply.github.com }

    Invoke-Git add -A
    # 再确认一次：API Key 所在的设置文件绝不能进仓库
    $staged = @(& $script:Git --no-pager diff --cached --name-only)
    if ($staged -contains 'web/config.json') {
        & $script:Git --no-pager rm -q --cached web/config.json
        throw 'web/config.json（含 API Key）被加进来了，已撤回，请检查 .gitignore 后重试。'
    }
    if ($Check) { Say '检查通过：git 可用、远程地址正确、不会上传 API Key。' 'Green'; exit 0 }

    # ---------- 提交（说明直接用 -m 传，不写临时文件：这台电脑会把 PowerShell 新建的文件加密） ----------
    & $script:Git --no-pager diff --cached --quiet
    $diffExit = $LASTEXITCODE
    if ($diffExit -eq 1) {
        & $script:Git --no-pager rev-parse -q --verify HEAD *> $null
        if ($LASTEXITCODE -eq 0) {
            $names = ($staged | Select-Object -First 3 | ForEach-Object { Split-Path $_ -Leaf }) -join '、'
            $more = if ($staged.Count -gt 3) { " 等 $($staged.Count) 个文件" } else { '' }
            $paras = @("更新 $names$more（$(Get-Date -Format 'yyyy-MM-dd HH:mm')）")
            if (Get-SafeText $Message) { $paras = @((Get-SafeText $Message)) + $paras }
        } else {
            $paras = @(
                'bling-paper-reading：网页端精读工作台 + HTML 精读笔记',
                "- web/：导入 → PDF / 图表 / 大纲 / 代码阅读 → 按 SKILL.md 六站讨论 → 分节精读笔记 → 导出单文件 HTML`n- 精读笔记改为 HTML（references/notes-template.html），SKILL.md / README 同步`n- 模型接口：本机 Claude Code / 本机 Codex（会员额度）/ DeepSeek / Claude API / OpenAI 兼容`n- 项目更名为 bling-paper-reading；start.bat 一键装 Python、建 .venv、启动网页端",
                "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01SpfPukjpBKv4ewRSdoWrtu"
            )
        }
        $margs = @()
        foreach ($p in $paras) { $t = Get-SafeText $p; if ($t) { $margs += '-m'; $margs += $t } }
        Invoke-Git commit -q @margs
        Say '✓ 已在本地提交' 'Green'
    } elseif ($diffExit -eq 0) {
        Say '没有新的改动需要提交。'
    } else {
        throw '检查暂存区失败。'
    }

    # ---------- GitHub 上已有提交（比如建仓库时勾了 README）：先合进来，冲突的文件以本地为准 ----------
    Say '连接 GitHub（第一次会弹出登录窗口）…'
    $heads = (& $script:Git --no-pager ls-remote --heads origin | Out-String)
    if ($LASTEXITCODE -ne 0) { throw '连不上 GitHub 仓库：检查网络 / 代理，或者登录的账号是不是 Bling-sun。' }
    if ($heads -match 'refs/heads/main') {
        Invoke-Git fetch -q origin main
        & $script:Git --no-pager merge-base --is-ancestor origin/main HEAD
        if ($LASTEXITCODE -ne 0) { Invoke-Git merge --allow-unrelated-histories -X ours --no-edit origin/main }
    }

    Invoke-Git push -u origin HEAD:main
    Say ''
    Say "✓ 已上传：$RepoPage" 'Green'
    Say '本机设置（API Key）、论文材料、虚拟环境都没有上传。'
    exit 0
} catch {
    Say ''
    Say ('✗ 上传失败：' + $_.Exception.Message) 'Red'
    Say '检查 GitHub 登录、仓库权限和网络 / 代理设置。没有做强制推送。' 'Yellow'
    exit 1
}
