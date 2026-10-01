$ErrorActionPreference = 'Stop'
try {
    $roastBootstrap = Invoke-RestMethod 'http://127.0.0.1:8740/api/bootstrap' -TimeoutSec 3
    Invoke-RestMethod 'http://127.0.0.1:8740/api/shutdown' -Method Post -ContentType 'application/json' -Headers @{ 'X-Roast-Token' = $roastBootstrap.token } -Body '{}' | Out-Null
    Write-Host 'Roast Studio stopped. All saved records remain in SQLite.'
} catch {
    Write-Error 'Could not stop Roast Studio. Finish and save any active batch, then try again. If it is already stopped, no action is needed.'
}
