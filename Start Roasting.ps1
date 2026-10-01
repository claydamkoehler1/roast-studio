$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$roastPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $roastPython)) {
    $roastPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
if (-not (Test-Path -LiteralPath $roastPython)) {
    $roastPython = (Get-Command python -ErrorAction Stop).Source
}
try {
    $roastHealth = Invoke-RestMethod 'http://127.0.0.1:8740/api/bootstrap' -TimeoutSec 2
} catch { $roastHealth = $null }
if (-not $roastHealth) {
    $roastArgs = '"' + (Join-Path $PSScriptRoot 'run.py') + '"'
    Start-Process -FilePath $roastPython -ArgumentList $roastArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log')
    for ($roastAttempt=0; $roastAttempt -lt 30; $roastAttempt++) {
        Start-Sleep -Milliseconds 300
        try { $roastHealth = Invoke-RestMethod 'http://127.0.0.1:8740/api/bootstrap' -TimeoutSec 1; break } catch {}
    }
}
if (-not $roastHealth) { throw 'The server did not start. Check server-error.log.' }
Start-Process 'http://127.0.0.1:8740'
