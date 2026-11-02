# OMNeT++ and INET setup

## Selected versions

Use OMNeT++ **6.4.0** with INET **4.7.0**. INET’s current compatibility matrix lists this pair; use `opp_env` to install dependencies together. Recheck the [official matrix](https://inet.omnetpp.org/inet/Download.html) before setup. If unavailable, use the upstream compatibility matrix and update this document plus test the project before changing versions. No OMNeT++ or INET installation was available on the authoring host, so build/run commands remain unverified.

INET is an external source dependency; this repository contains only its NED/INI scenario and exporter. It does not vendor OMNeT++ or INET.

## Install through opp_env

Install Nix and `opp_env` using the upstream guide, create an external workspace, then install the paired packages:

```sh
mkdir -p "$HOME/opp-workspace/p12"
cd "$HOME/opp-workspace/p12"
opp_env init
opp_env install inet-4.7.0
opp_env shell inet-4.7.0
```

`opp_env` sets tool paths only inside its shell. Confirm `opp_run -h`, `inet -h`, `OMNETPP_ROOT`, and `INET_ROOT`. Keep this workspace outside the repository. Use only in a shell where `inet-4.7.0` is installed.

## Build/run prerequisites

The project is NED/INI/XML only; no custom C++ or project Makefile. INET itself must be compiled by `opp_env` (or manually as in [INET installation guide](https://github.com/inet-framework/inet/blob/master/INSTALL.md)). Run commands in [simulation README](../../simulation/README.md). `-n` includes project NED path and `$INET_ROOT/src`; output files go to `simulation/inet/results/`.

## Qtenv

Qtenv requires OMNeT++ GUI/Qt support and a graphical session. Linux headless hosts may need X11/Wayland Qt libraries. `opp_env shell` plus `inet -u Qtenv ...` launches UI; GUI behavior has not been tested here.
