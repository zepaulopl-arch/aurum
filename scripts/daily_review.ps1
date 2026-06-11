param(
    [string]$PY = "",
    [string]$Profile = "CON",
    [string]$List = "IBOV",
    [string]$SignalDate = "",
    [string]$ReviewDate = "",
    [string]$SignalsDir = "storage/signals",
    [string]$PricesDir = "data/prices",
    [switch]$Json,
    [switch]$Color
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ops_common.ps1")

$scriptName = Split-Path -Leaf $PSCommandPath
$PY = Initialize-AurumScript -RequestedPython $PY -ScriptName $scriptName
Set-AurumColorMode -Enabled $Color.IsPresent

$argsPayload = @{
    profile = $Profile
    list_name = $List
    signal_date = $SignalDate
    review_date = $ReviewDate
    signals_dir = $SignalsDir
    prices_dir = $PricesDir
    emit_json = $Json.IsPresent
} | ConvertTo-Json -Compress

$env:AURUM_CORE_ARGS = $argsPayload
$code = @'
import json
import os

from aurum.core import run_review

args = json.loads(os.environ["AURUM_CORE_ARGS"])
emit_json = bool(args.pop("emit_json", False))
for key in ("signal_date", "review_date"):
    if not args.get(key):
        args[key] = None

payload = run_review(**args)
if emit_json:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
else:
    print(payload["text"], end="")
'@

try {
    & $PY -c $code
    $exitCode = $LASTEXITCODE
} finally {
    Remove-Item Env:\AURUM_CORE_ARGS -ErrorAction SilentlyContinue
}

if ($exitCode -ne 0) {
    Write-RunManifest -Status "FAIL" -Outputs @{ signals_dir = $SignalsDir; list = $List; profile = $Profile }
    exit $exitCode
}

Write-RunManifest -Status "OK" -Outputs @{ signals_dir = $SignalsDir; list = $List; profile = $Profile }
exit 0
