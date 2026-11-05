import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hebra import db  # noqa: E402


@pytest.fixture
def con(tmp_path):
    c = db.connecta(str(tmp_path / "prova.db"))
    db.inicialitza(c)
    yield c
    c.close()
