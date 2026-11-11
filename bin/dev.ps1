$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
python -m gazette.cli --source $(if ($env:GAZETTE_SOURCE) { $env:GAZETTE_SOURCE } else { "Ouest-France" }) --output (Join-Path $PSScriptRoot "..\data\items.jsonl")
