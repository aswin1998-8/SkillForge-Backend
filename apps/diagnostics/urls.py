from django.urls import path

from apps.diagnostics.views import (
    AttemptAnswersView,
    AttemptDetailView,
    AttemptNextView,
    AttemptSubmitView,
    AttemptTurnSubmitView,
    DiagnosticDetailView,
    DiagnosticListView,
    DiagnosticSessionAnswersView,
    DiagnosticSessionDetailView,
    DiagnosticSessionListCreateView,
    DiagnosticStartView,
)

urlpatterns = [
    path("diagnostics/", DiagnosticListView.as_view(), name="diagnostic-list"),
    path(
        "diagnostics/<int:diagnostic_id>/",
        DiagnosticDetailView.as_view(),
        name="diagnostic-detail",
    ),
    path(
        "diagnostics/<int:diagnostic_id>/start/",
        DiagnosticStartView.as_view(),
        name="diagnostic-start",
    ),
    path(
        "diagnostic-sessions/",
        DiagnosticSessionListCreateView.as_view(),
        name="diagnostic-session-create",
    ),
    path(
        "diagnostic-sessions/<int:session_id>/",
        DiagnosticSessionDetailView.as_view(),
        name="diagnostic-session-detail",
    ),
    path(
        "diagnostic-sessions/<int:session_id>/answers/",
        DiagnosticSessionAnswersView.as_view(),
        name="diagnostic-session-answers",
    ),
    path("attempts/<int:attempt_id>/answers/", AttemptAnswersView.as_view(), name="attempt-answers"),
    path("attempts/<int:attempt_id>/submit/", AttemptSubmitView.as_view(), name="attempt-submit"),
    path("attempts/<int:attempt_id>/next/", AttemptNextView.as_view(), name="attempt-next"),
    path("attempts/<int:attempt_id>/turns/", AttemptTurnSubmitView.as_view(), name="attempt-turn-submit"),
    path("attempts/<int:attempt_id>/", AttemptDetailView.as_view(), name="attempt-detail"),
]
