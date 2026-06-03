param([string]$PY = "C:\Users\zepau\anaconda3\python.exe")

$ErrorActionPreference = "Stop"
$env:NO_COLOR = "1"
$env:PY_COLORS = "0"
$env:CLICOLOR = "0"

. (Join-Path $PSScriptRoot "ops_common.ps1")

$PY = Initialize-PyMercatorScript -RequestedPython $PY
$logDir = New-PyMercatorLogDir -Prefix "daily_signal"
$reportOutput = Join-Path $logDir "report_CON.txt"
$jsonOutput = Join-Path $logDir "report_CON.json"
$runDir = Join-Path $logDir "run_CON"
$basketOutput = Join-Path $logDir "basket_CON.csv"

Write-Host ""
Write-Host "PYMERCATOR DAILY SIGNAL"
Write-Host "PYTHON : $PY"
Write-Host "RUNTIME: $logDir"
Write-Host ""

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Update IBOV" `
    -PyArgs @("update", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "00_update_ibov.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Diag" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "01_diag.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Run CON basket" `
    -PyArgs @(
        "run",
        "--profile",
        "CON",
        "--basket",
        "--report-output",
        $reportOutput,
        "--json-output",
        $jsonOutput,
        "--run-dir",
        $runDir,
        "--basket-output",
        $basketOutput
    ) `
    -LogFile (Join-Path $logDir "02_run_CON_basket.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Observe IBOV" `
    -PyArgs @("observe", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "03_observe_ibov.log") `
    -Critical $false

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Basket show" `
    -PyArgs @("basket", "show", "--output", $basketOutput) `
    -LogFile (Join-Path $logDir "04_basket_show.log") `
    -Critical $false

Write-Host ""
Write-Host "============================================================"
Write-Host "DAILY SIGNAL FINISHED"
Write-Host "RUNTIME: $logDir"
Write-Host "============================================================"
