$ErrorActionPreference = "Stop"

$script:PY = ""
$script:PROJECT_ROOT = ""
$script:PYTHON_VERSION = ""
$script:AURUM_DEFAULT_LIST = "IBOV"
$script:AURUM_COLOR = "never"
$script:GIT_INFO = $null
$script:AURUM_RUNTIME_DIR = ""
$script:AURUM_MANIFEST_PATH = ""
$script:AURUM_MANIFEST = $null
$script:AURUM_SCRIPT_NAME = ""
$script:AURUM_VT_ATTEMPTED = $false

function Enable-AurumVirtualTerminal {
    if ($script:AURUM_VT_ATTEMPTED) {
        return
    }
    $script:AURUM_VT_ATTEMPTED = $true

    $source = @"
using System;
using System.Runtime.InteropServices;

public static class AurumConsoleMode {
    [DllImport("kernel32.dll")]
    private static extern IntPtr GetStdHandle(int nStdHandle);

    [DllImport("kernel32.dll")]
    private static extern bool GetConsoleMode(IntPtr hConsoleHandle, out int lpMode);

    [DllImport("kernel32.dll")]
    private static extern bool SetConsoleMode(IntPtr hConsoleHandle, int dwMode);

    public static void EnableVirtualTerminal() {
        IntPtr handle = GetStdHandle(-11);
        int mode;
        if (GetConsoleMode(handle, out mode)) {
            SetConsoleMode(handle, mode | 0x0004);
        }
    }
}
"@
    try {
        Add-Type -TypeDefinition $source -ErrorAction SilentlyContinue | Out-Null
        [AurumConsoleMode]::EnableVirtualTerminal()
    } catch {
        return
    }
}

function Set-AurumColorMode {
    param([bool]$Enabled = $false)

    if ($Enabled) {
        $script:AURUM_COLOR = "always"
        Remove-Item Env:\NO_COLOR -ErrorAction SilentlyContinue
        Remove-Item Env:\PY_COLORS -ErrorAction SilentlyContinue
        $env:FORCE_COLOR = "1"
        $env:CLICOLOR = "1"
        $env:TERM = "xterm-256color"
        Enable-AurumVirtualTerminal
    } else {
        $script:AURUM_COLOR = "never"
        $env:NO_COLOR = "1"
        $env:PY_COLORS = "0"
        Remove-Item Env:\FORCE_COLOR -ErrorAction SilentlyContinue
        $env:CLICOLOR = "0"
    }
}

function Get-AurumColorArgs {
    if ($script:AURUM_COLOR -and $script:AURUM_COLOR -ne "never") {
        return @("--color", $script:AURUM_COLOR)
    }
    return @("--no-color")
}

function Remove-AnsiFromFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $ansiPattern = "`e\[[0-?]*[ -/]*[@-~]"
    $content = Get-Content -LiteralPath $Path -Raw
    $clean = $content -replace $ansiPattern, ""
    if ($clean -ne $content) {
        Set-Content -LiteralPath $Path -Value $clean -Encoding UTF8
    }
}

function Get-AurumJsonValue {
    param(
        [object]$Object,
        [string]$Name,
        [object]$Default = 0
    )

    if ($null -eq $Object) {
        return $Default
    }
    if ($Object.PSObject.Properties.Name -contains $Name) {
        return $Object.$Name
    }
    return $Default
}

function Get-AurumProfilePaths {
    param(
        [string]$LogDir,
        [string]$Profile
    )

    return @{
        Report = Join-Path $LogDir "report_${Profile}.txt"
        Json = Join-Path $LogDir "report_${Profile}.json"
        RunDir = Join-Path $LogDir "run_${Profile}"
        Basket = Join-Path $LogDir "basket_${Profile}.csv"
        Log = Join-Path $LogDir "run_${Profile}.log"
    }
}

function Show-AurumProfileSummary {
    param(
        [string]$LogDir,
        [string[]]$Profiles,
        [switch]$SkipVerdict
    )

    $rows = @()
    $blockers = @{}
    $script:AURUM_LAST_PROFILE_SUMMARY = $null
    foreach ($profile in $Profiles) {
        $paths = Get-AurumProfilePaths -LogDir $LogDir -Profile $profile
        $payload = $null
        if (Test-Path -LiteralPath $paths.Json) {
            try {
                $payload = Get-Content -LiteralPath $paths.Json -Raw | ConvertFrom-Json
            } catch {
                Write-Host "WARNING: unable to parse profile JSON for ${profile}: $($paths.Json)" -ForegroundColor Yellow
                $payload = $null
            }
        } else {
            Write-Host "WARNING: missing profile JSON for ${profile}: $($paths.Json)" -ForegroundColor Yellow
        }

        $decision = Get-AurumJsonValue -Object $payload -Name "decision" -Default $null
        $decisions = @(Get-AurumJsonValue -Object $payload -Name "decisions" -Default @())
        $basketPayload = Get-AurumJsonValue -Object $payload -Name "basket" -Default $null
        $blockerPayload = Get-AurumJsonValue -Object $payload -Name "blockers_count" -Default $null
        if ($null -eq $blockerPayload) {
            $blockerPayload = Get-AurumJsonValue -Object $payload -Name "blockers" -Default $null
        }

        $volHigh = 0
        $atrHigh = 0
        foreach ($item in $decisions) {
            $codes = @(Get-AurumJsonValue -Object $item -Name "decision_codes" -Default @())
            if ($codes -contains "VOL_HIGH") {
                $volHigh += 1
            }
            if ($codes -contains "ATR_HIGH") {
                $atrHigh += 1
            }
        }

        if ($null -ne $blockerPayload) {
            foreach ($prop in $blockerPayload.PSObject.Properties) {
                $current = 0
                if ($blockers.ContainsKey($prop.Name)) {
                    $current = [int]$blockers[$prop.Name]
                }
                $blockers[$prop.Name] = $current + [int]$prop.Value
            }
        }

        $rows += [pscustomobject]@{
            Profile = $profile
            Actionable = [int](Get-AurumJsonValue -Object $decision -Name "actionable" -Default 0)
            Watch = [int](Get-AurumJsonValue -Object $decision -Name "watch" -Default 0)
            Blocked = [int](Get-AurumJsonValue -Object $decision -Name "blocked" -Default 0)
            VolHigh = $volHigh
            AtrHigh = $atrHigh
            Basket = [string](Get-AurumJsonValue -Object $basketPayload -Name "status" -Default "-")
        }
    }

    Write-Host ""
    Write-Host "PROFILE SUMMARY"
    Write-Host "--------------------------------------------------------------------------------"
    Write-Host ("{0,-7} {1,10} {2,6} {3,8} {4,9} {5,9} {6,9}" -f "PROFILE", "ACTIONABLE", "WATCH", "BLOCKED", "VOL_HIGH", "ATR_HIGH", "BASKET")
    foreach ($row in $rows) {
        Write-Host ("{0,-7} {1,10} {2,6} {3,8} {4,9} {5,9} {6,9}" -f $row.Profile, $row.Actionable, $row.Watch, $row.Blocked, $row.VolHigh, $row.AtrHigh, $row.Basket)
    }

    $totalActionable = ($rows | Measure-Object -Property Actionable -Sum).Sum
    $globalBlockers = @()
    $secondaryBlockers = @()
    if ($blockers.Count -gt 0) {
        $secondaryCodes = @("VOL_HIGH", "ATR_HIGH")
        $globalBlockers = $blockers.GetEnumerator() |
            Where-Object { $secondaryCodes -notcontains $_.Name } |
            Sort-Object -Property @{ Expression = { [int]$_.Value }; Descending = $true }, Name |
            Select-Object -First 3 |
            ForEach-Object { $_.Name }
        $secondaryBlockers = $secondaryCodes | Where-Object {
            $blockers.ContainsKey($_) -and [int]$blockers[$_] -gt 0
        }
    }

    $script:AURUM_LAST_PROFILE_SUMMARY = [pscustomobject]@{
        TotalActionable = [int]$totalActionable
        GlobalBlockers = @($globalBlockers)
        SecondaryBlockers = @($secondaryBlockers)
    }

    if (-not $SkipVerdict) {
        Show-AurumVerdict
    }
}

