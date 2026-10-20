$ErrorActionPreference = "Stop"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
python -m gazette.cli --source "Le Monde" --output (Join-Path $PSScriptRoot "..\data\items.jsonl")
