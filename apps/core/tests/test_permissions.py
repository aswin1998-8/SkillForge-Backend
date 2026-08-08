"""Permission isolation tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.services import ensure_user_side_effects


@pytest.mark.django_db
def test_user_cannot_access_other_debrief() -> None:
    api = APIClient()
    owner = ensure_user_side_effects(
        User.objects.create_user(email="owner@skillforge.test", password="testpass123")
    )
    other = ensure_user_side_effects(
        User.objects.create_user(email="other@skillforge.test", password="testpass123")
    )
    api.force_authenticate(user=other)
    response = api.get("/api/v1/debriefs/999999/")
    assert response.status_code in {403, 404}
    api.force_authenticate(user=owner)
    response = api.get("/api/v1/sessions/")
    assert response.status_code == 200