function Show-AurumVerdict {
    $summary = $script:AURUM_LAST_PROFILE_SUMMARY
    if ($null -eq $summary) {
        $summary = [pscustomobject]@{
            TotalActionable = 0
            GlobalBlockers = @()
            SecondaryBlockers = @()
        }
    }

    Write-Host ""
    Write-Host "VERDICT"
    Write-Host "--------------------------------------------------------------------------------"
    if ([int]$summary.TotalActionable -eq 0) {
        Write-Host "No profile allowed trades."
    } else {
        Write-Host ("Profiles allowed {0} actionable trade(s)." -f [int]$summary.TotalActionable)
    }
    if ($summary.GlobalBlockers.Count -gt 0) {
        Write-Host ("Global blockers dominate: {0}." -f ($summary.GlobalBlockers -join ", "))
    } else {
        Write-Host "Global blockers dominate: none."
    }
    if ($summary.SecondaryBlockers.Count -gt 0) {
        Write-Host ("Secondary blockers vary by profile: {0}." -f ($summary.SecondaryBlockers -join ", "))
    }
}

function Get-AurumPytestCheck {
    param(
        [string]$LogFile,
        [Nullable[int]]$ExitCode = $null
    )

    if (-not $LogFile -or -not (Test-Path -LiteralPath $LogFile)) {
        return [pscustomobject]@{
            Status = "NOT_RUN"
            Tests = "NOT_RUN"
            LogFile = $LogFile
        }
    }

    $text = Get-Content -LiteralPath $LogFile -Raw
    $lines = @($text -split "\r?\n" | Where-Object { $_.Trim() })
    $summaryLine = $lines |
        Where-Object { $_ -match "(?i)(\d+\s+passed|failed|error|no tests ran)" } |
        Select-Object -Last 1
    $tests = "-"
    if ($summaryLine) {
        $tests = ($summaryLine -replace "\s+in\s+[\d\.]+s.*$", "").Trim()
    }

    $failed = $false
    if ($null -ne $ExitCode) {
        $failed = ([int]$ExitCode -ne 0)
    } elseif ($text -match "(?i)(\d+\s+failed|FAILURES|ERRORS|Traceback|FAILED)") {
        $failed = $true
    }

    $passed = $false
    if ($null -ne $ExitCode) {
        $passed = ([int]$ExitCode -eq 0)
    } elseif ($text -match "(?i)\d+\s+passed") {
        $passed = $true
    }

    return [pscustomobject]@{
        Status = if ($failed) { "FAIL" } elseif ($passed) { "PASS" } else { "FAIL" }
        Tests = $tests
        LogFile = $LogFile
    }
}

function Get-AurumScenarioCheck {
    param(
        [string]$LogFile,
        [Nullable[int]]$ExitCode = $null
    )

    if (-not $LogFile -or -not (Test-Path -LiteralPath $LogFile)) {
        return [pscustomobject]@{
            Status = "NOT_RUN"
            LogFile = $LogFile
        }
    }

    $text = Get-Content -LiteralPath $LogFile -Raw
    $hasCheckFail = ($text -match "(?im)^\s*-\s+.+:\s+FAIL\s*$")
    $failed = $false
    if ($null -ne $ExitCode) {
        $failed = ([int]$ExitCode -ne 0)
    } elseif ($text -match "(?i)(Traceback|FAILED|STATUS FAIL|ERROR)" -or $hasCheckFail) {
        $failed = $true
    }

    $passed = $false
    if ($null -ne $ExitCode) {
        $passed = ([int]$ExitCode -eq 0) -and (-not $hasCheckFail)
    } elseif ($text -match "(?i)STATUS OK" -and (-not $hasCheckFail)) {
        $passed = $true
    }

    return [pscustomobject]@{
        Status = if ($failed) { "FAIL" } elseif ($passed) { "PASS" } else { "FAIL" }
        LogFile = $LogFile
    }
}

function Show-AurumSystemChecks {
    param(
        [string]$ScenarioLog = "",
        [Nullable[int]]$ScenarioExitCode = $null,
        [string]$PytestLog = "",
        [Nullable[int]]$PytestExitCode = $null
    )

    $scenario = Get-AurumScenarioCheck -LogFile $ScenarioLog -ExitCode $ScenarioExitCode
    $pytest = Get-AurumPytestCheck -LogFile $PytestLog -ExitCode $PytestExitCode

    Write-Host ""
    Write-Host "SYSTEM CHECKS"
    Write-Host "--------------------------------------------------------------------------------"
    Write-Host ("{0,-18} {1}" -f "scenario_positive", $scenario.Status)
    Write-Host ("{0,-18} {1}" -f "pytest", $pytest.Status)
    Write-Host ("{0,-18} {1}" -f "tests", $pytest.Tests)

    if ($scenario.Status -eq "FAIL") {
        Show-AurumLogTail -LogFile $ScenarioLog -Lines 60
    }
    if ($pytest.Status -eq "FAIL") {
        Show-AurumLogTail -LogFile $PytestLog -Lines 60
    }

    return [pscustomobject]@{
        ScenarioPositive = $scenario.Status
        Pytest = $pytest.Status
        Tests = $pytest.Tests
    }
}

function Show-AurumKeyFiles {
    param(
        [hashtable]$Files,
        [string[]]$Order = @(
            "train_log",
            "pytest_log",
            "report_CON",
            "report_CON_json",
            "basket_CON",
            "manifest"
        )
    )

    Write-Host ""
    Write-Host "KEY FILES"
    Write-Host "--------------------------------------------------------------------------------"
    foreach ($key in $Order) {
        $value = "-"
        if ($Files -and $Files.ContainsKey($key) -and $Files[$key]) {
            $value = "$($Files[$key])"
        }
        Write-Host ("{0,-18} {1}" -f $key, $value)
    }
}

function Write-AurumSummaryValue {
    param(
        [string]$Label,
        [object]$Value,
        [string]$Status = ""
    )

    $text = if ($null -eq $Value -or "$Value" -eq "") { "-" } else { "$Value" }
    $formattedValue = Format-AurumSignalText -Text $text -Status $Status
    Write-Host ("{0,-18} {1}" -f $Label, $formattedValue)
}

