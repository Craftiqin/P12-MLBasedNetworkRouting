# Installation overview

Install project Python dependencies separately from OMNeT++/INET. Python graph simulation does not depend on OMNeT++; packet-level ML routing uses Python for training, analysis, and experiment orchestration plus C++ inference inside INET. Use Python 3.11 and exact pins in the component requirements files.

## Platform paths

- macOS: [platform guide](MACOS.md); Apple Silicon and Intel use different upstream archives. This project uses the native OMNeT++/INET workflow.
- Windows: [platform guide](WINDOWS.md); use Windows 11 + WSL2 (recommended upstream route) or OMNeT++ MinGW toolchain only if manually verified. INET guide notes Windows commands need OMNeT++'s MinGW environment.
- Linux: [platform guide](LINUX.md); use a supported 64-bit distro, compiler/build packages, Qt for Qtenv.

Installation procedures are platform-specific. Only macOS Apple Silicon was built and exercised for this ML packet simulation. Windows and Linux are documented routes, not test claims. See current [OMNeT++ install guide](https://docs.omnetpp.org/installguide/) before installing because platform support changes.

## Reproducible version choice

The ML packet simulation uses OMNeT++ 6.5.0 with INET 4.7.0, locally verified on macOS Apple Silicon. INET's published matrix lists OMNeT++ 6.4 with INET 4.7.0. See [simulation setup](SIMULATION_SETUP.md) for this distinction and platform status. Build artifacts and raw run outputs should stay outside committed source unless deliberately archived.
