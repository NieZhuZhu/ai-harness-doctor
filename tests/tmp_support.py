"""Shared test helpers for resilient temporary-directory cleanup.

Several tests create a throwaway git repository inside a ``TemporaryDirectory``
and drive the Node CLI (``guard``/``install``) against it. On macOS -- and
notably under Python 3.14 -- the plain ``shutil.rmtree`` invoked by
``TemporaryDirectory.cleanup`` intermittently raises ``OSError: [Errno 66]
Directory not empty`` (``ENOTEMPTY``): a lingering child process or the OS
momentarily repopulates the tree (e.g. inside ``.git``) between the directory
walk and the final ``rmdir``. This is a *teardown race*, not a product defect --
Linux CI, where ``rmtree`` succeeds on the first try, is unaffected.

``robust_rmtree`` retries a few times and, as a last resort, falls back to
``ignore_errors=True`` so a cleanup race can never fail an otherwise-green run.
``ResilientTemporaryDirectory`` is a drop-in ``tempfile.TemporaryDirectory``
whose ``cleanup`` routes through ``robust_rmtree``; because every call site uses
it as a ``with`` context manager, ``__exit__`` -> ``cleanup`` picks up the
resilient behavior with no other change.
"""

import shutil
import tempfile
import time


def robust_rmtree(path, retries=5, delay=0.1):
    """Remove ``path`` tolerating a transient ENOTEMPTY cleanup race.

    On the final attempt, fall back to ``ignore_errors=True`` so a persistent
    race never turns into a test error. A missing path is treated as success.
    """
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == retries - 1:
                shutil.rmtree(path, ignore_errors=True)
                return
            time.sleep(delay)


class ResilientTemporaryDirectory(tempfile.TemporaryDirectory):
    """A ``TemporaryDirectory`` whose cleanup tolerates the ENOTEMPTY race."""

    def cleanup(self):
        robust_rmtree(self.name)