function Get-AurumDailyObjectValue {
    param(
        [object]$Object,
        [string]$Name,
        [object]$Default = "-"
    )

    if ($null -eq $Object) {
        return $Default
    }
    if ($Object.PSObject.Properties.Name -contains $Name) {
        return $Object.$Name
    }
    return $Default
}

function Get-AurumShortPermissionSummary {
    param([object[]]$Candidates)

    if (-not $Candidates -or $Candidates.Count -eq 0) {
        return "-"
    }
    foreach ($candidate in $Candidates) {
        $borrowStatus = "$(Get-AurumDailyObjectValue -Object $candidate -Name 'borrow_status' -Default '')"
        if ($borrowStatus -match "DATA_MISSING|MISSING|UNKNOWN") {
            return "DATA_MISSING"
        }
    }
    foreach ($candidate in $Candidates) {
        $manualOnly = Get-AurumDailyObjectValue -Object $candidate -Name "manual_only" -Default $false
        $permission = "$(Get-AurumDailyObjectValue -Object $candidate -Name 'permission' -Default '')"
        if ($manualOnly -eq $true -or $permission -match "MANUAL") {
            return "MANUAL_ONLY"
        }
    }
    foreach ($candidate in $Candidates) {
        $permission = "$(Get-AurumDailyObjectValue -Object $candidate -Name 'permission' -Default '')"
        $action = "$(Get-AurumDailyObjectValue -Object $candidate -Name 'action' -Default '')"
        if ($permission -match "BLOCKED" -or $action -match "BLOCKED") {
            return "BLOCKED"
        }
    }
    return "OK"
}

function Show-AurumDailySummary {
    param(
        [string]$ReportJson,
        [string]$UpdateStatusFile,
        [string]$RunLog
    )

    Write-Host ""
    Write-Host "DAILY SUMMARY"
    Write-Host "--------------------------------------------------------------------------------"

    if (-not (Test-Path -LiteralPath $ReportJson)) {
        Write-AurumSummaryValue -Label "warning" -Value "report json not found" -Status "WARNING"
        Write-AurumSummaryValue -Label "json" -Value $ReportJson
        Write-AurumSummaryValue -Label "run_log" -Value $RunLog
        return
    }

    try {
        $payload = Get-Content -LiteralPath $ReportJson -Raw | ConvertFrom-Json
    } catch {
        Write-AurumSummaryValue -Label "warning" -Value "unable to parse report json" -Status "WARNING"
        Write-AurumSummaryValue -Label "json" -Value $ReportJson
        Write-AurumSummaryValue -Label "run_log" -Value $RunLog
        return
    }

    $updatePayload = Get-AurumDailyObjectValue -Object $payload -Name "update_status" -Default $null
    if ($null -eq $updatePayload -and $UpdateStatusFile -and (Test-Path -LiteralPath $UpdateStatusFile)) {
        try {
            $updatePayload = Get-Content -LiteralPath $UpdateStatusFile -Raw | ConvertFrom-Json
        } catch {
            $updatePayload = $null
        }
    }

    $marketContext = Get-AurumDailyObjectValue -Object $payload -Name "market_context" -Default $null
    $regimeSummary = Get-AurumDailyObjectValue -Object $marketContext -Name "regime_summary" -Default $null
    $marketRegime = Get-AurumDailyObjectValue -Object $payload -Name "market_regime" -Default $null
    $prediction = Get-AurumDailyObjectValue -Object $payload -Name "prediction" -Default $null
    $predictionQuality = Get-AurumDailyObjectValue -Object $prediction -Name "model_quality" -Default $null
    $modelQuality = Get-AurumDailyObjectValue -Object $payload -Name "model_quality" -Default $null
    if ($modelQuality -isnot [string]) {
        $modelQuality = Get-AurumDailyObjectValue -Object $modelQuality -Name "status" -Default $null
    }
    if (-not $modelQuality -or "$modelQuality" -eq "-") {
        $modelQuality = Get-AurumDailyObjectValue -Object $predictionQuality -Name "status" -Default "-"
    }
    $edge = Get-AurumDailyObjectValue -Object $payload -Name "model_edge" -Default $null
    if ($null -eq $edge -or "$edge" -eq "-") {
        $edge = Get-AurumDailyObjectValue -Object $predictionQuality -Name "edge" -Default "-"
    }

    $decision = Get-AurumDailyObjectValue -Object $payload -Name "decision" -Default $null
    $basket = Get-AurumDailyObjectValue -Object $payload -Name "basket" -Default $null
    $shortCandidates = @(Get-AurumDailyObjectValue -Object $payload -Name "short_candidates" -Default @())
    if ($shortCandidates.Count -eq 0) {
        $defensiveBook = Get-AurumDailyObjectValue -Object $payload -Name "defensive_book" -Default $null
        $shortCandidates = @(Get-AurumDailyObjectValue -Object $defensiveBook -Name "short_candidates" -Default @())
    }
    $observationCandidates = @(Get-AurumDailyObjectValue -Object $payload -Name "observation_candidates" -Default @())

    $updateStatus = Get-AurumDailyObjectValue -Object $updatePayload -Name "status" -Default "-"
    $freshness = Get-AurumDailyObjectValue -Object (Get-AurumDailyObjectValue -Object $updatePayload -Name "freshness" -Default $null) -Name "freshness_status" -Default "-"
    $market = Get-AurumDailyObjectValue -Object $regimeSummary -Name "market_regime" -Default (Get-AurumDailyObjectValue -Object $marketRegime -Name "regime" -Default "-")
    $trend = Get-AurumDailyObjectValue -Object $regimeSummary -Name "market_trend" -Default (Get-AurumDailyObjectValue -Object $marketContext -Name "market_trend" -Default "-")
    $volatility = Get-AurumDailyObjectValue -Object $regimeSummary -Name "market_volatility" -Default (Get-AurumDailyObjectValue -Object $marketContext -Name "market_volatility" -Default "-")
    $contextScore = Get-AurumDailyObjectValue -Object $regimeSummary -Name "context_score" -Default "-"
    $behavior = Get-AurumDailyObjectValue -Object $prediction -Name "behavior" -Default "-"
    $alignment = Get-AurumDailyObjectValue -Object $prediction -Name "horizon_alignment" -Default "-"
    $longBasket = Get-AurumDailyObjectValue -Object $basket -Name "status" -Default "-"
    $actionable = [int](Get-AurumDailyObjectValue -Object $decision -Name "actionable" -Default 0)
    $blocked = [int](Get-AurumDailyObjectValue -Object $decision -Name "blocked" -Default 0)
    $shortPermission = Get-AurumShortPermissionSummary -Candidates $shortCandidates
    $finalDecision = if ($actionable -gt 0 -and "$longBasket" -eq "OK") {
        "REVIEW BASKET"
    } elseif ($actionable -gt 0) {
        "MANUAL REVIEW"
    } else {
        "NO LONG TRADE"
    }

    Write-AurumSummaryValue -Label "update" -Value $updateStatus -Status $updateStatus
    Write-AurumSummaryValue -Label "data_freshness" -Value $freshness -Status $freshness
    Write-AurumSummaryValue -Label "market" -Value $market -Status $market
    Write-AurumSummaryValue -Label "trend" -Value $trend -Status $trend
    Write-AurumSummaryValue -Label "volatility" -Value $volatility -Status $volatility
    Write-AurumSummaryValue -Label "context_score" -Value $contextScore
    Write-AurumSummaryValue -Label "model_quality" -Value $modelQuality -Status $modelQuality
    Write-AurumSummaryValue -Label "edge" -Value $edge
    Write-AurumSummaryValue -Label "behavior" -Value $behavior -Status $behavior
    Write-AurumSummaryValue -Label "alignment" -Value $alignment -Status $alignment
    Write-AurumSummaryValue -Label "long_basket" -Value $longBasket -Status $longBasket
    Write-AurumSummaryValue -Label "actionable" -Value $actionable
    Write-AurumSummaryValue -Label "blocked" -Value $blocked
    Write-AurumSummaryValue -Label "observation" -Value ("{0} candidates" -f $observationCandidates.Count)
    Write-AurumSummaryValue -Label "short_setups" -Value ("{0} candidates" -f $shortCandidates.Count)
    Write-AurumSummaryValue -Label "short_permission" -Value $shortPermission -Status $shortPermission
    Write-AurumSummaryValue -Label "decision" -Value $finalDecision -Status $finalDecision
}

