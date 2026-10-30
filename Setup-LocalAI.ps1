$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:OLLAMA_NO_CLOUD='1'
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL='1'
$env:OLLAMA_MAX_LOADED_MODELS='1'
$env:OLLAMA_MAX_QUEUE='16'
$env:OLLAMA_CONTEXT_LENGTH='12288'
[Environment]::SetEnvironmentVariable('OLLAMA_NO_CLOUD','1','User')
$runtimeCommand=Get-Command ollama -ErrorAction SilentlyContinue
$runtimePath=if ($runtimeCommand) { $runtimeCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
if (-not (Test-Path -LiteralPath $runtimePath)) {
    $version='0.40.12'
    $expectedHash='9a6a44ddb9044da0a8985235ad1114baba31f42d202b53a179c452acdaec9fd7'
    $installerDirectory=Join-Path $PSScriptRoot 'data\installers'
    New-Item -ItemType Directory -Force -Path $installerDirectory | Out-Null
    $installer=Join-Path $installerDirectory 'OllamaSetup-0.40.12.exe'
    if (-not (Test-Path -LiteralPath $installer)) {
        Write-Host 'Downloading the official Ollama Windows installer (about 1.6 GB)...'
        & curl.exe --fail --location --retry 3 --connect-timeout 20 --output $installer "https://github.com/ollama/ollama/releases/download/v$version/OllamaSetup.exe"
        if ($LASTEXITCODE -ne 0) { throw 'Ollama installer download failed. Rerun setup to retry.' }
    }
    if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Ollama installer hash did not match the pinned official package. Installation was not attempted.' }
    Write-Host 'Installing Ollama locally...'
    $installation=Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-') -WindowStyle Hidden -PassThru
    $installation.WaitForExit()
    if ($installation.ExitCode -ne 0) { throw 'Ollama installation failed.' }
}
$online=$false
try { $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $online=$true } catch {}
if (-not $online) {
    $logDirectory=Join-Path $PSScriptRoot 'data\logs'
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $null=Start-Process -FilePath $runtimePath -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'ollama.log') -RedirectStandardError (Join-Path $logDirectory 'ollama-error.log')
    for ($attempt=0; $attempt -lt 45; $attempt++) {
        try { $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $online=$true; break } catch { Start-Sleep -Milliseconds 500 }
    }
}
if (-not $online) { throw 'Ollama did not start. Check data\logs\ollama-error.log.' }
Write-Host 'Checking and downloading full-CV understanding, Fast, detailed review, and embedding models (about 7.0 GB total when missing)...'
& '.\.venv\Scripts\python.exe' -m scripts.install-models --confirm-download
if ($LASTEXITCODE -ne 0) { throw 'One or more model downloads failed. Rerun Setup-LocalAI.ps1 to resume.' }
Write-Host 'Local AI is configured. Full-CV understanding, Fast, detailed review, and embedding models are installed.' -ForegroundColor Green
