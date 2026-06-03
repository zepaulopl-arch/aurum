param([string]$Python = "")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "ops_common.ps1")

$Python = Initialize-PyMercatorScript -RequestedPython $Python
$logDir = New-PyMercatorLogDir -Prefix "daily_profiles"

Write-Host ""
Write-Host "PYMERCATOR DAILY PROFILE COMPARISON"
Write-Host "PYTHON : $Python"
Write-Host "LOG DIR: $logDir"
Write-Host ""

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Update IBOV" `
    -PyArgs @("update", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "00_update.txt") `
    -Critical $false

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run CON basket" `
    -PyArgs @("run", "--profile", "CON", "--basket") `
    -LogFile (Join-Path $logDir "01_run_CON.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run BAL basket" `
    -PyArgs @("run", "--profile", "BAL", "--basket") `
    -LogFile (Join-Path $logDir "02_run_BAL.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run AGR basket" `
    -PyArgs @("run", "--profile", "AGR", "--basket") `
    -LogFile (Join-Path $logDir "03_run_AGR.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run RLX basket" `
    -PyArgs @("run", "--profile", "RLX", "--basket") `
    -LogFile (Join-Path $logDir "04_run_RLX.txt")

Write-Host ""
Write-Host "============================================================"
Write-Host "DAILY PROFILE COMPARISON FINISHED"
Write-Host "LOGS: $logDir"
Write-Host "============================================================"