function Get-AurumSignalColorCode {
    param([string]$Status)

    $key = "$Status".ToUpperInvariant()
    if ($key -match "^(OK|PASS|STRONG|READY|EXEC_READY|RISK_ON|TREND_CONFIRM|ALIGNED_STRONG|REVIEW LONG BASKET|REVIEW BASKET|OBS_FAVORABLE|BUY_SETUP|SELL_SETUP)$") {
        return "32"
    }
    if ($key -match "^(WARNING|PARTIAL|WATCH|MANUAL_ONLY|MANUAL REVIEW|CHOPPY|HEDGE_WATCH)$") {
        return "33"
    }
    if ($key -match "^(FAIL|WEAK|DEGENERATE|BLOCKED|SHORT_BLOCKED|RISK_OFF|AVOID|NO LONG TRADE)$") {
        return "31"
    }
    if ($key -match "^(DATA_MISSING|DATA_BLOCKED|UNKNOWN|BORROW_DATA_MISSING|EVENT_UNKNOWN)$") {
        return "90"
    }
    if ($key -match "^(CASH|WAIT|HOLD_CASH|PREFERRED|DEFENSIVE MODE ACTIVE)$") {
        return "36"
    }
    return ""
}

function Format-AurumSignalText {
    param(
        [object]$Text,
        [string]$Status = ""
    )

    $value = if ($null -eq $Text -or "$Text" -eq "") { "-" } else { "$Text" }
    if ($script:AURUM_COLOR -eq "never" -or -not $Status) {
        return $value
    }
    $code = Get-AurumSignalColorCode -Status $Status
    if (-not $code) {
        return $value
    }
    $esc = [char]27
    return "$esc[${code}m$value$esc[0m"
}

function Format-AurumSignalCell {
    param(
        [object]$Text,
        [int]$Width,
        [string]$Align = "Left",
        [string]$Status = ""
    )

    $value = if ($null -eq $Text -or "$Text" -eq "") { "-" } else { "$Text" }
    if ($value.Length -gt $Width) {
        $value = $value.Substring(0, [Math]::Max(0, $Width - 1)) + "."
    }
    $padded = if ($Align -eq "Right") {
        $value.PadLeft($Width)
    } else {
        $value.PadRight($Width)
    }
    return Format-AurumSignalText -Text $padded -Status $Status
}

function Format-AurumSignalNumber {
    param(
        [object]$Value,
        [int]$Decimals = 1
    )

    try {
        return ([double]$Value).ToString("F$Decimals", [System.Globalization.CultureInfo]::InvariantCulture)
    } catch {
        return "-"
    }
}

function Normalize-AurumSignalStatus {
    param([object]$Value)

    $text = "$Value".Trim().ToUpperInvariant()
    if (-not $text) {
        return "-"
    }
    if ($text -eq "OBS_READY") {
        return "OBS_FAVORABLE"
    }
    if ($text -match "DATA_MISSING|MISSING|UNKNOWN") {
        return "DATA_MISSING"
    }
    if ($text -match "SHORT_BLOCKED|BLOCKED") {
        return "BLOCKED"
    }
    if ($text -match "MANUAL") {
        return "MANUAL_ONLY"
    }
    if ($text -match "READY|OK|ALLOW") {
        return "READY"
    }
    return $text
}

function Get-AurumObservationClassForTicker {
    param(
        [string]$Ticker,
        [object[]]$Candidates,
        [string]$Default = "WATCH"
    )

    $tickerKey = "$Ticker".Trim().ToUpperInvariant()
    if (-not $tickerKey) {
        return $Default
    }

    foreach ($candidate in @($Candidates)) {
        $candidateTicker = "$(Get-AurumDailyObjectValue -Object $candidate -Name 'ticker' -Default '')".Trim().ToUpperInvariant()
        if ($candidateTicker -eq $tickerKey) {
            return Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $candidate -Name "class" -Default $Default)
        }
    }

    return $Default
}

function Get-AurumBoardSignal {
    param(
        [object]$Value,
        [string]$Default
    )

    if ($null -eq $Value -or "$Value" -eq "") {
        $text = "$Default"
    } else {
        $text = "$Value"
    }
    $text = $text.Trim().ToUpperInvariant()
    if ($text -match "SHORT_SETUP|SELL") {
        return "SELL_SETUP"
    }
    if ($text -match "BUY|LONG") {
        return "BUY_SETUP"
    }
    if ($text -match "HEDGE") {
        return "HEDGE_WATCH"
    }
    if ($text -match "NO_") {
        return "NO_SETUP"
    }
    return $Default
}

function Get-AurumLongSignalRows {
    param(
        [object[]]$Decisions,
        [object[]]$ObservationCandidates = @(),
        [int]$Limit = 10
    )

    $rows = @()
    foreach ($item in @($Decisions | Select-Object -First $Limit)) {
        $asset = Get-AurumDailyObjectValue -Object $item -Name "asset" -Default $null
        $ranking = Get-AurumDailyObjectValue -Object $item -Name "ranking" -Default $null
        $permission = Get-AurumDailyObjectValue -Object $item -Name "permission" -Default $null
        $validation = Get-AurumDailyObjectValue -Object $item -Name "validation" -Default $null
        $execution = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $permission -Name "status" -Default "")
        if ($execution -eq "-") {
            $execution = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $validation -Name "status" -Default "-")
        }
        $score = Get-AurumDailyObjectValue -Object $ranking -Name "context_score" -Default (Get-AurumDailyObjectValue -Object $ranking -Name "raw_score" -Default "-")
        $signalRaw = Get-AurumDailyObjectValue -Object $ranking -Name "context_signal" -Default (Get-AurumDailyObjectValue -Object $ranking -Name "raw_signal" -Default "BUY")
        $reason = Get-AurumDailyObjectValue -Object $item -Name "decision_label" -Default ""
        $reasons = @(Get-AurumDailyObjectValue -Object $item -Name "blocker_reasons" -Default @())
        if ($reasons.Count -gt 0) {
            $reason = $reasons -join "+"
        } elseif (-not $reason) {
            $permissionReasons = @(Get-AurumDailyObjectValue -Object $permission -Name "reasons" -Default @())
            $validationReasons = @(Get-AurumDailyObjectValue -Object $validation -Name "reasons" -Default @())
            if ($permissionReasons.Count -gt 0) {
                $reason = $permissionReasons[0]
            } elseif ($validationReasons.Count -gt 0) {
                $reason = $validationReasons[0]
            } else {
                $reason = "-"
            }
        }
        $ticker = Get-AurumDailyObjectValue -Object $asset -Name "ticker" -Default "-"
        $rows += [pscustomobject]@{
            Ticker = $ticker
            ObsClass = Get-AurumObservationClassForTicker -Ticker $ticker -Candidates $ObservationCandidates -Default "WATCH"
            Signal = Get-AurumBoardSignal -Value $signalRaw -Default "BUY_SETUP"
            Execution = $execution
            Score = $score
            MainReason = $reason
        }
    }
    return $rows
}

