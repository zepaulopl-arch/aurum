param([string]$PY = "C:\Users\zepau\anaconda3\python.exe")

$ErrorActionPreference = "Stop"
$env:NO_COLOR = "1"
$env:PY_COLORS = "0"
$env:CLICOLOR = "0"

. (Join-Path $PSScriptRoot "ops_common.ps1")

$PY = Initialize-PyMercatorScript -RequestedPython $PY
$logDir = New-PyMercatorLogDir -Prefix "weekend_full"
$profiles = @("CON", "BAL", "AGR", "RLX")

function New-ProfilePaths {
    param([string]$Profile)

    return @{
        Report = Join-Path $logDir "report_${Profile}.txt"
        Json = Join-Path $logDir "report_${Profile}.json"
        RunDir = Join-Path $logDir "run_${Profile}"
        Basket = Join-Path $logDir "basket_${Profile}.csv"
        Log = Join-Path $logDir "run_${Profile}.log"
    }
}

Write-Host ""
Write-Host "PYMERCATOR WEEKEND FULL"
Write-Host "PYTHON : $PY"
Write-Host "RUNTIME: $logDir"
Write-Host ""

Invoke-NativeStep `
    -Name "Install editable package" `
    -Command @($PY, "-m", "pip", "install", "-e", ".") `
    -LogFile (Join-Path $logDir "00_pip_install_editable.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Diag" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "01_diag.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Update IBOV" `
    -PyArgs @("update", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "02_update_ibov.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Universe diagnose" `
    -PyArgs @(
        "universe",
        "diagnose",
        "--file",
        "data\universes\ibov_live.csv",
        "--policy",
        "config\policy.json"
    ) `
    -LogFile (Join-Path $logDir "03_universe_diagnose.log")

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Train multi-horizon autotune details" `
    -PyArgs @(
        "train",
        "--horizons",
        "5,20,60",
        "--engines",
        "extratrees,randomforest,gradientboosting",
        "--meta",
        "ridge",
        "--observer",
        "weighted",
        "--weights",
        "D5=0.25,D20=0.35,D60=0.40",
        "--autotune",
        "--details",
        "--output",
        "storage\prediction\latest_train_detail_report.txt"
    ) `
    -LogFile (Join-Path $logDir "04_train_autotune_details.log")

foreach ($profile in $profiles) {
    $paths = New-ProfilePaths -Profile $profile
    Invoke-PyMercatorStep `
        -Python $PY `
        -Name "Run $profile basket" `
        -PyArgs @(
            "run",
            "--profile",
            $profile,
            "--basket",
            "--report-output",
            $paths.Report,
            "--json-output",
            $paths.Json,
            "--run-dir",
            $paths.RunDir,
            "--basket-output",
            $paths.Basket
        ) `
        -LogFile $paths.Log
}

Invoke-PyMercatorStep `
    -Python $PY `
    -Name "Scenario positive AGR basket" `
    -PyArgs @(
        "scenario",
        "run",
        "--preset",
        "positive_risk_on",
        "--profile",
        "AGR",
        "--basket",
        "--report-output",
        (Join-Path $logDir "scenario_positive_report.txt"),
        "--json-output",
        (Join-Path $logDir "scenario_positive_report.json"),
        "--run-dir",
        (Join-Path $logDir "scenario_positive_run"),
        "--basket-output",
        (Join-Path $logDir "scenario_positive_basket.csv")
    ) `
    -LogFile (Join-Path $logDir "09_scenario_positive.log")

Invoke-NativeStep `
    -Name "Pytest" `
    -Command @($PY, "-m", "pytest", "tests", "-q") `
    -LogFile (Join-Path $logDir "10_pytest.log")

Write-Host ""
Write-Host "============================================================"
Write-Host "WEEKEND FULL FINISHED"
Write-Host "RUNTIME: $logDir"
Write-Host "============================================================"
