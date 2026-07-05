"""Global pytest configuration.

Isolates the test suite from the real application data. The memory store binds
its SQLAlchemy engine and Chroma client from settings at import time, so these
env overrides must be set here — before pytest imports any test module (and thus
any app module). Without this, running the suite writes test rows into the real
./data database and Chroma index.
"""

import atexit
import os
import shutil
import tempfile

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="joi-tests-")

# Redirect every persistent surface to the throwaway directory.
os.environ["DB_PATH"] = os.path.join(_TEST_DATA_DIR, "test.db")
os.environ["AGENT_CHROMA_PATH"] = os.path.join(_TEST_DATA_DIR, "chroma")
os.environ["JOI_DATA_DIR"] = _TEST_DATA_DIR
# Force SQLite even if a Postgres DATABASE_URL is configured in the environment.
os.environ["DATABASE_URL"] = ""


@atexit.register
def _cleanup_test_data_dir() -> None:
    # Best-effort: SQLite/Chroma may still hold file handles at interpreter exit
    # on Windows, so ignore errors and let the OS reclaim the temp dir.
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