function Get-AurumShortSignalRows {
    param(
        [object[]]$Candidates,
        [int]$Limit = 10
    )

    $rows = @()
    foreach ($item in @($Candidates | Select-Object -First $Limit)) {
        $borrow = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $item -Name "borrow_status" -Default "-")
        $permission = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $item -Name "short_permission" -Default (Get-AurumDailyObjectValue -Object $item -Name "permission" -Default "-"))
        $shortExecution = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $item -Name "short_execution_status" -Default "")
        $execution = $permission
        $reason = Get-AurumDailyObjectValue -Object $item -Name "reason" -Default (Get-AurumDailyObjectValue -Object $item -Name "setup_reason" -Default "-")
        if ($shortExecution -and $shortExecution -ne "-") {
            $execution = $shortExecution
            $reason = Get-AurumDailyObjectValue -Object $item -Name "short_execution_reason" -Default $reason
        } elseif ($borrow -eq "DATA_MISSING" -or $borrow -eq "BORROW_DATA_MISSING") {
            $execution = "DATA_BLOCKED"
            $reason = "borrow data missing"
        }
        $setup = Get-AurumDailyObjectValue -Object $item -Name "short_setup_status" -Default (Get-AurumDailyObjectValue -Object $item -Name "class" -Default "SHORT_SETUP")
        $rows += [pscustomobject]@{
            Ticker = Get-AurumDailyObjectValue -Object $item -Name "ticker" -Default "-"
            ObsClass = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $item -Name "class" -Default $setup)
            Signal = Get-AurumBoardSignal -Value $setup -Default "SELL_SETUP"
            Execution = $execution
            Score = Get-AurumDailyObjectValue -Object $item -Name "short_score" -Default (Get-AurumDailyObjectValue -Object $item -Name "score" -Default "-")
            MainReason = $reason
        }
    }
    return $rows
}

function Get-AurumLongObservationRows {
    param(
        [object[]]$Candidates,
        [object[]]$Decisions,
        [int]$Limit = 5
    )

    $rows = @()
    foreach ($candidate in @($Candidates | Select-Object -First $Limit)) {
        $ticker = Get-AurumDailyObjectValue -Object $candidate -Name "ticker" -Default "-"
        $obsClass = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $candidate -Name "class" -Default "WATCH")
        $score = Get-AurumDailyObjectValue -Object $candidate -Name "score" -Default (Get-AurumDailyObjectValue -Object $candidate -Name "obs_index" -Default "-")
        $mainReason = Get-AurumDailyObjectValue -Object $candidate -Name "reason" -Default "-"
        $signal = "BUY_SETUP"
        $execution = "WATCH"

        foreach ($decision in @($Decisions)) {
            $asset = Get-AurumDailyObjectValue -Object $decision -Name "asset" -Default $null
            $decisionTicker = Get-AurumDailyObjectValue -Object $asset -Name "ticker" -Default ""
            if ("$decisionTicker".Trim().ToUpperInvariant() -ne "$ticker".Trim().ToUpperInvariant()) {
                continue
            }

            $matched = @(Get-AurumLongSignalRows -Decisions @($decision) -ObservationCandidates $Candidates -Limit 1)
            if ($matched.Count -gt 0) {
                $signal = $matched[0].Signal
                $execution = $matched[0].Execution
                if ($execution -ne "WATCH" -and $matched[0].MainReason -and $matched[0].MainReason -ne "-") {
                    $mainReason = $matched[0].MainReason
                }
            }
            break
        }

        $rows += [pscustomobject]@{
            Ticker = $ticker
            ObsClass = $obsClass
            Signal = $signal
            Execution = $execution
            Score = $score
            MainReason = $mainReason
        }
    }
    return $rows
}

function Write-AurumSignalBoardRows {
    param(
        [string]$Title,
        [object[]]$Rows,
        [string]$EmptyReason
    )

    Write-Host ""
    Write-Host $Title
    Write-Host "--------------------------------------------------------------------------------"
    Write-Host ("{0,2}  {1,-8} {2,-13} {3,-11} {4,-12} {5,7}  {6}" -f "#", "TICKER", "OBS_CLASS", "SIGNAL", "EXECUTION", "SCORE", "MAIN_REASON")
    if (-not $Rows -or $Rows.Count -eq 0) {
        Write-AurumSummaryValue -Label "status" -Value "EMPTY"
        Write-AurumSummaryValue -Label "reason" -Value $EmptyReason
        return
    }

    $index = 1
    foreach ($row in $Rows) {
        Write-Host (
            "{0,2}  {1,-8} {2} {3} {4} {5,7}  {6}" -f
            $index,
            $row.Ticker,
            (Format-AurumSignalCell -Text $row.ObsClass -Width 13 -Status $row.ObsClass),
            (Format-AurumSignalCell -Text $row.Signal -Width 11 -Status $row.Signal),
            (Format-AurumSignalCell -Text $row.Execution -Width 12 -Status $row.Execution),
            (Format-AurumSignalNumber -Value $row.Score -Decimals 1),
            $row.MainReason
        )
        $index += 1
    }
}

