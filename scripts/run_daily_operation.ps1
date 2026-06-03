param([string]$Python = "")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "ops_common.ps1")

$Python = Initialize-PyMercatorScript -RequestedPython $Python
$logDir = New-PyMercatorLogDir -Prefix "daily_operation"

Write-Host ""
Write-Host "PYMERCATOR DAILY OPERATION"
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
    -Name "Diag" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "01_diag.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run CON basket" `
    -PyArgs @("run", "--profile", "CON", "--basket") `
    -LogFile (Join-Path $logDir "02_run_CON_basket.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Basket show" `
    -PyArgs @("basket", "show", "--output", "storage\baskets\latest_daily_basket.csv") `
    -LogFile (Join-Path $logDir "03_basket_show.txt") `
    -Critical $false

Write-Host ""
Write-Host "============================================================"
Write-Host "DAILY OPERATION FINISHED"
Write-Host "LOGS: $logDir"
Write-Host "============================================================"
