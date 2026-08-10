from django.urls import path

from apps.challenges.views import (
    AnalyticsEventView,
    AttemptConfidenceView,
    AttemptDebriefChecklistView,
    AttemptDebriefCompleteView,
    AttemptDebriefView,
    ChallengeDetailView,
    ChallengeSubmitView,
    TodayChallengeView,
)

urlpatterns = [
    path("challenges/today/", TodayChallengeView.as_view(), name="challenge-today"),
    path("challenges/<int:challenge_id>/", ChallengeDetailView.as_view(), name="challenge-detail"),
    path(
        "challenges/<int:challenge_id>/submit/",
        ChallengeSubmitView.as_view(),
        name="challenge-submit",
    ),
    path(
        "attempts/<int:attempt_id>/confidence/",
        AttemptConfidenceView.as_view(),
        name="attempt-confidence",
    ),
    path(
        "attempts/<int:attempt_id>/debrief/",
        AttemptDebriefView.as_view(),
        name="attempt-debrief",
    ),
    path(
        "attempts/<int:attempt_id>/debrief/checklist/",
        AttemptDebriefChecklistView.as_view(),
        name="attempt-debrief-checklist",
    ),
    path(
        "attempts/<int:attempt_id>/debrief/complete/",
        AttemptDebriefCompleteView.as_view(),
        name="attempt-debrief-complete",
    ),
    path("events/", AnalyticsEventView.as_view(), name="analytics-events"),
]