function Show-AurumSignals {
    param(
        [string]$ReportJson,
        [string]$BasketFile,
        [string]$UpdateStatusFile = "",
        [string]$RunLog = "",
        [string]$ObserveLog = "",
        [int]$LongLimit = 10,
        [int]$ShortLimit = 10,
        [int]$ObservationLimit = 5
    )

    Write-Host ""
    Write-Host "AURUM SIGNALS"
    Write-Host "--------------------------------------------------------------------------------"

    if (-not (Test-Path -LiteralPath $ReportJson)) {
        Write-AurumSummaryValue -Label "warning" -Value "report json not found" -Status "WARNING"
        Write-AurumSummaryValue -Label "json" -Value $ReportJson
        Write-AurumSummaryValue -Label "run_log" -Value $RunLog
        return
    }

    try {
        $payload = Get-Content -LiteralPath $ReportJson -Raw | ConvertFrom-Json
    } catch {
        Write-AurumSummaryValue -Label "warning" -Value "unable to parse report json" -Status "WARNING"
        Write-AurumSummaryValue -Label "json" -Value $ReportJson
        Write-AurumSummaryValue -Label "run_log" -Value $RunLog
        return
    }

    $marketContext = Get-AurumDailyObjectValue -Object $payload -Name "market_context" -Default $null
    $regimeSummary = Get-AurumDailyObjectValue -Object $marketContext -Name "regime_summary" -Default $null
    $marketRegime = Get-AurumDailyObjectValue -Object $payload -Name "market_regime" -Default $null
    $prediction = Get-AurumDailyObjectValue -Object $payload -Name "prediction" -Default $null
    $predictionQuality = Get-AurumDailyObjectValue -Object $prediction -Name "model_quality" -Default $null
    $modelQuality = Get-AurumDailyObjectValue -Object $payload -Name "model_quality" -Default $null
    if ($modelQuality -isnot [string]) {
        $modelQuality = Get-AurumDailyObjectValue -Object $modelQuality -Name "status" -Default $null
    }
    if (-not $modelQuality -or "$modelQuality" -eq "-") {
        $modelQuality = Get-AurumDailyObjectValue -Object $predictionQuality -Name "status" -Default "-"
    }

    $decision = Get-AurumDailyObjectValue -Object $payload -Name "decision" -Default $null
    $basket = Get-AurumDailyObjectValue -Object $payload -Name "basket" -Default $null
    $defensiveBook = Get-AurumDailyObjectValue -Object $payload -Name "defensive_book" -Default $null
    $shortCandidates = @(Get-AurumDailyObjectValue -Object $payload -Name "short_candidates" -Default @())
    if ($shortCandidates.Count -eq 0) {
        $shortCandidates = @(Get-AurumDailyObjectValue -Object $defensiveBook -Name "short_candidates" -Default @())
    }
    $hedgeCandidates = @(Get-AurumDailyObjectValue -Object $payload -Name "hedge_candidates" -Default @())
    if ($hedgeCandidates.Count -eq 0) {
        $hedgeCandidates = @(Get-AurumDailyObjectValue -Object $defensiveBook -Name "hedge_candidates" -Default @())
    }
    $observationCandidates = @(Get-AurumDailyObjectValue -Object $payload -Name "observation_candidates" -Default @())
    $shortObservationCandidates = @(Get-AurumDailyObjectValue -Object $payload -Name "short_observation_candidates" -Default @())
    if ($shortObservationCandidates.Count -eq 0) {
        $shortObservationCandidates = $shortCandidates
    }
    $decisions = @(Get-AurumDailyObjectValue -Object $payload -Name "decisions" -Default @())

    $profile = Get-AurumDailyObjectValue -Object $payload -Name "profile" -Default "CON"
    $market = Get-AurumDailyObjectValue -Object $regimeSummary -Name "market_regime" -Default (Get-AurumDailyObjectValue -Object $marketRegime -Name "regime" -Default "-")
    $trend = Get-AurumDailyObjectValue -Object $regimeSummary -Name "market_trend" -Default (Get-AurumDailyObjectValue -Object $marketContext -Name "market_trend" -Default "-")
    $contextScore = Get-AurumDailyObjectValue -Object $regimeSummary -Name "context_score" -Default "-"
    $dataFreshness = "-"
    $dataQuality = "-"
    if ($UpdateStatusFile -and (Test-Path -LiteralPath $UpdateStatusFile)) {
        try {
            $updateStatus = Get-Content -LiteralPath $UpdateStatusFile -Raw | ConvertFrom-Json
            $freshness = Get-AurumDailyObjectValue -Object $updateStatus -Name "freshness" -Default $null
            $dataFreshness = Get-AurumDailyObjectValue -Object $freshness -Name "freshness_status" -Default "-"
            $dataQuality = Get-AurumDailyObjectValue -Object $freshness -Name "data_quality_score" -Default "-"
        } catch {
            $dataFreshness = "UNKNOWN"
            $dataQuality = "-"
        }
    }
    $behavior = Get-AurumDailyObjectValue -Object $prediction -Name "behavior" -Default "-"
    $longBasket = Get-AurumDailyObjectValue -Object $basket -Name "status" -Default "-"
    $defensiveMode = Get-AurumDailyObjectValue -Object $defensiveBook -Name "defensive_mode" -Default "inactive"
    if ($longBasket -eq "BLOCKED" -and $defensiveMode -eq "-") {
        $defensiveMode = "active"
    }
    $actionable = [int](Get-AurumDailyObjectValue -Object $decision -Name "actionable" -Default 0)
    $watch = [int](Get-AurumDailyObjectValue -Object $decision -Name "watch" -Default 0)
    $blocked = [int](Get-AurumDailyObjectValue -Object $decision -Name "blocked" -Default 0)
    $shortPermission = Get-AurumShortPermissionSummary -Candidates $shortCandidates
    $shortReady = 0
    $shortDataBlocked = 0
    foreach ($candidate in $shortCandidates) {
        $permission = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $candidate -Name "short_permission" -Default (Get-AurumDailyObjectValue -Object $candidate -Name "permission" -Default "-"))
        $borrow = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $candidate -Name "borrow_status" -Default "-")
        if ($permission -eq "READY" -and $borrow -ne "DATA_MISSING") {
            $shortReady += 1
        }
        if ($borrow -eq "DATA_MISSING") {
            $shortDataBlocked += 1
        }
    }
    $hedgeStatus = if ($hedgeCandidates.Count -gt 0) { "WATCH" } else { "NONE" }
    $cashStatus = if ("$defensiveMode".ToLowerInvariant() -eq "active" -or $longBasket -eq "BLOCKED") { "PREFERRED" } else { "NEUTRAL" }

    Write-AurumSummaryValue -Label "date" -Value (Get-Date -Format "yyyy-MM-dd")
    Write-AurumSummaryValue -Label "profile" -Value $profile
    Write-AurumSummaryValue -Label "market" -Value $market -Status $market
    Write-AurumSummaryValue -Label "trend" -Value $trend -Status $trend
    Write-AurumSummaryValue -Label "context_score" -Value (Format-AurumSignalNumber -Value $contextScore -Decimals 1)
    Write-AurumSummaryValue -Label "data_freshness" -Value $dataFreshness -Status $dataFreshness
    Write-AurumSummaryValue -Label "data_quality" -Value (Format-AurumSignalNumber -Value $dataQuality -Decimals 1)
    Write-AurumSummaryValue -Label "model_quality" -Value $modelQuality -Status $modelQuality
    Write-AurumSummaryValue -Label "behavior" -Value $behavior -Status $behavior
    Write-AurumSummaryValue -Label "long_basket" -Value $longBasket -Status $longBasket
    Write-AurumSummaryValue -Label "defensive_mode" -Value $defensiveMode -Status $defensiveMode

    Write-Host ""
    Write-Host "SIGNAL SUMMARY"
    Write-Host "--------------------------------------------------------------------------------"
    Write-Host ("{0,-18} {1} READY | {2} WATCH | {3} BLOCKED" -f "LONG/BUY", $actionable, $watch, $blocked)
    Write-Host ("{0,-18} {1} SETUPS | {2} EXEC_READY | {3} DATA_BLOCKED" -f "SELL-SHORT", $shortCandidates.Count, $shortReady, $shortDataBlocked)
    Write-Host ("{0,-18} {1}" -f "HEDGE", (Format-AurumSignalText -Text $hedgeStatus -Status $hedgeStatus))
    Write-Host ("{0,-18} {1}" -f "CASH", (Format-AurumSignalText -Text $cashStatus -Status $cashStatus))

    $longRows = @(Get-AurumLongSignalRows -Decisions $decisions -ObservationCandidates $observationCandidates -Limit $LongLimit)
    Write-AurumSignalBoardRows -Title "LONG / BUY BOARD" -Rows $longRows -EmptyReason "no long candidates in report"
    if ($longRows.Count -eq 0) {
        Write-Host "No long candidates in report."
    } elseif ($actionable -eq 0) {
        Write-Host "No READY long execution."
    }

    $shortRows = @(Get-AurumShortSignalRows -Candidates $shortCandidates -Limit $ShortLimit)
    Write-AurumSignalBoardRows -Title "SHORT / SELL BOARD" -Rows $shortRows -EmptyReason "no short setup candidates"

    Write-Host ""
    Write-Host "HEDGE / DEFENSE"
    Write-Host "--------------------------------------------------------------------------------"
    Write-Host ("{0,-10}  {1,-9}  {2}" -f "TARGET", "STATUS", "REASON")
    if ($hedgeCandidates.Count -eq 0 -and $cashStatus -ne "PREFERRED") {
        Write-Host "No hedge or cash defense candidates."
    } else {
        $printedCashDefense = $false
        foreach ($row in @($hedgeCandidates | Select-Object -First 5)) {
            $target = Get-AurumDailyObjectValue -Object $row -Name "target" -Default "-"
            if ("$target".ToUpperInvariant() -eq "CASH") {
                $printedCashDefense = $true
            }
            $status = Normalize-AurumSignalStatus -Value (Get-AurumDailyObjectValue -Object $row -Name "status" -Default (Get-AurumDailyObjectValue -Object $row -Name "action" -Default "WATCH"))
            if ($status -eq "HEDGE_WATCH") {
                $status = "WATCH"
            }
            $reason = Get-AurumDailyObjectValue -Object $row -Name "reason" -Default "-"
            Write-Host (
                "{0,-10}  {1}  {2}" -f
                $target,
                (Format-AurumSignalCell -Text $status -Width 9 -Status $status),
                $reason
            )
        }
        if ($cashStatus -eq "PREFERRED" -and -not $printedCashDefense) {
            Write-Host (
                "{0,-10}  {1}  {2}" -f
                "CASH",
                (Format-AurumSignalCell -Text "PREFERRED" -Width 9 -Status "PREFERRED"),
                "no long basket allowed"
            )
        }
    }

    $longObservationRows = @(Get-AurumLongObservationRows -Candidates $observationCandidates -Decisions $decisions -Limit $ObservationLimit)
    Write-AurumSignalBoardRows -Title "LONG OBSERVATION" -Rows $longObservationRows -EmptyReason "no long observation candidates"

    $shortObservationRows = @(Get-AurumShortSignalRows -Candidates $shortObservationCandidates -Limit $ObservationLimit)
    Write-AurumSignalBoardRows -Title "SHORT OBSERVATION" -Rows $shortObservationRows -EmptyReason "no short observation candidates"

    Write-Host ""
    Write-Host "BASKET"
    Write-Host "--------------------------------------------------------------------------------"
    Write-AurumSummaryValue -Label "status" -Value $longBasket -Status $longBasket
    Write-AurumSummaryValue -Label "assets" -Value (Get-AurumDailyObjectValue -Object $basket -Name "assets" -Default 0)
    Write-AurumSummaryValue -Label "reason" -Value (Get-AurumDailyObjectValue -Object $basket -Name "reason" -Default "-")

    Write-Host ""
    Write-Host "FINAL DECISION"
    Write-Host "--------------------------------------------------------------------------------"
    if ($longBasket -eq "OK" -and $actionable -gt 0) {
        Write-Host (Format-AurumSignalText -Text "REVIEW LONG BASKET." -Status "REVIEW LONG BASKET")
        Write-Host "Execution requires human confirmation."
    } else {
        Write-Host (Format-AurumSignalText -Text "NO LONG TRADE." -Status "NO LONG TRADE")
        if ("$defensiveMode".ToLowerInvariant() -eq "active" -or $shortCandidates.Count -gt 0 -or $hedgeCandidates.Count -gt 0) {
            Write-Host (Format-AurumSignalText -Text "DEFENSIVE MODE ACTIVE." -Status "DEFENSIVE MODE ACTIVE")
        }
        if ($shortCandidates.Count -gt 0 -and $shortPermission -eq "DATA_MISSING") {
            Write-Host "Short setups exist, but execution is blocked until borrow/cost data is available."
        } elseif ($shortCandidates.Count -gt 0) {
            Write-Host "Short setups exist; execution still requires manual permission checks."
        } elseif ($hedgeCandidates.Count -gt 0) {
            Write-Host "Hedge watch is active; no automatic execution is authorized."
        } else {
            Write-Host "Cash/wait is preferred until signals improve."
        }
    }
}

