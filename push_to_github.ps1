# 把本目录推到 https://github.com/Bling-sun/bling-paper-reading
# 由 push_to_github.bat 调用。第一次推送会弹出 GitHub 登录窗口（Git Credential Manager），用你的账号登录即可。
# 提交说明自动生成（改了哪些文件 + 时间），全程不用输入；想自己写说明：push_to_github.bat "说明文字"
param([string]$Message = '')
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Remote = 'https://github.com/Bling-sun/bling-paper-reading.git'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
# 去掉控制字符：Windows 控制台里输入中文时，Read-Host / 命令行参数偶尔会混进 NUL 字符，git 会拒绝这样的提交说明
function Get-SafeText([string]$t) { if (-not $t) { return '' }; return (($t -replace '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '') -replace [char]0xFFFD, '').Trim() }
function Fail($msg) { Say ''; Say "✗ $msg" 'Red'; Read-Host '按回车关闭窗口' | Out-Null; exit 1 }

function Find-Git {
    $g = Get-Command git -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    foreach ($p in @("$env:ProgramFiles\Git\cmd\git.exe", "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe", "${env:ProgramFiles(x86)}\Git\cmd\git.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

Say ''
Say '==== 上传到 GitHub：Bling-sun/bling-paper-reading ====' 'Cyan'

$git = Find-Git
if (-not $git) {
    Say '没找到 git。' 'Yellow'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $ans = Read-Host '现在用 winget 自动安装 Git 吗？（可能会弹出管理员确认）[Y/n]'
        if ($ans -eq '' -or $ans -match '^[Yy]') {
            winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
            $git = Find-Git
        }
    }
    if (-not $git) {
        Start-Process 'https://git-scm.com/download/win'
        Fail '请先安装 Git（默认选项一路下一步即可），装完重新双击 push_to_github.bat。'
    }
}
Say "git：$git"

# 不该进仓库的东西：旧文件夹、截图、虚拟环境、本机设置（含 API Key）、论文材料
$must = @('kelip-paper-reading-main/', 'Claude outputs/', '.venv/', 'web/config.json', 'web/_uploads/', 'papers/', 'profile.md')
$gi = if (Test-Path .gitignore) { Get-Content .gitignore -Encoding UTF8 } else { @() }
$add = $must | Where-Object { $gi -notcontains $_ }
if ($add) {
    Add-Content .gitignore -Encoding UTF8 -Value ("`n# 本机文件，不上传`n" + ($add -join "`n"))
}

if (-not (Test-Path .git)) {
    & $git init -q
    & $git symbolic-ref HEAD refs/heads/main
}
& $git config core.autocrlf true
& $git config core.safecrlf false   # 不再刷屏「LF will be replaced by CRLF」（换行符由 .gitattributes 统一处理，无害）
& $git config core.quotepath false
& $git config i18n.commitEncoding utf-8

# 提交者信息（只在这个仓库里设置，不改你的全局配置）
$name = & $git config user.name 2>$null
if (-not $name) { & $git config user.name 'Bling-sun' }
$email = & $git config user.email 2>$null
if (-not $email) {
    $email = Get-SafeText (Read-Host '提交用的邮箱（直接回车用 bing.sun@int.visionnav.com）')
    if ($email -notmatch '^[^@\s]+@[^@\s]+$') { $email = 'bing.sun@int.visionnav.com' }
    & $git config user.email $email
}

$remotes = & $git remote
if ($remotes -contains 'origin') { & $git remote set-url origin $Remote } else { & $git remote add origin $Remote }

& $git add -A
# 再确认一次：API Key 所在的设置文件绝不能进仓库
$staged = & $git diff --cached --name-only
if ($staged -contains 'web/config.json') { & $git rm -q --cached web/config.json; Fail 'web/config.json（含 API Key）被加进来了，已撤回，请检查 .gitignore 后重试。' }

& $git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    # 提交说明直接用 -m 传给 git，不写临时文件：
    # 公司电脑上的文件加密软件会把 PowerShell 新建的文件加密（文件头 %TSD-Header-###%），git 读到的是密文，
    # 就会报「a NUL byte in commit log message not allowed」。
    & $git rev-parse -q --verify HEAD *> $null
    if ($LASTEXITCODE -eq 0) {  # 不是第一次提交：自动写说明，不用输入
        $files = @(& $git diff --cached --name-only | ForEach-Object { Get-SafeText $_ } | Where-Object { $_ })
        $names = ($files | Select-Object -First 3 | ForEach-Object { Split-Path $_ -Leaf }) -join '、'
        $more = if ($files.Count -gt 3) { " 等 $($files.Count) 个文件" } else { '' }
        $paras = @("更新 $names$more（$(Get-Date -Format 'yyyy-MM-dd HH:mm')）")
        $custom = Get-SafeText $Message
        if ($custom) { $paras = @($custom) + $paras }
    } else {
        $paras = @(
            'bling-paper-reading：网页端精读工作台 + HTML 精读笔记',
            "- web/：导入 → PDF / 图表 / 大纲 / 代码阅读 → 按 SKILL.md 六站讨论 → 分节精读笔记 → 导出单文件 HTML`n- 精读笔记改为 HTML（references/notes-template.html），SKILL.md / README 同步`n- 模型接口：本机 Claude Code / 本机 Codex（会员额度）/ DeepSeek / Claude API / OpenAI 兼容`n- 项目更名为 bling-paper-reading；start.bat 一键装 Python、建 .venv、启动网页端",
            "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01SpfPukjpBKv4ewRSdoWrtu"
        )
    }
    $margs = @()
    foreach ($p in $paras) {
        $t = Get-SafeText (($p -replace "`r", '') -replace '"', "'")  # Windows PowerShell 5.1 传带双引号的参数会出错
        if ($t) { $margs += '-m'; $margs += $t }
    }
    & $git commit -q @margs
    if ($LASTEXITCODE -ne 0) { Fail '提交失败（看上面的报错）。' }
    Say '✓ 已在本地提交' 'Green'
} else {
    Say '没有新的改动需要提交。'
}

# GitHub 上建仓库时如果勾了 README / License，远端已经有提交：先合进来（冲突的文件以本地为准），再推
Say '连接 GitHub（第一次会弹出登录窗口）…'
$heads = & $git ls-remote --heads origin 2>&1
if ($LASTEXITCODE -ne 0) { Say "$heads" 'Yellow'; Fail '连不上 GitHub 仓库。检查网络 / 仓库地址，或者登录的账号是不是 Bling-sun。' }
$remoteBranch = $null
if ("$heads" -match 'refs/heads/main') { $remoteBranch = 'main' } elseif ("$heads" -match 'refs/heads/master') { $remoteBranch = 'master' }
if ($remoteBranch) {
    & $git fetch -q origin $remoteBranch
    & $git merge-base --is-ancestor "origin/$remoteBranch" HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $git merge --allow-unrelated-histories -X ours --no-edit "origin/$remoteBranch"
        if ($LASTEXITCODE -ne 0) { Fail '和 GitHub 上已有的内容合并失败（看上面的报错）。' }
    }
}
$branch = (& $git rev-parse --abbrev-ref HEAD).Trim()
& $git push -u origin "${branch}:main"
if ($LASTEXITCODE -ne 0) { Fail '推送失败（看上面的报错）。常见原因：登录的不是 Bling-sun 账号，或者网络连不上 github.com。' }

Say ''
Say '✓ 已上传：https://github.com/Bling-sun/bling-paper-reading' 'Green'
Start-Process 'https://github.com/Bling-sun/bling-paper-reading'
Read-Host '按回车关闭窗口' | Out-Null
