#!/usr/bin/env python3
"""Report Python dependencies and optional OMNeT++/INET command availability."""
import argparse
import importlib.metadata
import shutil
import sys

REQUIRED = ("networkx", "numpy", "pandas", "scikit-learn", "joblib", "streamlit", "plotly", "pytest")
SIM_COMMANDS = ("opp_run", "inet")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-only", action="store_true", help="check only Python runtime and dependencies")
    args = parser.parse_args()
    failed = False
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info[:2] != (3, 11):
        print("FAIL: project dependency pins target Python 3.11")
        failed = True
    for package in REQUIRED:
        try:
            print(f"OK: {package}=={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            print(f"MISSING: {package}")
            failed = True
    if not args.python_only:
        for command in SIM_COMMANDS:
            found = shutil.which(command)
            print(f"{'OK' if found else 'UNAVAILABLE'}: {command}{' -> ' + found if found else ''}")
        for name in ("OMNETPP_ROOT", "INET_ROOT"):
            print(f"{'OK' if __import__('os').environ.get(name) else 'UNAVAILABLE'}: {name}")
        print("INET availability is reported separately; Python checks do not validate a simulation build.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
