"""Prevent two recorder processes from using the same database."""
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, database):
        path = Path(str(database) + '.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open('a+b')
        if path.stat().st_size == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise ValueError('This database is already open in another Roast Studio process. Open the existing app instead.') from exc

    def close(self):
        if not self.file.closed:
            self.file.close()
