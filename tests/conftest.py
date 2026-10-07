import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

NOW = dt.datetime(2026, 10, 7, 12, 0, 0)       # frozen "server time" (BST wall clock) for every test


@pytest.fixture(scope="session")
def api():
    from fastapi.testclient import TestClient
    import api.main as m
    m.now_bst = lambda: NOW                    # freeze the clock used by validation and defaults
    return TestClient(m.app)


@pytest.fixture(scope="session")
def customer(api):
    """A real synthetic customer with a profile and at least one frequent recipient."""
    for cid in api.get("/demo_customers").json():
        ctx = api.get(f"/customer/{cid}/context").json()
        if ctx["frequent_recipients"]:
            return ctx
    raise RuntimeError("no demo customer with history")


def iso(minutes_before=0, day_offset=0):
    return (NOW - dt.timedelta(days=day_offset, minutes=minutes_before)).isoformat(timespec="seconds")
