param([switch]$Development, [switch]$SmokeTest, [switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_MAX_QUEUE = '16'
$env:OLLAMA_CONTEXT_LENGTH = '12288'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js is missing. Install Node.js LTS first.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'node_modules\next\package.json')) { throw 'Dependencies are missing. Run .\Install-TalentIQ.ps1 first.' }
if (-not $Development -and -not (Test-Path -LiteralPath '.next\BUILD_ID')) { throw 'Production build is missing. Run npm run build, or start with -Development.' }
if (-not $SmokeTest) {
    try {
        $existingWorkspace=Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $existingPage=Invoke-WebRequest 'http://127.0.0.1:3000' -UseBasicParsing -TimeoutSec 2
        if ($existingWorkspace.ok -and $existingWorkspace.local_only -and $existingPage.Content.Contains('TalentIQ')) {
            Write-Host 'TalentIQ is already running at http://127.0.0.1:3000' -ForegroundColor Green
            if ($OpenBrowser) { Start-Process 'http://127.0.0.1:3000' }
            return
        }
    } catch {}
}
foreach ($portNumber in @(8000,3000)) {
    $listener = Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $portNumber is already in use. Stop the existing TalentIQ instance or free the port before starting." }
}
if (Test-Path -LiteralPath '.env') {
    foreach ($line in Get-Content -LiteralPath '.env') {
        if ($line -match '^\s*(TALENTIQ_DATA_DIR|TALENTIQ_OLLAMA_URL|TALENTIQ_AI_PROVIDER|DASHSCOPE_API_KEY|QWENCLOUD_API_KEY)\s*=\s*(.*?)\s*$') { [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2].Trim('"').Trim("'"),'Process') }
    }
}
$logDirectory = Join-Path $PSScriptRoot 'data\logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
# Provider selection happens before any local-runtime inspection or startup.
$providerChoice=& '.\.venv\Scripts\python.exe' -c "from backend.ai import settings; print(settings()['provider'])"
if ($LASTEXITCODE -ne 0) { throw 'AI provider configuration could not be read.' }
if ($providerChoice.Trim() -eq 'local') {
# Start an installed local runtime when it is not already serving. Never download models at startup.
$ollamaReady = $false
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $ollamaReady=$true } catch {}
if (-not $ollamaReady) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    $ollamaExecutable = if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
    if (Test-Path -LiteralPath $ollamaExecutable) {
        Write-Host 'Starting local Ollama runtime...'
        $null = Start-Process -FilePath $ollamaExecutable -ArgumentList @('serve') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'ollama.log') -RedirectStandardError (Join-Path $logDirectory 'ollama-error.log')
        for ($attempt=0; $attempt -lt 30; $attempt++) {
            try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $ollamaReady=$true; break } catch { Start-Sleep -Milliseconds 500 }
        }
    }
}
if (-not $ollamaReady) { Write-Warning 'Ollama is not reachable. Install Ollama to enable local AI; other workspace features remain available.' }
}
$backendProcess = $null
$frontendProcess = $null
try {
    $backendProcess = Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--no-access-log') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'backend.log') -RedirectStandardError (Join-Path $logDirectory 'backend-error.log')
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        if ($backendProcess.HasExited) { throw 'Backend stopped during startup. Check data\logs\backend-error.log.' }
        try { $status = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($status.ok) { $ready=$true; break } } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Backend readiness check failed. Check data\logs.' }
    $mode = if ($Development) { 'dev' } else { 'start' }
    $frontendProcess = Start-Process -FilePath (Get-Command node).Source -ArgumentList @('node_modules/next/dist/bin/next',$mode,'--hostname','127.0.0.1','--port','3000') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'frontend.log') -RedirectStandardError (Join-Path $logDirectory 'frontend-error.log')
    $frontendReady = $false
    for ($attempt=0; $attempt -lt 45; $attempt++) {
        if ($frontendProcess.HasExited) { throw 'Frontend stopped during startup. Check data\logs\frontend-error.log.' }
        try { $pageResponse = Invoke-WebRequest 'http://127.0.0.1:3000' -UseBasicParsing -TimeoutSec 2; if ($pageResponse.StatusCode -eq 200) { $frontendReady=$true; break } } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $frontendReady) { throw 'Frontend readiness check failed. Check data\logs.' }
    Write-Host ''
    Write-Host 'TalentIQ is running at http://127.0.0.1:3000' -ForegroundColor Green
    Write-Host 'Open the URL in your browser. Keep this window open. Press Ctrl+C to stop this TalentIQ instance.'
    if ($providerChoice.Trim() -eq 'qwencloud') { Write-Host 'QwenCloud selected. No local AI runtime or model is started.' } elseif ($providerChoice.Trim() -eq 'local') { Write-Host 'Local AI selected. AI Workspace shows model readiness and analysis controls.' } else { Write-Host 'Choose Local AI or QwenCloud in AI Workspace before using AI.' }
    if ($SmokeTest) { Write-Host 'Launcher smoke test passed; stopping only the processes started by this check.'; return }
    if ($OpenBrowser) { Start-Process 'http://127.0.0.1:3000' }
    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) { Start-Sleep -Seconds 1 }
    throw 'A TalentIQ process exited. Review data\logs for details.'
} finally {
    foreach ($ownedProcess in @($frontendProcess,$backendProcess)) { if ($ownedProcess -and -not $ownedProcess.HasExited) { Stop-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue } }
}
