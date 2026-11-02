#!/bin/sh
set -eu
case "$(uname -s)" in
  Darwin) exec tools/scripts/setup_macos.sh ;;
  Linux) exec tools/scripts/setup_linux.sh ;;
  *) echo "Unsupported shell OS: $(uname -s). Use setup_windows.ps1 on Windows." >&2; exit 1 ;;
esac
