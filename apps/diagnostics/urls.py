from django.urls import path

from apps.diagnostics.views import (
    DiagnosticSessionAnswerRevealView,
    DiagnosticSessionAnswerSelfRateView,
    DiagnosticSessionAnswersView,
    DiagnosticSessionDetailView,
    DiagnosticSessionListCreateView,
    DiagnosticSessionRunTestsView,
    FrameworkTopicListView,
)

urlpatterns = [
    path("framework-topics/", FrameworkTopicListView.as_view(), name="framework-topics"),
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
    path(
        "diagnostic-sessions/<int:session_id>/answers/<int:answer_id>/reveal/",
        DiagnosticSessionAnswerRevealView.as_view(),
        name="diagnostic-session-answer-reveal",
    ),
    path(
        "diagnostic-sessions/<int:session_id>/answers/<int:answer_id>/self-rate/",
        DiagnosticSessionAnswerSelfRateView.as_view(),
        name="diagnostic-session-answer-self-rate",
    ),
    path(
        "diagnostic-sessions/<int:session_id>/run-tests/",
        DiagnosticSessionRunTestsView.as_view(),
        name="diagnostic-session-run-tests",
    ),
]
