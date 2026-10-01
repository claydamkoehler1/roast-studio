#!/bin/bash
# Self-contained macOS bootstrap. Only built-in macOS tools are needed initially.
set -Eeuo pipefail
umask 077

roast_error() {
    printf '\nSetup did not finish. Check your Internet connection and the message above, then retry.\n'
    if [ -t 0 ]; then read -r -p 'Press Return to close. ' _roast_reply; fi
}
trap roast_error ERR

if [ "$(/usr/bin/uname -s)" != "Darwin" ]; then
    printf 'These launchers are for macOS. On Windows, use Start Roasting.cmd.\n' >&2
    exit 1
fi

ROAST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROAST_ROOT"
ROAST_RUNTIME="$ROAST_ROOT/.runtime"
ROAST_PYTHON="$ROAST_ROOT/.venv/bin/python"
ROAST_UV="$ROAST_RUNTIME/bin/uv"
export PATH="$ROAST_RUNTIME/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export UV_PYTHON_INSTALL_DIR="$ROAST_RUNTIME/python"
export UV_PYTHON_BIN_DIR="$ROAST_RUNTIME/bin"
export UV_CACHE_DIR="$ROAST_RUNTIME/cache"
export UV_PYTHON_CACHE_DIR="$ROAST_RUNTIME/cache/python"
export UV_NO_CONFIG=1

case "$(/usr/bin/uname -m)" in
    arm64) ROAST_ARCH=aarch64 ;;
    x86_64) ROAST_ARCH=x86_64 ;;
    *) printf 'Unsupported Mac architecture.\n' >&2; exit 1 ;;
esac
# Prefer native Apple Silicon even when launched from a translated Terminal.
if [ "$(/usr/sbin/sysctl -in sysctl.proc_translated 2>/dev/null || true)" = 1 ]; then
    ROAST_ARCH=aarch64
fi

# Pinned official release assets. A checksum mismatch stops installation.
ROAST_UV_VERSION=0.12.21
ROAST_CODEX_VERSION=0.160.0
if [ "$ROAST_ARCH" = aarch64 ]; then
    ROAST_UV_SHA=b88bda573e566ef9bced66b155fe0408626fbbc053aee1c30ba686f0728c9447
    ROAST_CODEX_SHA=07c3c7ca376a8f791115342f53138dda37e97cfa29b8125d0652d93784894b5d
else
    ROAST_UV_SHA=2b336763b396ec6afa20c5a8b083538ca7402445b868311979d740a4344c17d8
    ROAST_CODEX_SHA=a50c10606e4e81b8dd2f7b6bab635595aabc773c84cf2071773fbaf067825fbf
fi

roast_download_binary() {
    local name="$1" version="$2" url="$3" sha="$4" member="$5"
    local binary="$ROAST_RUNTIME/bin/$name" archive partial
    if [ -x "$binary" ] && "$binary" --version 2>/dev/null | /usr/bin/grep -Fq "$version"; then
        return
    fi
    mkdir -p "$ROAST_RUNTIME/bin"
    archive="$(/usr/bin/mktemp "$ROAST_RUNTIME/download.XXXXXX")"
    partial="$(/usr/bin/mktemp "$ROAST_RUNTIME/bin/$name.XXXXXX")"
    printf '\nDownloading %s %s for your Mac…\n' "$name" "$version"
    /usr/bin/curl --proto '=https' --tlsv1.2 --fail --location --retry 2 --connect-timeout 20 --max-time 300 "$url" -o "$archive"
    printf '%s  %s\n' "$sha" "$archive" | /usr/bin/shasum -a 256 -c -
    # Extract only the named executable, never arbitrary archive paths.
    /usr/bin/tar -xOf "$archive" "$member" > "$partial"
    chmod 700 "$partial"
    "$partial" --version
    mv -f "$partial" "$binary"
    rm -f "$archive"
}

roast_setup() {
    roast_download_binary uv "$ROAST_UV_VERSION" \
        "https://github.com/astral-sh/uv/releases/download/$ROAST_UV_VERSION/uv-$ROAST_ARCH-apple-darwin.tar.gz" \
        "$ROAST_UV_SHA" "uv-$ROAST_ARCH-apple-darwin/uv"
    # Always use a private managed Python, regardless of system installations.
    if ! "$ROAST_PYTHON" -c 'import sys; from pathlib import Path; assert sys.version_info[:2] == (3,12); assert Path(sys.base_prefix).resolve().is_relative_to(Path(".runtime/python").resolve())' >/dev/null 2>&1; then
        "$ROAST_UV" python install 3.12 --no-bin
        if [ -e "$ROAST_ROOT/.venv" ] || [ -L "$ROAST_ROOT/.venv" ]; then
            # Preserve an earlier system-based environment; never delete it or user data.
            local backup
            backup="$(/usr/bin/mktemp -d "$ROAST_RUNTIME/previous-venv.XXXXXX")"
            mv "$ROAST_ROOT/.venv" "$backup/environment"
            printf 'Previous Python environment preserved at %s\n' "$backup/environment"
        fi
        "$ROAST_UV" venv --python 3.12 --managed-python "$ROAST_ROOT/.venv"
    fi
    local fingerprint saved
    fingerprint="$("$ROAST_PYTHON" -c 'import hashlib,platform,sys; from pathlib import Path; print(hashlib.sha256(Path("requirements.txt").read_bytes()).hexdigest()+sys.version+sys.base_prefix+platform.machine())')"
    saved="$(cat .venv/roast-requirements 2>/dev/null || true)"
    if [ "$fingerprint" != "$saved" ] || ! "$ROAST_PYTHON" -c 'import usb,libusb_package' >/dev/null 2>&1; then
        printf '\nInstalling USB libraries into the private virtual environment…\n'
        "$ROAST_UV" pip install --python "$ROAST_PYTHON" --only-binary :all: -r requirements.txt
        printf '%s' "$fingerprint" > .venv/roast-requirements
    fi
}

roast_python() {
    # Stopping an existing installation should work without downloads or Internet.
    if ! "$ROAST_PYTHON" -c 'import sys' >/dev/null 2>&1; then
        roast_setup
    fi
}

roast_codex() {
    roast_download_binary codex "$ROAST_CODEX_VERSION" \
        "https://github.com/openai/codex/releases/download/rust-v$ROAST_CODEX_VERSION/codex-$ROAST_ARCH-apple-darwin.tar.gz" \
        "$ROAST_CODEX_SHA" "codex-$ROAST_ARCH-apple-darwin"
}
