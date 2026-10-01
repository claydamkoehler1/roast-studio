"""CI-only Mac process smoke test: isolated data, no login, no hardware."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import launcher


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This smoke test requires macOS.')
    if launcher.running_studio():
        raise SystemExit('Refusing to test against an existing server.')
    with tempfile.TemporaryDirectory(prefix='roast-launch-smoke-') as folder:
        db = str(Path(folder) / 'isolated.sqlite3')
        with patch.dict(os.environ, {'ROAST_DB': db}), \
             patch('launcher.connect_chatgpt', return_value=False), \
             patch('launcher.webbrowser.open') as browser:
            try:
                launcher.start()
                info = launcher.running_studio()
                assert Path(info['database']).resolve() == Path(db).resolve()
                assert launcher.local_request('/api/data')['lots'] == []
                state = launcher.local_request('/api/state')
                assert not state['active']
                browser.assert_called_once_with(launcher.BASE)
                # A second launch must reuse the existing recorder.
                launcher.start()
                assert launcher.running_studio()['token'] == info['token']
            finally:
                launcher.stop()
                for _ in range(50):
                    if launcher.running_studio() is None:
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError('Recorder did not shut down cleanly.')
    print('Mac background launch, reuse, isolated database, and stop passed.')


if __name__ == '__main__':
    main()
