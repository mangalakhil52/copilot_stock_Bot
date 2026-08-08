$scriptPath = Join-Path $PSScriptRoot 'main.py'
$configPath = Join-Path $PSScriptRoot 'config.yaml'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}

if (-not $python) {
    Write-Error 'Python is not available on PATH. Install Python 3.10+ and add it to PATH.'
    exit 1
}

& $python $scriptPath run --config $configPath
