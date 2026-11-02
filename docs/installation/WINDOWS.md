# Windows installation

## Recommended simulation environment: Windows 11 + WSL2

Upstream `opp_env` does not run natively on Windows; OMNeT++ documents WSL2 as recommended. Enable WSL2, install the upstream `opp_env` WSL image or an Ubuntu WSL distribution, then use Linux commands from that shell. Keep the repository inside the WSL filesystem for builds (for example `~/src/P12-MLBasedNetworkRouting`), not a Windows-mounted folder when performance matters. Qtenv requires WSLg/GUI support.

From elevated PowerShell, if WSL is not installed:

```powershell
wsl --install
```

Then use WSL distro terminal and follow [Linux guide](LINUX.md) and [simulation setup](SIMULATION_SETUP.md). Current official OMNeT++ guide also documents a native Windows 11 MinGW64 toolchain; INET says to open the `mingwenv.cmd` shell before building/running. Native Windows and WSL project builds are untested; no PowerShell experiment wrapper is supplied. ML routing package commands are in [ML routing README](../../simulation/inet/ml-routing/README.md).

## Python on Windows

Install Python 3.11 from python.org with launcher `py`, then use PowerShell commands in [ML setup](ML_SETUP.md):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools\validation\validate_environment.py --python-only
```

Command Prompt users: use `.venv\Scripts\activate.bat` and backslash paths. ML/Python works independently of OMNeT++.

## ML packet simulation

Unverified on Windows. For WSL2, use the Linux setup, then follow the [ML routing package guide](../../simulation/inet/ml-routing/README.md) from the WSL project checkout. Native MinGW users must enter OMNeT++'s `mingwenv.cmd` shell before building; install the package's Python dependencies from `simulation/inet/ml-routing/ml/requirements.txt`, then follow its build and experiment steps. Command names, GUI launch, and experiment behavior have not been validated on Windows.
