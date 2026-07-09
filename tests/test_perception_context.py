"""The live-perception prompt note: present/away/expression, and the critical
no-overclaim guard (nothing injected when the camera is off)."""

from app.api.v2 import _perception_extra_context as ctx
from app.api.v2_models import PerceptionContextRequest as P


def test_camera_off_injects_nothing():
    # No signal => no prompt note => Joi can't claim to see.
    assert ctx(None) is None
    assert ctx(P(camera_active=False, user_present=True, expression="smile")) is None


def test_present_includes_expression_and_lean():
    out = ctx(P(camera_active=True, user_present=True, expression="smile", leaned_in=True))
    assert out is not None
    assert "in frame" in out
    assert "leaned in" in out
    assert "happy" in out or "warm" in out


def test_present_neutral_reads_as_calm():
    out = ctx(P(camera_active=True, user_present=True, expression="neutral"))
    assert out is not None and "in frame" in out
    assert "calm" in out  # she has something concrete to say


def test_away_is_reported_not_denied():
    out = ctx(P(camera_active=True, user_present=False))
    assert out is not None
    assert "isn't visible" in out
    assert "camera is on" in out  # she knows the camera is on — just no face right now
