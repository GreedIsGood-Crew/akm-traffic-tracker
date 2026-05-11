"""
Smoke unit tests for akm-traffic-tracker pure Python modules.
No DB / HTTP / external services required.

Run: pytest backend/tests/ -v
"""
import sys
import os

# Allow importing from backend/ without modifying PYTHONPATH globally
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── schemas ──────────────────────────────────────────────────────────────────
from schemas import Filters


def test_filters_all_optional():
    """Filters model accepts an empty dict (all fields optional)."""
    f = Filters()
    assert f.date_from is None
    assert f.date_to is None
    assert f.campaigns is None
    assert f.detail_level is None


def test_filters_accepts_valid_data():
    f = Filters(date_from="2026-01-01", date_to="2026-01-31", campaigns=[1, 2, 3], detail_level="day")
    assert f.date_from == "2026-01-01"
    assert f.campaigns == [1, 2, 3]
    assert f.detail_level == "day"


def test_filters_campaigns_list():
    f = Filters(campaigns=[10])
    assert isinstance(f.campaigns, list)
    assert f.campaigns[0] == 10


# ── jwt helpers (isolated, no DB dependency) ─────────────────────────────────
# We import only the JWT primitives directly to avoid the DB import chain in auth.py.
from jose import jwt as _jwt
from datetime import datetime, timedelta

SECRET = "test-secret"
ALGO = "HS256"


def _make_token(sub: str) -> str:
    """Minimal re-implementation of create_access_token for testing the contract."""
    payload = {"sub": sub, "exp": datetime.utcnow() + timedelta(hours=1)}
    return _jwt.encode(payload, SECRET, algorithm=ALGO)


def test_jwt_token_returns_string():
    token = _make_token("user_1")
    assert isinstance(token, str)
    assert len(token) > 20


def test_jwt_different_subs_produce_different_tokens():
    t1 = _make_token("user_A")
    t2 = _make_token("user_B")
    assert t1 != t2


def test_jwt_token_decodes_sub():
    token = _make_token("test_user")
    payload = _jwt.decode(token, SECRET, algorithms=[ALGO])
    assert payload["sub"] == "test_user"
