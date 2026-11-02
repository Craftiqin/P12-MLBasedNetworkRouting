# macOS installation

## Python

Install Python 3.11 (for example from python.org or a managed package manager), then follow [ML setup](ML_SETUP.md) using `python3.11`. This path is separate from OMNeT++.

## OMNeT++ and INET

Current OMNeT++ docs provide distinct macOS archives: Apple Silicon uses `aarch64`; Intel uses `x86_64`. OMNeT++ requires Apple's command line developer tools; Qt enables Qtenv. Use upstream current install steps for the selected release. `opp_env` supports macOS through Nix; Apple Silicon requires OMNeT++ 6.x. Version selection: [simulation setup](SIMULATION_SETUP.md).

```sh
xcode-select --install
python3 -m pip install --user opp-env
# Follow Nix upstream installation; open a new Terminal after setup.
mkdir -p "$HOME/opp-workspace/p12"
cd "$HOME/opp-workspace/p12"
opp_env init
opp_env install inet-4.7.0
opp_env shell inet-4.7.0
```

Do not treat this as tested here. Validate `opp_run -h`, `inet -h`, `OMNETPP_ROOT`, `INET_ROOT`; compile/run steps in [simulation README](../../simulation/README.md). Keep Nix installation outside the project. Intel and Apple Silicon binary archives are architecture-specific; do not share compiled artifacts across architectures.
