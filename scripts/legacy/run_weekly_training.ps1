param([string]$Python = "")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\ops_common.ps1")

$Python = Initialize-PyMercatorScript -RequestedPython $Python
$logDir = New-PyMercatorLogDir -Prefix "weekly_training"

Write-Host ""
Write-Host "PYMERCATOR WEEKLY TRAINING"
Write-Host "PYTHON : $Python"
Write-Host "LOG DIR: $logDir"
Write-Host ""

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Diag before" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "00_diag_before.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Update IBOV" `
    -PyArgs @("update", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "01_update.txt") `
    -Critical $false

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Prices check" `
    -PyArgs @("prices", "check", "--prices-dir", "data\prices") `
    -LogFile (Join-Path $logDir "02_prices_check.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe summary" `
    -PyArgs @("universe", "summary", "--file", "data\universes\ibov_live.csv") `
    -LogFile (Join-Path $logDir "03_universe_summary.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe diagnose" `
    -PyArgs @("universe", "diagnose", "--file", "data\universes\ibov_live.csv", "--policy", "config\policy.json") `
    -LogFile (Join-Path $logDir "04_universe_diagnose.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Train multi-horizon no autotune" `
    -PyArgs @("train") `
    -LogFile (Join-Path $logDir "05_train.txt")

$trainingValidation = @'
import json
from pathlib import Path

p = Path("storage/prediction/latest_evaluation.json")
if not p.exists():
    raise SystemExit("FAIL: latest_evaluation.json not found")

data = json.loads(p.read_text(encoding="utf-8"))

print("engine:", data.get("engine_used") or data.get("engine"))
print("status:", data.get("status"))
print("horizons:", data.get("horizons"))
print("base_engines:", data.get("base_engines"))
print("model_quality:", data.get("model_quality"))
print("ensemble_accuracy:", data.get("ensemble_accuracy"))
print("edge:", data.get("edge"))

errors = []

if (data.get("engine_used") or data.get("engine")) != "multi_horizon_ridge":
    errors.append("engine is not multi_horizon_ridge")

if data.get("horizons") != [5, 20, 60]:
    errors.append("horizons are not [5, 20, 60]")

if data.get("status") != "OK":
    errors.append("evaluation status is not OK")

if errors:
    print("\nFAILURES:")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("\nWEEKLY TRAINING VALIDATION OK")
'@

Invoke-PythonCode `
    -Python $Python `
    -Name "Validate training" `
    -Code $trainingValidation `
    -LogFile (Join-Path $logDir "06_validate_training.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run CON basket" `
    -PyArgs @("run", "--profile", "CON", "--basket") `
    -LogFile (Join-Path $logDir "07_run_CON.txt")

Write-Host ""
Write-Host "============================================================"
Write-Host "WEEKLY TRAINING FINISHED"
Write-Host "LOGS: $logDir"
Write-Host "============================================================"

