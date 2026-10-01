"""Platform paths and discovery; never reads or copies account credentials."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Roast Studio'
    return ROOT / 'data'


def database_path():
    override = os.environ.get('ROAST_DB')
    return Path(override).expanduser().resolve() if override else data_directory() / 'roasting.sqlite3'


def codex_client():
    env = dict(os.environ)
    home = Path.home()
    if sys.platform == 'win32':
        env.setdefault('USERPROFILE', str(home))
    # Keep Codex's own login location, including OS-keychain authentication.
    # Only the official CLI reads credentials; this app never copies auth.json.
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL',
                'OPENAI_ORG_ID', 'OPENAI_ORGANIZATION', 'CODEX_ACCESS_TOKEN'):
        env.pop(key, None)
    bundled = ROOT / '.runtime' / 'bin' / 'codex'
    if sys.platform == 'darwin' and bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled), env
    exe = shutil.which('codex')
    if exe:
        return exe, env
    if sys.platform == 'win32':
        base = Path(env.get('LOCALAPPDATA') or home / 'AppData' / 'Local') / 'OpenAI' / 'Codex' / 'bin'
        choices = sorted(base.glob('*/codex.exe'), key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        # Finder-launched scripts may not inherit the interactive shell's PATH.
        choices = [Path('/opt/homebrew/bin/codex'), Path('/usr/local/bin/codex'),
                   home / '.local' / 'bin' / 'codex', home / '.npm-global' / 'bin' / 'codex']
    for path in choices:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path), env
    return None, env
