$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$venvDir = Join-Path $scriptDir '.venv'

function Find-Python {
    $candidates = @('py','python')
    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            return $candidate
        }
    }
    throw 'Python was not found. Install Python 3.10+ from https://www.python.org/downloads/ and try again.'
}

$pythonCmd = Find-Python

if (-not (Test-Path (Join-Path $venvDir 'Scripts/python.exe'))) {
    Write-Host 'Creating virtual environment...'
    & $pythonCmd -m venv $venvDir
}

$pythonExe = Join-Path $venvDir 'Scripts/python.exe'

Write-Host 'Installing requirements...'
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt

Write-Host ''
Write-Host 'Starting Parcel Label Extractor...'
Write-Host 'Open your browser at: http://localhost:3000'
Write-Host 'Press Ctrl+C in this window to stop the app.'
Write-Host ''
Start-Process 'http://localhost:3000'
& $pythonExe -m uvicorn main:app --host 0.0.0.0 --port 3000
