# bling 精读工作台 · Windows 一键启动
# 由 start.bat 调用：找 Python（没有就帮你装）→ 建 .venv 装依赖（第一次几分钟）→ 启动网页端并打开浏览器
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Fail($msg) {
    Say ''
    Say "✗ $msg" 'Red'
    Say ''
    Read-Host '按回车关闭窗口' | Out-Null
    exit 1
}

# 能用的 Python：版本 >= 3.9。Microsoft Store 的 python.exe 占位程序会被这里排除（它跑不出 True）。
function Test-Python($exe, [string[]]$pre = @()) {
    try {
        $out = & $exe @pre -c "import sys; print(sys.version_info >= (3, 9))" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq 'True')
    } catch { return $false }
}

function Find-Python {
    $cands = @(
        @{ exe = 'py'; pre = @('-3') },
        @{ exe = 'python'; pre = @() },
        @{ exe = 'python3'; pre = @() }
    )
    $paths = @()
    $paths += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
    $paths += Get-ChildItem "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
    foreach ($d in @("$env:USERPROFILE\miniconda3", "$env:USERPROFILE\anaconda3", "$env:LOCALAPPDATA\miniconda3", "$env:ProgramData\miniconda3", "$env:ProgramData\anaconda3")) {
        if (Test-Path "$d\python.exe") { $paths += Get-Item "$d\python.exe" }
    }
    foreach ($p in $paths) { $cands += @{ exe = $p.FullName; pre = @() } }
    foreach ($c in $cands) {
        if (Test-Python $c.exe $c.pre) { return $c }
    }
    return $null
}

Say ''
Say '==== bling 精读工作台 ====' 'Cyan'
$venvPy = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPy)) {
    $py = Find-Python
    if (-not $py) {
        Say '没找到 Python 3.9 以上的版本。' 'Yellow'
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            $ans = Read-Host '现在用 winget 自动安装 Python 3.12 吗？只装到当前用户，不需要管理员 [Y/n]'
            if ($ans -eq '' -or $ans -match '^[Yy]') {
                Say '正在安装 Python 3.12（几分钟，安装窗口里有提示就点同意）…'
                winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
                $py = Find-Python
            }
        }
        if (-not $py) {
            Say ''
            Say '请手动安装 Python：' 'Yellow'
            Say '  1. 打开 https://www.python.org/downloads/windows/ ，下载 Python 3.12 的 Windows installer (64-bit)'
            Say '  2. 安装第一页一定勾上「Add python.exe to PATH」，然后点 Install Now'
            Say '  3. 装完重新双击 start.bat'
            Start-Process 'https://www.python.org/downloads/windows/'
            Fail '没有 Python，没法继续。'
        }
    }
    Say "用这个 Python 建虚拟环境：$($py.exe) $($py.pre -join ' ')"
    $pre = [string[]]$py.pre
    & $py.exe @pre -m venv (Join-Path $Root '.venv')
    if (-not (Test-Path $venvPy)) { Fail '建虚拟环境 .venv 失败（看上面的报错）。' }
}

# 依赖：缺了才装；官方源装不上就换清华镜像
$req = Join-Path $Root 'web\requirements.txt'
& $venvPy -c "import flask, markdown, fitz" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say '第一次运行，安装依赖（flask / markdown / pymupdf / anthropic / openai），大概 1–3 分钟…'
    & $venvPy -m pip install --disable-pip-version-check -r $req
    if ($LASTEXITCODE -ne 0) {
        Say '官方源没装成功，换清华镜像再试…' 'Yellow'
        & $venvPy -m pip install --disable-pip-version-check -r $req -i https://pypi.tuna.tsinghua.edu.cn/simple
    }
    & $venvPy -c "import flask, markdown, fitz" 2>$null
    if ($LASTEXITCODE -ne 0) { Fail '依赖没装好（看上面 pip 的报错，多半是网络问题）。' }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Say '提示：没检测到 git，导入论文时克隆官方代码这一步会跳过（其他功能不受影响）。装 git：https://git-scm.com/download/win' 'Yellow'
}

Say ''
Say '启动中…浏览器会自动打开。用完关掉这个窗口就停止了。' 'Green'
& $venvPy (Join-Path $Root 'web\server.py') --open
Read-Host '网页端已停止，按回车关闭窗口' | Out-Null
