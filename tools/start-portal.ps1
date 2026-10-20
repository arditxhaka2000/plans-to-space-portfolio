param([string]$AdminEmail = 'admin@example.com', [switch]$SkipBootstrap)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$serverPath = Join-Path $projectRoot 'server'
$priorEnvironment = $env:ASPNETCORE_ENVIRONMENT
$priorEmail = $env:Saas__AdminEmail
$priorPassword = $env:Saas__AdminPassword
$priorCloud = $env:PTS_DATABASE_URL
try {
    $cloudSecretPath = Join-Path $serverPath 'App_Data/saas/supabase-connection.xml'
    if (Test-Path -LiteralPath $cloudSecretPath) {
        $cloudSecret = Import-Clixml -LiteralPath $cloudSecretPath
        $env:PTS_DATABASE_URL = ([System.Net.NetworkCredential]::new('', $cloudSecret)).Password
    }
    $env:ASPNETCORE_ENVIRONMENT = 'Development'
    if ($AdminEmail -and -not $SkipBootstrap) {
        $secret = Read-Host 'Initial administrator password (at least 12 characters)' -AsSecureString
        $credential = [System.Net.NetworkCredential]::new('', $secret)
        $env:Saas__AdminEmail = $AdminEmail
        $env:Saas__AdminPassword = $credential.Password
        if ($env:Saas__AdminPassword.Length -lt 12) { throw 'Password must contain at least 12 characters.' }
    }
    # Local development only. Do not expose this HTTP process to clients.
    Push-Location $serverPath
    try { dotnet run --no-launch-profile --urls http://127.0.0.1:5088 }
    finally { Pop-Location }
} finally {
    $env:ASPNETCORE_ENVIRONMENT = $priorEnvironment
    $env:Saas__AdminEmail = $priorEmail
    $env:Saas__AdminPassword = $priorPassword
    $env:PTS_DATABASE_URL = $priorCloud
    $credential = $null
    $secret = $null
}
