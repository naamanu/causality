import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_db = tempfile.NamedTemporaryFile(prefix="causality-test-", suffix=".sqlite", delete=False)
_db.close()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ["DEV_AUTH_ENABLED"] = "true"
