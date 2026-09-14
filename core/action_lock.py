"""Cross-process ownership of Android while a program or manual action runs."""
from contextlib import contextmanager
import os
import config

@contextmanager
def android_owner():
    directory=config.BASE_DIR/"local-runtime"
    directory.mkdir(exist_ok=True)
    with (directory/"android.lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0);handle.write(b"0");handle.flush();handle.seek(0)
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Android is owned by a running program or another action. Stop it or wait.") from exc
        try: yield
        finally:
            if os.name == "nt":
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)
