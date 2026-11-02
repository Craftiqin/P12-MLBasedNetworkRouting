# Installation overview

Install Python and OMNeT++/INET separately. Python ML and graph simulations do not depend on OMNeT++. INET packet simulation does not use the Python model. Use Python 3.11 and the exact Python pins in `requirements.txt`.

## Platform paths

- macOS: [platform guide](MACOS.md); Apple Silicon and Intel supported by OMNeT++ through different upstream archives. `opp_env` requires Nix; Apple Silicon needs OMNeT++ 6.x.
- Windows: [platform guide](WINDOWS.md); use Windows 11 + WSL2 (recommended upstream route) or OMNeT++ MinGW toolchain only if manually verified. INET guide notes Windows commands need OMNeT++'s MinGW environment.
- Linux: [platform guide](LINUX.md); use a supported 64-bit distro, compiler/build packages, Qt for Qtenv.

These are documented procedures, not test claims. See current [OMNeT++ install guide](https://docs.omnetpp.org/installguide/) and [opp_env install guide](https://github.com/omnetpp/opp_env/blob/main/INSTALL.md) before installing because platform support changes.

## Reproducible version choice

INET source was authored against the OMNeT++/INET compatibility pair recorded in [simulation setup](SIMULATION_SETUP.md). Prefer `opp_env` so it resolves and builds compatible dependencies together. Do not install INET's `full` feature set for this project. Build artifacts and results stay outside committed source.
