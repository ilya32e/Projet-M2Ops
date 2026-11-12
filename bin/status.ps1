$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
python -m gazette.status --db (Join-Path $PSScriptRoot "..\data\gazette.sqlite3")
exit $LASTEXITCODE
