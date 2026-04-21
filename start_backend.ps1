param(
    [ValidateSet("auto", "backend", "root")]
    [string]$EnvName = "auto",

    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $BackendDir

$BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$RootPython = Join-Path $RootDir ".venv\Scripts\python.exe"

function Test-BackendPython {
    param([string]$PythonPath)

    if (-not (Test-Path $PythonPath)) {
        return $false
    }

    & $PythonPath -c "import fastapi, uvicorn, sqlalchemy, pymysql, httpx, dotenv" 2>$null
    return $LASTEXITCODE -eq 0
}

if ($EnvName -eq "backend") {
    $Python = $BackendPython
} elseif ($EnvName -eq "root") {
    $Python = $RootPython
} else {
    if (Test-BackendPython $BackendPython) {
        $Python = $BackendPython
    } elseif (Test-BackendPython $RootPython) {
        $Python = $RootPython
    } else {
        throw "No usable virtual environment found. Run '.\.venv\Scripts\python.exe -m pip install -r requirements.txt' in ai-interview-backend, or install dependencies in the root .venv."
    }
}

if (-not (Test-Path $Python)) {
    throw "Python executable not found: $Python"
}

if (-not (Test-BackendPython $Python)) {
    throw "Selected environment is missing dependencies: $Python. Run '$Python -m pip install -r requirements.txt'."
}

Push-Location $BackendDir
try {
    $Args = @("-m", "uvicorn", "main:app", "--host", $HostAddress, "--port", "$Port")
    if ($Reload) {
        $Args += "--reload"
    }
    Write-Host "Using Python: $Python"
    & $Python @Args
} finally {
    Pop-Location
}
