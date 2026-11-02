$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command inet -ErrorAction SilentlyContinue)) { throw 'inet missing. Use configured OMNeT++/INET environment; Windows opp_env route runs in WSL2.' }
if (-not $env:INET_ROOT) { throw 'INET_ROOT missing.' }
Set-Location (Join-Path $root 'simulation/inet')
New-Item -ItemType Directory -Force -Path results | Out-Null
$config = if ($args.Count -ge 1) { $args[0] } else { 'Normal' }
$run = if ($args.Count -ge 2) { $args[1] } else { '0' }
inet -u Cmdenv -n "src;$env:INET_ROOT/src" -f simulations/mesh/omnetpp.ini -c $config -r $run
if ($LASTEXITCODE -ne 0) { throw 'Simulation failed; inspect tool output and results.' }
