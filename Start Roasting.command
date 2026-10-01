#!/bin/bash
source "$(cd "$(dirname "$0")" && pwd)/scripts/macos.sh"
roast_setup
roast_codex
"$ROAST_PYTHON" launcher.py start
