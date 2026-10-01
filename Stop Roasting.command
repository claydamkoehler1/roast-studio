#!/bin/bash
source "$(cd "$(dirname "$0")" && pwd)/scripts/macos.sh"
roast_python
"$ROAST_PYTHON" launcher.py stop
