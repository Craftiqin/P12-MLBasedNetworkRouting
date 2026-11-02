"""Generate a platform-local OMNeT++ Makefile for the ML routing project."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    inet_root = os.environ.get("INET_ROOT")
    if not inet_root:
        raise SystemExit("INET_ROOT missing; activate OMNeT++ and INET setenv first")
    inet_root_path = Path(inet_root)
    if not (inet_root_path / "src").is_dir():
        raise SystemExit(f"INET_ROOT does not contain src/: {inet_root_path}")
    library_names = ("libINET.so", "libINET.dylib", "libINET.dll", "INET.dll",
                     "INET.lib", "libINET.a", "libINET.dll.a")
    libraries = [path for name in library_names for path in (inet_root_path / "out").rglob(name)]
    if not libraries:
        raise SystemExit("No built INET library found under INET_ROOT/out; build INET first")
    libraries.sort(key=lambda path: ("release" not in str(path).lower(), str(path)))
    library_dir = libraries[0].parent
    opp_makemake = shutil.which("opp_makemake")
    if not opp_makemake:
        raise SystemExit("opp_makemake not found; source the OMNeT++ setenv script")
    command = [opp_makemake, "--deep", "--force", "-s", "-o", "mesh", "-O", "out",
               f"-I{inet_root_path / 'src'}", f"-L{library_dir}", "-lINET"]
    print("Generating local Makefile:", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True, shell=(os.name == "nt"))
    make = shutil.which("make")
    if not make:
        raise SystemExit("make not found; use OMNeT++'s configured shell")
    subprocess.run([make, "MODE=release", "-j1"], cwd=ROOT, check=True, shell=(os.name == "nt"))


if __name__ == "__main__":
    main()
