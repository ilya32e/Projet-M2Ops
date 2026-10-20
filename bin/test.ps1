$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
python -m unittest discover -s (Join-Path $PSScriptRoot "..\tests") -v
