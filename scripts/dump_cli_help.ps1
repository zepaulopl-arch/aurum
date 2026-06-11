param(
    [string]$PY = ""
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ops_common.ps1")

$scriptName = Split-Path -Leaf $PSCommandPath
$PY = Initialize-AurumScript -RequestedPython $PY -ScriptName $scriptName
Set-AurumColorMode -Enabled $false

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputDir = Join-Path "runtime" "cli_help_$timestamp"
$outputFile = Join-Path $outputDir "help_index.txt"
$null = New-Item -ItemType Directory -Force -Path $outputDir

$commands = @(
    @{ Label = "aurum --help"; Args = @("--help") },
    @{ Label = "aurum update --help"; Args = @("update", "--help") },
    @{ Label = "aurum diag --help"; Args = @("diag", "--help") },
    @{ Label = "aurum train --help"; Args = @("train", "--help") },
    @{ Label = "aurum train benchmark-engines --help"; Args = @("train", "benchmark-engines", "--help") },
    @{ Label = "aurum run --help"; Args = @("run", "--help") },
    @{ Label = "aurum db --help"; Args = @("db", "--help") },
    @{ Label = "aurum db status --help"; Args = @("db", "status", "--help") },
    @{ Label = "aurum db last-run --help"; Args = @("db", "last-run", "--help") },
    @{ Label = "aurum db signal --help"; Args = @("db", "signal", "--help") },
    @{ Label = "aurum db rank-last --help"; Args = @("db", "rank-last", "--help") },
    @{ Label = "aurum db sim-last --help"; Args = @("db", "sim-last", "--help") },
    @{ Label = "aurum observe --help"; Args = @("observe", "--help") },
    @{ Label = "aurum basket --help"; Args = @("basket", "--help") },
    @{ Label = "aurum mtm --help"; Args = @("mtm", "--help") },
    @{ Label = "aurum review --help"; Args = @("review", "--help") },
    @{ Label = "aurum universe --help"; Args = @("universe", "--help") },
    @{ Label = "aurum scenario --help"; Args = @("scenario", "--help") },
    @{ Label = "aurum context --help"; Args = @("context", "--help") },
    @{ Label = "aurum borrow --help"; Args = @("borrow", "--help") },
    @{ Label = "aurum pos --help"; Args = @("pos", "--help") },
    @{ Label = "aurum prices --help"; Args = @("prices", "--help") },
    @{ Label = "aurum lab --help"; Args = @("lab", "--help") },
    @{ Label = "aurum cfg --help"; Args = @("cfg", "--help") },
    @{ Label = "aurum open --help"; Args = @("open", "--help") },
    @{ Label = "aurum daily --help"; Args = @("daily", "--help") },
    @{ Label = "aurum weekly --help"; Args = @("weekly", "--help") },
    @{ Label = "aurum execution --help"; Args = @("execution", "--help") },
    @{ Label = "aurum indices --help"; Args = @("indices", "--help") },
    @{ Label = "aurum sentiment --help"; Args = @("sentiment", "--help") },
    @{ Label = "aurum predict --help"; Args = @("predict", "--help") },
    @{ Label = "aurum features --help"; Args = @("features", "--help") }
)

$lines = [System.Collections.Generic.List[string]]::new()
[void]$lines.Add("AURUM CLI HELP")
[void]$lines.Add("Generated at: $((Get-Date).ToUniversalTime().ToString("o"))")
[void]$lines.Add("Python: $PY")
[void]$lines.Add("")

$entrypoint = "import sys; from aurum.cli import main; raise SystemExit(main(sys.argv[1:]))"

foreach ($item in $commands) {
    [void]$lines.Add("================================================================================")
    [void]$lines.Add($item.Label)
    [void]$lines.Add("--------------------------------------------------------------------------------")

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $PY -c $entrypoint @($item.Args) 2>&1
        $exitCode = $LASTEXITCODE
    } catch {
        $output = @("$_")
        $exitCode = 1
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        [void]$lines.Add("STATUS: NOT_AVAILABLE")
        [void]$lines.Add("EXIT_CODE: $exitCode")
    } else {
        [void]$lines.Add("STATUS: OK")
    }

    foreach ($line in @($output)) {
        [void]$lines.Add("$line")
    }
    [void]$lines.Add("")
}

Set-Content -LiteralPath $outputFile -Value $lines -Encoding UTF8
Remove-AnsiFromFile -Path $outputFile
Write-Host "CLI help written: $outputFile"
