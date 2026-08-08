from django.urls import path

from apps.challenges.views import (
    AttemptConfidenceView,
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
]
