from django.urls import path

from apps.diagnostics.views import (
    DiagnosticSessionAnswerRevealView,
    DiagnosticSessionAnswerSelfRateView,
    DiagnosticSessionAnswersView,
    DiagnosticSessionDetailView,
    DiagnosticSessionListCreateView,
    DiagnosticSessionRunTestsView,
    FrameworkTopicListView,
    QuickScoreDetailView,
    QuickScoreOgImageView,
    QuickScoreQuestionsView,
    QuickScoreSubmitView,
)

urlpatterns = [
    path("framework-topics/", FrameworkTopicListView.as_view(), name="framework-topics"),
    path(
        "quick-score/questions/",
        QuickScoreQuestionsView.as_view(),
        name="quick-score-questions",
    ),
    path("quick-score/", QuickScoreSubmitView.as_view(), name="quick-score-submit"),
    path(
        "quick-score/<int:attempt_id>/",
        QuickScoreDetailView.as_view(),
        name="quick-score-detail",
    ),
    path(
        "quick-score/<int:attempt_id>/og.png",
        QuickScoreOgImageView.as_view(),
        name="quick-score-og",
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
