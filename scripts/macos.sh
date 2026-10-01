#!/bin/bash
# Shared setup for Finder and Terminal. Compatible with macOS's Bash 3.2.
set -Eeuo pipefail
umask 077
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

roast_error() {
    printf '\nSetup did not finish. Read the message above, then try again.\n'
    if [ -t 0 ]; then read -r -p 'Press Return to close. ' _roast_reply; fi
}
trap roast_error ERR

if [ "$(uname -s)" != "Darwin" ]; then
    printf 'These launchers are for macOS. On Windows, use Start Roasting.cmd.\n' >&2
    exit 1
fi

ROAST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROAST_ROOT"

roast_python() {
    ROAST_PYTHON=''
    for candidate in "$ROAST_ROOT/.venv/bin/python" /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 python3.12 python3; do
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' >/dev/null 2>&1; then
            ROAST_PYTHON="$candidate"
            break
        fi
    done
    if [ -z "$ROAST_PYTHON" ]; then
        if command -v brew >/dev/null 2>&1; then
            printf '\nInstalling Python 3.12 with Homebrew…\n'
            brew install python@3.12
            ROAST_PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
        else
            printf '\nInstall Python 3.12 or newer from https://www.python.org/downloads/macos/\n'
            printf 'Or install Homebrew from https://brew.sh, then run this launcher again.\n'
            return 1
        fi
    fi
}

roast_setup() {
    roast_python
    if [ ! -x "$ROAST_ROOT/.venv/bin/python" ]; then
        "$ROAST_PYTHON" -m venv "$ROAST_ROOT/.venv"
    fi
    ROAST_PYTHON="$ROAST_ROOT/.venv/bin/python"
    # Install once, then only when requirements or interpreter architecture change.
    local fingerprint saved
    fingerprint="$("$ROAST_PYTHON" -c 'import hashlib,platform,sys; from pathlib import Path; print(hashlib.sha256(Path("requirements.txt").read_bytes()).hexdigest()+sys.version+platform.machine())')"
    saved="$(cat .venv/roast-requirements 2>/dev/null || true)"
    if [ "$fingerprint" != "$saved" ]; then
        printf '\nInstalling Roast Studio USB support into its private Python environment…\n'
        "$ROAST_PYTHON" -m pip install -r requirements.txt
        printf '%s' "$fingerprint" > .venv/roast-requirements
    fi
}

roast_codex() {
    if "$ROAST_PYTHON" -c 'from roasting.runtime import codex_client; import sys; sys.exit(0 if codex_client()[0] else 1)'; then
        return
    fi
    if command -v brew >/dev/null 2>&1; then
        printf '\nInstalling the official Codex CLI for ChatGPT sign-in…\n'
        if ! brew install --cask codex; then
            printf 'Codex installation failed. You can retry with Connect ChatGPT.command.\n'
        fi
    else
        printf '\nTo enable AI, install Homebrew from https://brew.sh and run Connect ChatGPT.command.\n'
        printf 'Alternatively, with Node.js installed: npm install -g @openai/codex\n'
        printf 'Roast Studio can still open without AI.\n'
    fi
}
