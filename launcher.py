"""Local start/stop and official ChatGPT sign-in, used by the Mac launchers."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from roasting.runtime import ROOT, codex_client, database_path

BASE = 'http://127.0.0.1:8740'


def local_request(path, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Roast-Token'] = token
    req = urllib.request.Request(BASE + path, data=b'{}' if token else None, headers=headers)
    # Local tokens and requests must never go through a configured HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=2) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read()).get('error', 'Request rejected')
        except (ValueError, AttributeError):
            message = 'The local server rejected the request.'
        raise RuntimeError(message) from None


def running_studio():
    try:
        info = local_request('/api/bootstrap')
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None
    except (ValueError, RuntimeError):
        raise RuntimeError('Port 8740 is in use by another service. Close that service and try again.') from None
    if not isinstance(info, dict) or info.get('app') != 'roast-studio' or not info.get('token'):
        raise RuntimeError('Port 8740 is occupied by another service or an older Roast Studio. Stop it before launching this version.')
    return info


def chatgpt_ready(exe, env):
    result = subprocess.run([exe, 'login', 'status'], capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            timeout=15, env=env)
    return result.returncode == 0 and 'logged in using chatgpt' in (result.stdout + result.stderr).lower()


def connect_chatgpt():
    exe, env = codex_client()
    if not exe:
        print('ChatGPT is optional. To connect later, double-click Connect ChatGPT.command.')
        return False
    try:
        if chatgpt_ready(exe, env):
            print('ChatGPT is connected. Astra uses your account\'s available Codex usage.')
            return True
        print('Sign in with ChatGPT in the browser that opens. No API key is needed.')
        print('Your login is stored by Codex on this Mac, never in the project or roasting database.')
        # Force the official subscription flow; do not change the user's config file.
        result = subprocess.run([exe, '-c', 'forced_login_method="chatgpt"', 'login'], env=env)
        if result.returncode == 0 and chatgpt_ready(exe, env):
            print('ChatGPT connected. In the app, Settings > Check sign-in refreshes the status.')
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    print('Sign-in was not completed. You can use the app without AI and connect later.')
    return False


def start():
    current = running_studio()
    if current:
        if Path(current['database']).resolve() != database_path().resolve():
            print('An existing Roast Studio is using a different database. Opening that session; no second recorder was started.')
        webbrowser.open(BASE)
        return
    connect_chatgpt()
    folder = database_path().parent
    folder.mkdir(parents=True, exist_ok=True)
    log_path = folder / 'server.log'
    with log_path.open('ab') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'run.py'), '--database', str(database_path())],
                                   cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
    for _ in range(50):
        if process.poll() is not None:
            raise RuntimeError(f'Roast Studio could not start. See {log_path}')
        if running_studio():
            if sys.platform == 'darwin' and shutil.which('caffeinate'):
                # Prevent idle system sleep while the recorder runs; exits with its PID.
                subprocess.Popen(['caffeinate', '-i', '-w', str(process.pid)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            webbrowser.open(BASE)
            print(f'Roast Studio is open. Your data: {database_path()}')
            print('You can close this Terminal window. Use Stop Roasting.command to stop the app.')
            return
        time.sleep(.2)
    raise RuntimeError(f'Startup took too long. Check {log_path}; do not start another copy while troubleshooting.')


def stop():
    current = running_studio()
    if not current:
        print('Roast Studio is already stopped.')
        return
    # The server refuses this request while a roast needs to be finished/saved.
    local_request('/api/shutdown', current['token'])
    print('Roast Studio is stopping. Your saved data stays on this computer.')


def main():
    parser = argparse.ArgumentParser(description='Roast Studio launcher')
    parser.add_argument('action', choices=['start', 'stop', 'login'])
    args = parser.parse_args()
    try:
        if args.action == 'start':
            start()
        elif args.action == 'stop':
            stop()
        else:
            return 0 if connect_chatgpt() else 1
    except (RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