function Read-RuntimeConfig {
    $repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
    $configPath = Join-Path $repoRoot "config\runtime.json"
    $fallback = [ordered]@{
        python_executable = "C:\Users\zepau\anaconda3\python.exe"
        project_root = $repoRoot.Path
        default_list = "IBOV"
        color = "never"
    }

    if (-not (Test-Path -LiteralPath $configPath)) {
        return [pscustomobject]$fallback
    }

    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    } catch {
        throw "Unable to parse config/runtime.json: $_"
    }

    foreach ($key in $fallback.Keys) {
        if (-not $config.PSObject.Properties.Name.Contains($key) -or -not $config.$key) {
            $config | Add-Member -NotePropertyName $key -NotePropertyValue $fallback[$key] -Force
        }
    }
    return $config
}

function Test-AurumPython {
    param([string]$Command)

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command --version *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Resolve-AurumPython {
    param(
        [string]$Requested = "",
        [string]$Configured = ""
    )

    $candidate = ""
    if ($Requested) {
        $candidate = $Requested
    } elseif ($env:AURUM_PYTHON) {
        $candidate = $env:AURUM_PYTHON
    } elseif ($Configured) {
        $candidate = $Configured
    }

    if (-not $candidate) {
        throw "Python not configured. Set config/runtime.json python_executable."
    }

    $resolved = ""
    if (Test-Path -LiteralPath $candidate) {
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
    } else {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            $resolved = $command.Source
            if (-not $resolved) {
                $resolved = $command.Path
            }
        }
    }

    if (-not $resolved) {
        throw "Configured Python not found: $candidate"
    }

    if (-not (Test-AurumPython -Command $resolved)) {
        throw "Configured Python is not executable: $resolved"
    }

    return $resolved
}

