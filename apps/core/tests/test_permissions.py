"""Permission isolation tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.diagnostics.models import DiagnosticSession
from apps.users.models import User
from apps.users.services import ensure_user_side_effects


@pytest.mark.django_db
def test_user_cannot_access_other_diagnostic_session() -> None:
    api = APIClient()
    owner = ensure_user_side_effects(
        User.objects.create_user(email="owner@skillforge.test", password="testpass123")
    )
    other = ensure_user_side_effects(
        User.objects.create_user(email="other@skillforge.test", password="testpass123")
    )
    session = DiagnosticSession.objects.create(
        user=owner,
        goal=DiagnosticSession.Goal.SHARPEN_CURRENT,
        status=DiagnosticSession.Status.AWAITING_ANSWERS,
    )
    api.force_authenticate(user=other)
    response = api.get(f"/api/v1/diagnostic-sessions/{session.id}/")
    assert response.status_code in {403, 404}
    api.force_authenticate(user=owner)
    response = api.get(f"/api/v1/diagnostic-sessions/{session.id}/")
    assert response.status_code == 200
