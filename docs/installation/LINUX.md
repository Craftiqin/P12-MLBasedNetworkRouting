# Linux installation

Use a supported 64-bit Linux distribution, current C++ compiler/build tools, Python 3.11, and Qt/GUI libraries if Qtenv is required. For Ubuntu/Debian, the upstream OMNeT++ guide lists these core packages (package availability may vary by release):

```sh
sudo apt update
sudo apt install -y make diffutils pkg-config ccache clang lld gdb lldb bison flex perl sed gawk python3 python3-pip python3-venv python3-dev libxml2-dev zlib1g-dev doxygen graphviz xdg-utils libdw-dev
```

For Qtenv/IDE GUI support, add `qt6-base-dev qt6-base-dev-tools qmake6 libqt6svg6 qt6-wayland libwebkit2gtk-4.1-0`; optional 3D support needs `libopenscenegraph-dev`. Other distributions need their matching compiler/build libraries and Qt packages; use OMNeT++ official distro-specific list, not the Debian package names above. `opp_env` + Nix can resolve compatible OMNeT++/INET and dependencies.

Install Nix and `opp_env` from upstream docs, then:

```sh
python3 -m pip install --user opp-env
mkdir -p "$HOME/opp-workspace/p12"
cd "$HOME/opp-workspace/p12"
opp_env init
opp_env install inet-4.7.0
opp_env shell inet-4.7.0
```

Then follow [simulation setup](SIMULATION_SETUP.md). `opp_env` packages are available only inside its shell. For direct manual install, first install/build OMNeT++, extract matching INET source, run INET `setenv`, install INET's Python requirements, and build INET per [INET install guide](https://github.com/inet-framework/inet/blob/master/INSTALL.md).

Python setup and experiment commands: [ML setup](ML_SETUP.md). This project has not been tested on Linux; distro package names and GUI support vary.