function Get-PythonVersion {
    param([string]$Python)

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = & $Python --version 2>&1 | Select-Object -First 1
        if ($LASTEXITCODE -ne 0) {
            return "UNKNOWN"
        }
        return "$version"
    } catch {
        return "UNKNOWN"
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Get-GitInfo {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $branch = (git branch --show-current 2>$null | Select-Object -First 1)
        $commit = (git rev-parse --short HEAD 2>$null | Select-Object -First 1)
        $dirtyText = (git status --porcelain 2>$null)
        return [pscustomobject]@{
            branch = if ($branch) { "$branch" } else { "UNKNOWN" }
            commit = if ($commit) { "$commit" } else { "UNKNOWN" }
            dirty = [bool]$dirtyText
        }
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Initialize-AurumScript {
    param(
        [string]$RequestedPython = "",
        [string]$ScriptName = ""
    )

    $config = Read-RuntimeConfig
    $script:PROJECT_ROOT = (Resolve-Path -LiteralPath $config.project_root).Path
    Set-Location $script:PROJECT_ROOT

    $script:AURUM_DEFAULT_LIST = "$($config.default_list)"
    $script:AURUM_COLOR = "$($config.color)"
    $script:AURUM_SCRIPT_NAME = if ($ScriptName) { $ScriptName } else { "unknown_script.ps1" }
    $script:PY = Resolve-AurumPython -Requested $RequestedPython -Configured "$($config.python_executable)"
    $script:PYTHON_VERSION = Get-PythonVersion -Python $script:PY
    $script:GIT_INFO = Get-GitInfo
    return $script:PY
}

function New-AurumLogDir {
    param(
        [string]$Prefix,
        [string]$ScriptName = ""
    )

    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $logDir = Join-Path "runtime" "${Prefix}_$ts"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $script:AURUM_RUNTIME_DIR = $logDir
    $script:AURUM_MANIFEST_PATH = Join-Path $logDir "manifest.json"

    $resolvedScript = if ($ScriptName) { $ScriptName } elseif ($script:AURUM_SCRIPT_NAME) { $script:AURUM_SCRIPT_NAME } else { "unknown_script.ps1" }
    $script:AURUM_MANIFEST = [ordered]@{
        schema_version = "runtime_manifest.v1"
        script = $resolvedScript
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        project_root = $script:PROJECT_ROOT
        python = [ordered]@{
            executable = $script:PY
            version = $script:PYTHON_VERSION
        }
        git = [ordered]@{
            branch = $script:GIT_INFO.branch
            commit = $script:GIT_INFO.commit
            dirty = [bool]$script:GIT_INFO.dirty
        }
        commands = @()
        outputs = [ordered]@{}
        status = "RUNNING"
    }
    Write-RunManifest -Status "RUNNING"
    return $logDir
}

function Write-AurumRuntimeHeader {
    param([string]$Title)

    Write-Host ""
    if ($Title) {
        Write-Host $Title
    }
    Write-Host "PYTHON : $script:PY"
    Write-Host "VERSION: $script:PYTHON_VERSION"
    Write-Host "GIT    : $($script:GIT_INFO.branch) $($script:GIT_INFO.commit) dirty=$($script:GIT_INFO.dirty)"
    Write-Host "RUNTIME: $script:AURUM_RUNTIME_DIR"
    Write-Host ""
}

function Write-RunManifest {
    param(
        [string]$Status = "",
        [hashtable]$Outputs = @{}
    )

    if (-not $script:AURUM_MANIFEST -or -not $script:AURUM_MANIFEST_PATH) {
        return
    }

    if ($Status) {
        $script:AURUM_MANIFEST.status = $Status
    }
    if ($Outputs -and $Outputs.Count -gt 0) {
        $orderedOutputs = [ordered]@{}
        foreach ($key in $Outputs.Keys) {
            $orderedOutputs[$key] = "$($Outputs[$key])"
        }
        $script:AURUM_MANIFEST.outputs = $orderedOutputs
    }
    $script:AURUM_MANIFEST.updated_at = (Get-Date).ToUniversalTime().ToString("o")
    $json = $script:AURUM_MANIFEST | ConvertTo-Json -Depth 12
    Set-Content -LiteralPath $script:AURUM_MANIFEST_PATH -Value $json -Encoding UTF8
}

function Show-AurumLogTail {
    param(
        [string]$LogFile,
        [int]$Lines = 100
    )

    if (-not (Test-Path -LiteralPath $LogFile)) {
        return
    }

    Write-Host ""
    Write-Host "LAST $Lines LOG LINES: $LogFile" -ForegroundColor Yellow
    Write-Host "------------------------------------------------------------"
    Get-Content -LiteralPath $LogFile -Tail $Lines | ForEach-Object {
        Write-Host $_
    }
    Write-Host "------------------------------------------------------------"
}

function Run-Step {
    param(
        [string]$Name,
        [string[]]$Command,
        [string]$LogFile,
        [bool]$Critical = $true
    )

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "STEP: $Name"
    Write-Host "CMD : $($Command -join ' ')"
    Write-Host "LOG : $LogFile"
    Write-Host "============================================================"

    $logPath = Split-Path -Parent $LogFile
    if ($logPath) {
        New-Item -ItemType Directory -Force -Path $logPath | Out-Null
    }

    $entry = [ordered]@{
        name = $Name
        command = ($Command -join " ")
        log = $LogFile
        exit_code = $null
        critical = [bool]$Critical
        started_at = (Get-Date).ToUniversalTime().ToString("o")
        finished_at = ""
        status = "RUNNING"
    }

    $exe = $Command[0]
    $exeArgs = @()
    if ($Command.Count -gt 1) {
        $exeArgs = $Command[1..($Command.Count - 1)]
    }

    $code = 0
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $exe @exeArgs 2>&1 |
            ForEach-Object { "$_" } |
            Tee-Object -FilePath $LogFile |
            Out-Null
        $code = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    } catch {
        "$_" | Tee-Object -FilePath $LogFile -Append | Out-Null
        $code = 1
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    Remove-AnsiFromFile -Path $LogFile

    $entry.exit_code = [int]$code
    $entry.finished_at = (Get-Date).ToUniversalTime().ToString("o")
    $entry.status = if ($code -eq 0) { "OK" } else { "FAIL" }
    $script:AURUM_MANIFEST.commands = @($script:AURUM_MANIFEST.commands) + @($entry)
    Write-RunManifest

    if ($code -ne 0) {
        Write-Host "FAILED: $Name" -ForegroundColor Red
        if ($Critical) {
            Write-RunManifest -Status "FAIL"
            Show-AurumLogTail -LogFile $LogFile -Lines 100
            throw "FAILED: $Name"
        }
    }

    return [int]$code
}

function Invoke-NativeStep {
    param(
        [string]$Name,
        [string[]]$Command,
        [string]$LogFile,
        [bool]$Critical = $true
    )

    return Run-Step -Name $Name -Command $Command -LogFile $LogFile -Critical $Critical
}

function Invoke-AurumStep {
    param(
        [string]$Python,
        [string]$Name,
        [string[]]$PyArgs,
        [string]$LogFile,
        [bool]$Critical = $true
    )

    return Run-Step `
        -Name $Name `
        -Command (@($Python, "-m", "aurum") + (Get-AurumColorArgs) + $PyArgs) `
        -LogFile $LogFile `
        -Critical $Critical
}

function Invoke-PythonCode {
    param(
        [string]$Python,
        [string]$Name,
        [string]$Code,
        [string]$LogFile,
        [bool]$Critical = $true
    )

    $tempFile = Join-Path $env:TEMP ("aurum_step_" + [guid]::NewGuid().ToString("N") + ".py")
    Set-Content -LiteralPath $tempFile -Value $Code -Encoding UTF8
    try {
        return Run-Step `
            -Name $Name `
            -Command @($Python, $tempFile) `
            -LogFile $LogFile `
            -Critical $Critical
    } finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
}
