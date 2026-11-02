# macOS installation

## Python

Install Python 3.11 (for example from python.org or a managed package manager), then follow [ML setup](ML_SETUP.md) using `python3.11`. This path is separate from OMNeT++.

## OMNeT++ and INET

Current OMNeT++ docs provide distinct macOS archives: Apple Silicon uses `aarch64`; Intel uses `x86_64`. OMNeT++ requires Apple's command line developer tools; Qt enables Qtenv. Follow the [official macOS install guide](https://docs.omnetpp.org/installguide/ch-macos/). This project was locally built on M1/macOS 27 with OMNeT++ 6.5.0 and INET 4.7.0. Version caveat: [simulation setup](SIMULATION_SETUP.md).

```sh
xcode-select --install
# Download and extract the OMNeT++ macOS aarch64 archive using the official guide.
# Open a new terminal, then source the extracted distribution's setenv script.
source "$HOME/omnetpp-6.5.0/setenv" -q
```

Build INET 4.7.0 using its [official installation guide](https://inet.omnetpp.org/Installation.html), with the OMNeT++ environment active. Then follow [ML routing setup](../../simulation/inet/ml-routing/README.md). The previous Nix/QtWebEngine route failed on this Apple Silicon host and is not the tested installation path. Intel and Apple Silicon artifacts are architecture-specific; never share compiled outputs across architectures.
