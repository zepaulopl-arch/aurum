$ErrorActionPreference = "Stop"

function Test-PyMercatorPython {
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

function Resolve-PyMercatorPython {
    param([string]$Requested = "")

    $candidates = New-Object System.Collections.Generic.List[string]
    if ($Requested) {
        $candidates.Add($Requested)
    }
    if ($env:PYMERCATOR_PYTHON) {
        $candidates.Add($env:PYMERCATOR_PYTHON)
    }
    if ($env:USERPROFILE) {
        $candidates.Add((Join-Path $env:USERPROFILE "anaconda3\python.exe"))
    }
    $candidates.Add("python")
    $candidates.Add("py")

    foreach ($candidate in $candidates) {
        if (-not $candidate) {
            continue
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

        if ($resolved -and (Test-PyMercatorPython -Command $resolved)) {
            return $resolved
        }
    }

    throw "Python not found. Use -Python C:\path\python.exe or set PYMERCATOR_PYTHON."
}

function Initialize-PyMercatorScript {
    param([string]$RequestedPython = "")

    $repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
    Set-Location $repoRoot
    return Resolve-PyMercatorPython -Requested $RequestedPython
}

function New-PyMercatorLogDir {
    param([string]$Prefix)

    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $logDir = Join-Path "runtime" "${Prefix}_$ts"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    return $logDir
}

function Invoke-NativeStep {
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

    $exe = $Command[0]
    $exeArgs = @()
    if ($Command.Count -gt 1) {
        $exeArgs = $Command[1..($Command.Count - 1)]
    }

    $code = 0
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $exe @exeArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $LogFile
        $code = $LASTEXITCODE
    } catch {
        "$_" | Tee-Object -FilePath $LogFile -Append
        $code = 1
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($code -ne 0) {
        Write-Host "FAILED: $Name" -ForegroundColor Red
        if ($Critical) {
            throw "FAILED: $Name"
        }
    }
}

function Invoke-PyMercatorStep {
    param(
        [string]$Python,
        [string]$Name,
        [string[]]$PyArgs,
        [string]$LogFile,
        [bool]$Critical = $true
    )

    Invoke-NativeStep `
        -Name $Name `
        -Command (@($Python, "-m", "pymercator") + $PyArgs) `
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

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "STEP: $Name"
    Write-Host "CMD : $Python -"
    Write-Host "LOG : $LogFile"
    Write-Host "============================================================"

    $code = 0
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $Code | & $Python - 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $LogFile
        $code = $LASTEXITCODE
    } catch {
        "$_" | Tee-Object -FilePath $LogFile -Append
        $code = 1
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($code -ne 0) {
        Write-Host "FAILED: $Name" -ForegroundColor Red
        if ($Critical) {
            throw "FAILED: $Name"
        }
    }
}
