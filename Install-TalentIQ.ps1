param([string]$PythonPath = '', [switch]$IncludeAI)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:NEXT_TELEMETRY_DISABLED = '1'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 22 or later is required. Install the current Node.js LTS release, then rerun this script.' }
if (-not $PythonPath) {
    $candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'), (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'), (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'))
    foreach ($candidatePath in $candidates) { if (Test-Path -LiteralPath $candidatePath) { $PythonPath = $candidatePath; break } }
    if (-not $PythonPath) { $pythonCommand = Get-Command python -ErrorAction SilentlyContinue; if ($pythonCommand) { $PythonPath = $pythonCommand.Source } }
}
if (-not $PythonPath) { throw 'Install Python 3.11–3.13, then run .\Install-TalentIQ.ps1 -PythonPath "C:\path\to\python.exe".' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { & $PythonPath -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment. Verify the Python executable.' } }
& '.\.venv\Scripts\python.exe' -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize pip.' }
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not update pip. Check internet access.' }
& '.\.venv\Scripts\python.exe' -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed. Check internet access and rerun.' }
& npm.cmd ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Check internet access and rerun.' }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed. Review the errors above.' }
if ($IncludeAI) { & (Join-Path $PSScriptRoot 'Setup-LocalAI.ps1') }
Write-Host 'TalentIQ is installed. Run .\Start-TalentIQ.ps1 to open http://127.0.0.1:3000.' -ForegroundColor Green
if (-not $IncludeAI) { Write-Host 'Use -IncludeAI for automatic Ollama/model setup, or run .\Setup-LocalAI.ps1 separately.' }
