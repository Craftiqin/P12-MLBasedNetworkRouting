# Linux installation

Use a supported 64-bit Linux distribution, current C++ compiler/build tools, Python 3.11, and Qt/GUI libraries if Qtenv is required. For Ubuntu/Debian, the upstream OMNeT++ guide lists these core packages (package availability may vary by release):

```sh
sudo apt update
sudo apt install -y make diffutils pkg-config ccache clang lld gdb lldb bison flex perl sed gawk python3 python3-pip python3-venv python3-dev libxml2-dev zlib1g-dev doxygen graphviz xdg-utils libdw-dev
```

For Qtenv/IDE GUI support, add the Qt packages listed by the official OMNeT++ guide; optional 3D support needs OpenSceneGraph development libraries. Other distributions need their matching compiler/build libraries and Qt packages; use OMNeT++ official distro-specific list, not the Debian package names above.

Install OMNeT++ using the official Linux guide, then build INET from source with OMNeT++ environment active using the [INET installation procedure](https://inet.omnetpp.org/Installation.html). The tested local version pair and limits are in [simulation setup](SIMULATION_SETUP.md). Linux build/run is untested for this repository.

Python setup and exact ML packet simulation commands: [ML setup](ML_SETUP.md) and [ML routing README](../../simulation/inet/ml-routing/README.md). This project has not been tested on Linux; distro package names and GUI support vary.
