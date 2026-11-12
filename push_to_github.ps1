# 把本目录（Bling-Workspace）推到 https://github.com/Bling-sun/bling-paper-reading（GitHub 上改名后同步改下面的 $RemoteUrl / $RepoPage）
# 由 push_to_github.bat 调用（用本机 Codex 自带的 PowerShell 7）。
# 优先使用 Git 的 ucrt64 / mingw64 本体，避免 cmd 启动器及凭据回调再次触发启动错误。
# 网络请求一律显式走代理 http://127.0.0.1:7897；
# 登录复用 Git Credential Manager 里已保存的 GitHub 凭据，不需要也不保存任何 token。
#   push_to_github.bat              提交改动 → 只读检查连接 → 推送 → 核对远程提交
#   push_to_github.bat -Check       只做检查（origin、敏感文件、GitHub 连接），不提交不推送
#   push_to_github.bat -Message "说明"
param(
    [string]$Message = '',
    [switch]$Check,
    [string]$Proxy = 'http://127.0.0.1:7897'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # git 的退出码由下面自己判断
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$repo = $PSScriptRoot                                 # 即 D:\CODE\Bling-Workspace
$RemoteUrl = 'https://github.com/Bling-sun/bling-paper-reading.git'
$RepoPage = 'https://github.com/Bling-sun/bling-paper-reading'

# 绝不能上传的东西：.gitignore 必须有这些规则，推送前还会再查一遍要推的提交里有没有
$MustIgnore = @('web/config.json', 'web/_uploads/', '.venv/', 'papers/', 'repos/', 'profile.md', '__pycache__/')
$Forbidden = '^(web/config\.json|web/_uploads/|\.venv/|papers/|repos/|profile\.md$)|(^|/)__pycache__/'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }

function Find-NativeGit {
    $onPath = Get-Command git -ErrorAction SilentlyContinue
    $roots = @()
    if ($onPath) { $roots += Split-Path (Split-Path $onPath.Source -Parent) -Parent }
    $roots += 'D:\Git'
    $roots += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git'
    foreach ($root in ($roots | Select-Object -Unique)) {
        foreach ($relative in @('ucrt64\bin\git.exe','mingw64\bin\git.exe')) {
            $candidate = Join-Path $root $relative
            if (Test-Path -LiteralPath $candidate) { return (Get-Item -LiteralPath $candidate).FullName }
        }
    }
    if ($onPath) { return $onPath.Source }
    throw '没找到可用的 Git，请安装 Git for Windows。'
}

# 所有 git 调用都带 --no-pager 和 -C $repo；联网的命令（ls-remote / fetch / push）再显式带上代理
function Git-Out {
    # 用 $args 而不是声明参数：git 的 -A / -m / -q 之类会被 PowerShell 当成函数自己的参数名
    $A = @($args)
    $out = & $script:GitExe --no-pager -C $repo -c maintenance.auto=false @A
    return @{ code = $LASTEXITCODE; out = @($out) }
}
function Git-Run {
    # 用 $args 而不是声明参数：git 的 -A / -m / -q 之类会被 PowerShell 当成函数自己的参数名
    $A = @($args)
    & $script:GitExe --no-pager -C $repo -c maintenance.auto=false @A
    if ($LASTEXITCODE -ne 0) { throw "git $($A[0]) 失败（退出码 $LASTEXITCODE）" }
}
function Git-Net {
    # 用 $args 而不是声明参数：git 的 -A / -m / -q 之类会被 PowerShell 当成函数自己的参数名
    $A = @($args)
    $out = & $script:GitExe --no-pager -C $repo -c "http.proxy=$Proxy" @script:CredArgs @A
    return @{ code = $LASTEXITCODE; out = @($out) }
}

