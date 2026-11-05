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

### Refresh GitHub checkout in opp_env WSL2

Open the `opp_env` WSL distribution from PowerShell:

```powershell
wsl -d opp_env --cd ~
```

Inside WSL, update the repository and enter the INET environment:

```sh
mkdir -p ~/src
git clone https://github.com/Craftiqin/P12-MLBasedNetworkRouting.git ~/src/P12-MLBasedNetworkRouting
cd ~/src/P12-MLBasedNetworkRouting
git pull --ff-only origin main
opp_env shell inet-4.7.0
```

Then, inside the opp_env shell:

```sh
cd ~/src/P12-MLBasedNetworkRouting/simulation/inet/ml-routing
python3 -m venv .ml-venv
source .ml-venv/bin/activate
python -m pip install -r ml/requirements.txt
python tools/configure_build.py
python -m unittest discover -s tests -v
python tools/run_ml_experiment.py --config MLRoutePreference --seed-set 17
python tools/run_aodv_experiment.py --ui Cmdenv --config Normal --seed-set 17
```

`git clone` is for first setup; on later updates, use `git pull --ff-only origin main` in the existing checkout. Current upstream opp_env metadata pairs INET 4.7.0 with OMNeT++ 6.4.x; Mac verification used 6.5.0 + 4.7.0, so this opp_env route does not reproduce that exact version pair. Windows/WSL build and run remain unverified. See the [opp_env Windows/WSL2 install guide](https://github.com/omnetpp/opp_env/blob/main/INSTALL.md) and [package compatibility metadata](https://github.com/omnetpp/opp_env/blob/main/opp_env/database/inet.py).
