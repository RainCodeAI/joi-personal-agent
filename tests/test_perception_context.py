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
    assert "present in frame" in out
    assert "leaning in" in out
    assert "smile" in out


def test_present_neutral_omits_noisy_expression():
    out = ctx(P(camera_active=True, user_present=True, expression="neutral"))
    assert out is not None and "present in frame" in out
    assert "neutral" not in out  # don't narrate a non-signal


def test_away_is_reported_not_denied():
    out = ctx(P(camera_active=True, user_present=False))
    assert out is not None and "isn't visible" in out
