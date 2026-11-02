$ErrorActionPreference = 'Stop'
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python launcher py missing; install Python 3.11 first.' }
py -3.11 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe tools\validation\validate_environment.py --python-only
if ($LASTEXITCODE -ne 0) { throw 'Environment validation failed.' }
