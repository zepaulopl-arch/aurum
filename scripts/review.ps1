param(
    [string]$Profile = "CON",
    [string]$List = "IBOV",
    [switch]$NoUpdate
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$OpsCommon = Join-Path $PSScriptRoot "ops_common.ps1"
if (Test-Path $OpsCommon) {
    . $OpsCommon
}

$RuntimeConfig = $null
if (Get-Command Get-AurumRuntimeConfig -ErrorAction SilentlyContinue) {
    $RuntimeConfig = Get-AurumRuntimeConfig
} elseif (Get-Command Get-RuntimeConfig -ErrorAction SilentlyContinue) {
    $RuntimeConfig = Get-RuntimeConfig
}

$LogDir = Join-Path $ProjectRoot "storage\logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $LogDir "review_d1xd_$Stamp.log"

if (-not $NoUpdate) {
    Write-Host ""
    Write-Host "UPDATE"
    Write-Host "--------------------------------------------------------------------------------"

    python -m pymercator update --list $List
    $UpdateExitCode = $LASTEXITCODE

    if ($UpdateExitCode -ne 0) {
        Write-Host ""
        Write-Host "UPDATE FALHOU"
        Write-Host "--------------------------------------------------------------------------------"
        Write-Host ("ExitCode: {0}" -f $UpdateExitCode)
        exit $UpdateExitCode
    }
}

$cmd = @(
    "-m", "pymercator",
    "review", "run",
    "--profile", $Profile,
    "--list", $List
)

$raw = & python @cmd 2>&1
$ExitCode = $LASTEXITCODE

$raw | Set-Content -Path $Log -Encoding UTF8

Write-Host ""
Write-Host "AURUM REVIEW - D-1 x D"
Write-Host "--------------------------------------------------------------------------------"
Write-Host ("Profile : {0}" -f $Profile)
Write-Host ("List    : {0}" -f $List)
Write-Host ("Periodo : D-1 x D")
Write-Host ""

foreach ($line in $raw) {
    $s = [string]$line

    # Corrige negativo zero.
    $s = $s -replace "-0\.00%", "0.00%"
    $s = $s -replace "-0\.00", "0.00"

    # Nas linhas de ranking, melhora leitura visual.
    if ($s -match "^\s*\d+\s+") {
        $s = $s -replace "\s+0\.00%\s+", "   flat   "
        $s = $s -replace "\s+0\.00\s+", "     0    "
    }

    Write-Host $s
}

Write-Host ""
Write-Host "REVIEW LOG"
Write-Host "--------------------------------------------------------------------------------"
Write-Host $Log

exit $ExitCode