# 提交说明里不能有控制字符（git 拒绝 NUL）
function Get-SafeText([string]$t) {
    if (-not $t) { return '' }
    return ((($t -replace "`r", '') -replace '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '') -replace [char]0xFFFD, '').Trim()
}

try {
    Say ''
    Say '==== Bling-Workspace · 上传到 GitHub ====' 'Cyan'

    # ---------- 1. Git ----------
    $script:GitExe = Find-NativeGit
    # push 会调用凭据程序；凭据程序也可能再次调用 git。
    # 让子进程同样优先找到本体，而不是 PATH 中的 cmd\git.exe 启动器。
    $nativeBin = Split-Path $script:GitExe -Parent
    $env:PATH = $nativeBin + [IO.Path]::PathSeparator + $env:PATH
    Say "git：$script:GitExe（$((& $script:GitExe --no-pager --version) -join ' ')）"
    Say "仓库：$repo"
    Say "代理：$Proxy"

    # 登录：复用 Git Credential Manager。全局已配置就照用；没配置时只对这几次联网命令临时指定 manager
    $script:CredArgs = @()
    $helper = (Git-Out config --get credential.helper).out -join ''
    if (-not $helper) { $script:CredArgs = @('-c', 'credential.helper=manager') }

    # ---------- 2. 仓库、origin、敏感文件 ----------
    if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) { Git-Run init -b main }
    $remotes = (Git-Out remote).out
    if ($remotes -contains 'origin') {
        $origin = ((Git-Out remote get-url origin).out -join '').Trim()
        if ($origin -ne $RemoteUrl) { throw "origin 是 $origin，不是 $RemoteUrl。为安全起见没有上传，请确认后手动改：git remote set-url origin $RemoteUrl" }
    } else {
        Git-Run remote add origin $RemoteUrl
    }
    Say "origin：$RemoteUrl"

    $gi = if (Test-Path -LiteralPath (Join-Path $repo '.gitignore')) { Get-Content -LiteralPath (Join-Path $repo '.gitignore') -Encoding UTF8 } else { @() }
    $missing = $MustIgnore | Where-Object { $gi -notcontains $_ }
    if ($missing) { throw (".gitignore 缺少这些规则，为安全起见不上传：" + ($missing -join '、')) }

    & $script:GitExe --no-pager -C $repo config user.name *> $null
    if ($LASTEXITCODE -ne 0) { Git-Run config user.name Bling-sun }
    & $script:GitExe --no-pager -C $repo config user.email *> $null
    if ($LASTEXITCODE -ne 0) { Git-Run config user.email Bling-sun@users.noreply.github.com }

    # ---------- 3. 提交本地改动（说明用 -m 直接传，不写临时文件） ----------
    if ($Check) {
        # 只读：不动暂存区，用 git add 的演习模式看会加进哪些文件
        $staged = @((Git-Out add -A --dry-run).out | ForEach-Object { if ($_ -match "^(?:add|remove) '(.+)'$") { $Matches[1] } })
    } else {
        Git-Run add -A
        $staged = @((Git-Out diff --cached --name-only).out | Where-Object { $_ })
    }
    $bad = $staged | Where-Object { $_ -match $Forbidden }
    if ($bad) { if (-not $Check) { Git-Run reset -q }; throw ("这些文件不该上传" + $(if ($Check) { '' } else { '，已撤回暂存' }) + "：" + ($bad -join '、')) }

    if ($Check) {
        Say "待提交的改动：$($staged.Count) 个文件（-Check 模式不提交）"
    } elseif ($staged.Count -gt 0) {
        $hasHead = (Git-Out rev-parse -q --verify HEAD).code -eq 0
        if ($hasHead) {
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
        Git-Run commit -q @margs
        Say "✓ 已在本地提交（$($staged.Count) 个文件）" 'Green'
    } else {
        Say '没有新的改动需要提交。'
    }

    # ---------- 4. 只读检查 GitHub 连接 ----------
    Say ''
    Say '只读检查 GitHub 连接（ls-remote）…'
    $ls = Git-Net ls-remote origin
    if ($ls.code -ne 0) { throw "GitHub 连接失败（退出码 $($ls.code)）：确认代理软件开着（$Proxy），并且已用 Bling-sun 登录。" }
    $remoteMain = ($ls.out | Where-Object { $_ -match "`trefs/heads/main$" } | ForEach-Object { ($_ -split "`t")[0] }) | Select-Object -First 1
    Say ("✓ 连接正常；远程 main：" + $(if ($remoteMain) { $remoteMain.Substring(0, 7) } else { '（空仓库）' })) 'Green'
    if ($Check) { Say '检查通过，没有提交、没有推送。' 'Green'; exit 0 }

    # ---------- 5. 确认要推的内容 ----------
    $localHead = ((Git-Out rev-parse HEAD).out -join '').Trim()
    if (-not $localHead) { throw '本地还没有任何提交，没有可上传的内容。' }
    if ($remoteMain -eq $localHead) { Say "远程已经是最新（$($localHead.Substring(0, 7))），不需要推送。" 'Green'; exit 0 }

    if ($remoteMain) {
        $f = Git-Net fetch -q origin main
        if ($f.code -ne 0) { throw "拉取远程 main 失败（退出码 $($f.code)）。" }
        & $script:GitExe --no-pager -C $repo merge-base --is-ancestor origin/main HEAD
        if ($LASTEXITCODE -ne 0) {
            # 不自动合并、不强推：远程有本地没有的提交，交给用户决定
            throw ("GitHub 上的 main 有本地没有的提交（$($remoteMain.Substring(0, 7))），已停止，没有推送。`n" +
                   "  看一下远程多了什么：git --no-pager -C `"$repo`" log --oneline HEAD..origin/main`n" +
                   "  确认后再决定怎么合并；本脚本不会自动合并或强制推送。")
        }
        $range = 'origin/main..HEAD'
    } else {
        $range = 'HEAD'
    }
    $commits = @((Git-Out log --oneline $range).out)
    $files = @((Git-Out ls-tree -r --name-only HEAD).out)
    $historicalFiles = @((Git-Out log --format= --name-only $range).out | Where-Object { $_ } | Sort-Object -Unique)
    $leak = @($files + $historicalFiles) | Where-Object { $_ -match $Forbidden } | Sort-Object -Unique
    if ($leak) { throw ("要推送的提交里有不该上传的文件，已停止：" + ($leak -join '、')) }
    Say ''
    Say "将推送 $($commits.Count) 个提交（仓库里共 $($files.Count) 个文件，已检查敏感文件路径及待推送历史）："
    $commits | Select-Object -First 10 | ForEach-Object { Say "  $_" }

    # ---------- 6. 推送并核对 ----------
    Say ''
    Say '推送中…'
    $push = Git-Net push -u origin HEAD:main
    $push.out | ForEach-Object { Say "  $_" }
    if ($push.code -ne 0) { throw "推送失败（退出码 $($push.code)），不能算上传成功。" }

    $verify = Git-Net ls-remote origin refs/heads/main
    $after = ($verify.out | ForEach-Object { ($_ -split "`t")[0] }) | Select-Object -First 1
    if ($verify.code -ne 0 -or $after -ne $localHead) {
        throw "推送命令返回成功，但核对远程提交没对上（远程 $after，本地 $localHead）。请到 $RepoPage 看一下。"
    }
    Say ''
    Say "✓ 上传完成：远程 main = $($after.Substring(0, 7))，和本地一致。" 'Green'
    Say "  $RepoPage"
    exit 0
} catch {
    Say ''
    Say ('✗ ' + $_.Exception.Message) 'Red'
    Say '没有做合并、没有强制推送。' 'Yellow'
    exit 1
}
