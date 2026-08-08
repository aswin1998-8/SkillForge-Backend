from django.urls import path

from apps.diagnostics.views import (
    AttemptAnswersView,
    AttemptDetailView,
    AttemptSubmitView,
    DiagnosticDetailView,
    DiagnosticListView,
    DiagnosticStartView,
)

urlpatterns = [
    path("diagnostics/", DiagnosticListView.as_view(), name="diagnostic-list"),
    path("diagnostics/<int:diagnostic_id>/", DiagnosticDetailView.as_view(), name="diagnostic-detail"),
    path("diagnostics/<int:diagnostic_id>/start/", DiagnosticStartView.as_view(), name="diagnostic-start"),
    path("attempts/<int:attempt_id>/answers/", AttemptAnswersView.as_view(), name="attempt-answers"),
    path("attempts/<int:attempt_id>/submit/", AttemptSubmitView.as_view(), name="attempt-submit"),
    path("attempts/<int:attempt_id>/", AttemptDetailView.as_view(), name="attempt-detail"),
]
