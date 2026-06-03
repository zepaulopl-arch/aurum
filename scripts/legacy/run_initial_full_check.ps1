param([string]$Python = "")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\ops_common.ps1")

$Python = Initialize-PyMercatorScript -RequestedPython $Python
$logDir = New-PyMercatorLogDir -Prefix "initial_full_check"

Write-Host ""
Write-Host "PYMERCATOR INITIAL FULL CHECK"
Write-Host "PYTHON : $Python"
Write-Host "LOG DIR: $logDir"
Write-Host ""

Invoke-NativeStep `
    -Name "Python version" `
    -Command @($Python, "--version") `
    -LogFile (Join-Path $logDir "00_python_version.txt")

Invoke-NativeStep `
    -Name "Pip version" `
    -Command @($Python, "-m", "pip", "--version") `
    -LogFile (Join-Path $logDir "01_pip_version.txt")

Invoke-NativeStep `
    -Name "Install editable" `
    -Command @($Python, "-m", "pip", "install", "-e", ".") `
    -LogFile (Join-Path $logDir "02_install_editable.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Diag before" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "03_diag_before.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Prices check before" `
    -PyArgs @("prices", "check", "--prices-dir", "data\prices") `
    -LogFile (Join-Path $logDir "04_prices_check_before.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe summary before" `
    -PyArgs @("universe", "summary", "--file", "data\universes\ibov_live.csv") `
    -LogFile (Join-Path $logDir "05_universe_summary_before.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe diagnose before" `
    -PyArgs @("universe", "diagnose", "--file", "data\universes\ibov_live.csv", "--policy", "config\policy.json") `
    -LogFile (Join-Path $logDir "06_universe_diagnose_before.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Update IBOV" `
    -PyArgs @("update", "--list", "IBOV") `
    -LogFile (Join-Path $logDir "07_update.txt") `
    -Critical $false

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Diag after update" `
    -PyArgs @("diag") `
    -LogFile (Join-Path $logDir "08_diag_after_update.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Prices check after update" `
    -PyArgs @("prices", "check", "--prices-dir", "data\prices") `
    -LogFile (Join-Path $logDir "09_prices_check_after_update.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe summary after update" `
    -PyArgs @("universe", "summary", "--file", "data\universes\ibov_live.csv") `
    -LogFile (Join-Path $logDir "10_universe_summary_after_update.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Universe diagnose after update" `
    -PyArgs @("universe", "diagnose", "--file", "data\universes\ibov_live.csv", "--policy", "config\policy.json") `
    -LogFile (Join-Path $logDir "11_universe_diagnose_after_update.txt")

$assetFlowCheck = @'
import pandas as pd
from pathlib import Path

files = [
    "data/universes/ibov_live.csv",
    "storage/features/latest_feature_matrix.csv",
]

for file_name in files:
    path = Path(file_name)
    print("\n===", file_name, "===")
    if not path.exists():
        raise SystemExit(f"FAIL: missing file {file_name}")

    df = pd.read_csv(path)
    print("rows:", len(df))
    print("columns:", list(df.columns))

    for column in ["ticker", "symbol", "asset", "code"]:
        if column in df.columns:
            unique_assets = df[column].nunique()
            print("asset_col:", column)
            print("unique_assets:", unique_assets)
            if unique_assets < 30:
                raise SystemExit(f"FAIL: only {unique_assets} assets in {file_name}")
            break
    else:
        raise SystemExit(f"FAIL: no asset column found in {file_name}")

print("\nASSET FLOW OK")
'@

Invoke-PythonCode `
    -Python $Python `
    -Name "Asset flow check" `
    -Code $assetFlowCheck `
    -LogFile (Join-Path $logDir "12_asset_flow_check.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Train multi-horizon" `
    -PyArgs @("train") `
    -LogFile (Join-Path $logDir "13_train.txt")

$evaluationValidation = @'
import json
from pathlib import Path

path = Path("storage/prediction/latest_evaluation.json")
if not path.exists():
    raise SystemExit("FAIL: latest_evaluation.json not found")

data = json.loads(path.read_text(encoding="utf-8"))

engine = data.get("engine_used") or data.get("engine")
status = data.get("status")
horizons = data.get("horizons")
base_engines = set(data.get("base_engines", []))
is_baseline = data.get("is_baseline", data.get("baseline"))
assets = data.get("assets") or data.get("asset_count")

print("engine:", engine)
print("status:", status)
print("horizons:", horizons)
print("base_engines:", sorted(base_engines))
print("baseline:", is_baseline)
print("assets:", assets)
print("model_quality:", data.get("model_quality"))
print("edge:", data.get("edge"))

errors = []

if engine != "multi_horizon_ridge":
    errors.append(f"invalid engine: {engine}")

if status != "OK":
    errors.append(f"invalid status: {status}")

if horizons != [5, 20, 60]:
    errors.append(f"invalid horizons: {horizons}")

required = {"extratrees", "randomforest", "gradientboosting"}
if not required.issubset(base_engines):
    errors.append(f"incomplete base_engines: {base_engines}")

if is_baseline not in [False, "false", "False", 0]:
    errors.append(f"invalid baseline: {is_baseline}")

if assets is not None and int(assets) < 30:
    errors.append(f"not enough assets: {assets}")

if errors:
    print("\nFAILURES:")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("\nEVALUATION OK")
'@

Invoke-PythonCode `
    -Python $Python `
    -Name "Validate evaluation" `
    -Code $evaluationValidation `
    -LogFile (Join-Path $logDir "14_validate_evaluation.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run CON basket" `
    -PyArgs @("run", "--profile", "CON", "--basket") `
    -LogFile (Join-Path $logDir "15_run_CON.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run BAL basket" `
    -PyArgs @("run", "--profile", "BAL", "--basket") `
    -LogFile (Join-Path $logDir "16_run_BAL.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run AGR basket" `
    -PyArgs @("run", "--profile", "AGR", "--basket") `
    -LogFile (Join-Path $logDir "17_run_AGR.txt")

Invoke-PyMercatorStep `
    -Python $Python `
    -Name "Run RLX basket" `
    -PyArgs @("run", "--profile", "RLX", "--basket") `
    -LogFile (Join-Path $logDir "18_run_RLX.txt")

$basketValidation = @'
import csv
from pathlib import Path

path = Path("storage/baskets/latest_daily_basket.csv")

if not path.exists():
    print("Basket file not found. OK if basket was blocked.")
    raise SystemExit(0)

rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
print("basket_rows:", len(rows))

bad = []
for row in rows:
    text = " ".join(str(value) for value in row.values()).upper()
    if "BLOCKED" in text:
        bad.append(row)

if bad:
    print("FAIL: basket contains BLOCKED assets")
    for row in bad[:10]:
        print(row)
    raise SystemExit(1)

print("BASKET OK")
'@

Invoke-PythonCode `
    -Python $Python `
    -Name "Validate basket" `
    -Code $basketValidation `
    -LogFile (Join-Path $logDir "19_validate_basket.txt")

Invoke-NativeStep `
    -Name "Pytest full suite" `
    -Command @($Python, "-m", "pytest", "tests", "-q") `
    -LogFile (Join-Path $logDir "20_pytest_all.txt")

Write-Host ""
Write-Host "============================================================"
Write-Host "INITIAL FULL CHECK FINISHED"
Write-Host "LOGS: $logDir"
Write-Host "============================================================"

