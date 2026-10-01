import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import launcher
from roasting import runtime
from roasting.instance import InstanceLock
from roasting.server import App, handler_for


class PlatformTest(unittest.TestCase):
    def test_project_codex_takes_precedence_on_mac(self):
        bundled = runtime.ROOT / '.runtime' / 'bin' / 'codex'
        with patch('roasting.runtime.sys.platform', 'darwin'), \
             patch.object(Path, 'is_file', lambda p: p == bundled), \
             patch('roasting.runtime.os.access', return_value=True), \
             patch('roasting.runtime.shutil.which', return_value='/global/codex'):
            self.assertEqual(runtime.codex_client()[0], str(bundled))

    def test_mac_database_is_outside_checkout(self):
        home = Path.home()
        with patch('roasting.runtime.sys.platform', 'darwin'), patch.dict(os.environ, {}, clear=True), \
             patch('roasting.runtime.Path.home', return_value=home):
            self.assertEqual(runtime.database_path(), home / 'Library/Application Support/Roast Studio/roasting.sqlite3')

    def test_database_override_and_windows_default(self):
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder) / 'custom.sqlite3')
            with patch.dict(os.environ, {'ROAST_DB': target}):
                self.assertEqual(runtime.database_path(), Path(target).resolve())
        with patch('roasting.runtime.sys.platform', 'win32'), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runtime.database_path(), runtime.ROOT / 'data/roasting.sqlite3')

    def test_mac_finder_discovers_both_homebrew_prefixes(self):
        for expected in ('/opt/homebrew/bin/codex', '/usr/local/bin/codex'):
            with self.subTest(expected=expected), patch('roasting.runtime.sys.platform', 'darwin'), \
                 patch('roasting.runtime.shutil.which', return_value=None), \
                 patch.object(Path, 'is_file', lambda p: str(p).replace('\\', '/') == expected), \
                 patch('roasting.runtime.os.access', return_value=True):
                self.assertEqual(runtime.codex_client()[0].replace('\\', '/'), expected)

    def test_credentials_are_not_copied_and_api_environment_is_removed(self):
        with patch.dict(os.environ, {'CODEX_HOME': '/existing-codex-home', 'OPENAI_API_KEY': 'dummy', 'CODEX_ACCESS_TOKEN': 'dummy'}), \
             patch('roasting.runtime.shutil.which', return_value='codex'), \
             patch.object(Path, 'read_text', side_effect=AssertionError('Do not read credentials')):
            exe, env = runtime.codex_client()
        self.assertEqual(exe, 'codex')
        self.assertEqual(env['CODEX_HOME'], '/existing-codex-home')
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('CODEX_ACCESS_TOKEN', env)

    def test_lock_excludes_a_second_process(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'locked.sqlite3'
            lock = InstanceLock(database)
            try:
                result = subprocess.run([os.sys.executable, '-c',
                    'from roasting.instance import InstanceLock; import sys; InstanceLock(sys.argv[1])', str(database)],
                    cwd=runtime.ROOT, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'already open', result.stderr)
            finally:
                lock.close()
            InstanceLock(database).close()


class LauncherTest(unittest.TestCase):
    def test_existing_session_does_not_spawn_or_login(self):
        with patch('launcher.running_studio', return_value={'database': str(runtime.database_path())}), \
             patch('launcher.connect_chatgpt') as login, patch('launcher.subprocess.Popen') as spawn, \
             patch('launcher.webbrowser.open') as browser:
            launcher.start()
        login.assert_not_called()
        spawn.assert_not_called()
        browser.assert_called_once_with(launcher.BASE)

    def test_foreign_service_is_not_used_or_stopped(self):
        with patch('launcher.local_request', return_value={'token': 'not-our-app'}):
            with self.assertRaisesRegex(RuntimeError, 'another service'):
                launcher.stop()

    def test_official_login_and_already_signed_in(self):
        for ready in (True, False):
            with self.subTest(ready=ready), patch('launcher.codex_client', return_value=('codex', {})), \
                 patch('launcher.chatgpt_ready', side_effect=[ready, True]), \
                 patch('launcher.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertTrue(launcher.connect_chatgpt())
                if ready:
                    run.assert_not_called()
                else:
                    self.assertEqual(run.call_args.args[0], ['codex', '-c', 'forced_login_method="chatgpt"', 'login'])

    def test_local_server_lifecycle_and_active_roast_shutdown_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder) / 'smoke.sqlite3')
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with patch('launcher.BASE', f'http://127.0.0.1:{server.server_port}'):
                    self.assertEqual(launcher.running_studio()['app'], 'roast-studio')
                    self.assertFalse(app.engine.bullet.status()['connected'])
                    app.engine.active = {'id': 999, 'status': 'roasting'}
                    with self.assertRaisesRegex(RuntimeError, 'Finish and save'):
                        launcher.stop()
                    app.engine.active = None
                    launcher.stop()
                    worker.join(3)
                    self.assertFalse(worker.is_alive())
            finally:
                app.engine.active = None
                server.shutdown()
                server.server_close()
                worker.join()
                app.close()
