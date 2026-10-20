$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    npm --prefix client install
    npm --prefix client run build
    ./tools/start-portal.ps1 -SkipBootstrap
} finally { Pop-Location }
