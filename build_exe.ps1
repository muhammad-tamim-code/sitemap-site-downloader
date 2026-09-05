$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot '.venv'

if (-not (Test-Path -LiteralPath $venvPath)) {
    py -3 -m venv $venvPath
}

$python = Join-Path $venvPath 'Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -e $projectRoot -r (Join-Path $projectRoot 'requirements-dev.txt')
& $python -m PyInstaller --noconfirm --clean --onefile --name sitemap-site-downloader --paths (Join-Path $projectRoot 'src') (Join-Path $projectRoot 'run.py')

Write-Output "Executable created under $projectRoot\dist"
