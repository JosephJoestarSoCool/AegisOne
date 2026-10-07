import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp()) / "test_aegis.db"
os.environ["AEGIS_DB"] = str(_tmp)

import pytest  # noqa: E402

from app import service as svc  # noqa: E402
from app.datagen import build_database  # noqa: E402
from app.db import connect  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    build_database(_tmp, write_csv=False)
    yield


@pytest.fixture()
def con():
    c = connect()
    svc.clear_cache()
    yield c
    c.close()
