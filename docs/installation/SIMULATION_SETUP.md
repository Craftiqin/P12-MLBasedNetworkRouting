# OMNeT++ and INET setup

## Versions and validation state

ML packet routing is locally built and exercised with OMNeT++ **6.5.0** and INET **4.7.0** on macOS 27 / Apple Silicon M1. The INET published compatibility table names OMNeT++ 6.4 for INET 4.7.0; the 6.5.0 combination here is a locally verified build, not a claim that INET lists it as a supported pair. Windows and Linux builds remain untested.

Use the platform-specific [macOS](MACOS.md), [Linux](LINUX.md), or [Windows](WINDOWS.md) instructions. This repository does not vendor OMNeT++ or INET. Keep generated build files local. The AODV baseline and ML forwarder have distinct commands and configurations; see [simulation README](../../simulation/README.md) and [ML routing README](../../simulation/inet/ml-routing/README.md).

## Native install workflow

Install OMNeT++ from its official platform archive and build/install INET using the version-specific upstream procedure. The macOS host used the official Apple Silicon OMNeT++ 6.5.0 distribution and INET 4.7.0 source. Avoid `opp_env` for this project setup: the prior Apple Silicon Nix dependency build failed in QtWebEngine. Do not reuse artifacts from another OS or CPU architecture.

Check environment before building:

```sh
opp_run -h
inet -h
printf 'OMNETPP_ROOT=%s\nINET_ROOT=%s\n' "$OMNETPP_ROOT" "$INET_ROOT"
```

Build the custom ML project using [its setup guide](../../simulation/inet/ml-routing/README.md). Qtenv requires a graphical desktop and Qt support. Launch success alone does not validate rendered positions, route overlays, or animation.
