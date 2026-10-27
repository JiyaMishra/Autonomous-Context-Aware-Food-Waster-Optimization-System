"""Keep demo fixture data enabled only during automated tests and isolate test database."""
import os
import tempfile
import pytest

_TEST_DB_FILE = os.path.join(tempfile.gettempdir(), "messwise_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_FILE.replace(os.sep, '/')}"
os.environ.setdefault("MESSWISE_SEED_DEMO_DATA", "true")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    try:
        if os.path.exists(_TEST_DB_FILE):
            os.remove(_TEST_DB_FILE)
    except Exception:
        pass
