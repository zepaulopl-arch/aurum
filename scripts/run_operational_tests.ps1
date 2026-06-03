param([string]$Python = "")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "ops_common.ps1")

$Python = Initialize-PyMercatorScript -RequestedPython $Python
$logDir = New-PyMercatorLogDir -Prefix "operational_tests"

Write-Host ""
Write-Host "PYMERCATOR OPERATIONAL TESTS"
Write-Host "PYTHON : $Python"
Write-Host "LOG DIR: $logDir"
Write-Host ""

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Diag" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "00_diag.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Update IBOV" `
    -PyArgs @("update", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "01_update.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe diagnose" `
    -PyArgs @("universe", "diagnose", "--file", "data\universes\ibov_live.csv", "--policy", "config\policy.json") `
    -LogFile (Join-Path $logDir "02_universe_diagnose.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Train details" `
    -PyArgs @("train", "--details") `
    -LogFile (Join-Path $logDir "03_train_details.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run CON basket" `
    -PyArgs @("run", "--profile", "CON", "--basket") `
    -LogFile (Join-Path $logDir "04_run_CON_basket.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Basket show" `
    -PyArgs @("basket", "show", "--output", "storage\baskets\latest_daily_basket.csv") `
    -LogFile (Join-Path $logDir "05_basket_show.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Positive scenario" `
    -PyArgs @("scenario", "run", "--preset", "positive_risk_on", "--profile", "AGR", "--basket") `
    -LogFile (Join-Path $logDir "06_positive_scenario.txt")

Invoke-NativeStep `
    -Name "Pytest" `
    -Command @($Python, "-m", "pytest", "tests", "-q") `
    -LogFile (Join-Path $logDir "07_pytest.txt")

Write-Host ""
Write-Host "============================================================"
Write-Host "OPERATIONAL TESTS FINISHED"
Write-Host "LOGS: $logDir"
Write-Host "============================================================"
