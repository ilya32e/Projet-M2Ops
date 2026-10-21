$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
$interval = if ($env:GAZETTE_INTERVAL_SECONDS) { $env:GAZETTE_INTERVAL_SECONDS } else { "1800" }
python -m gazette.collector --interval $interval
