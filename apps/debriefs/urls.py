from django.urls import path

from apps.debriefs.views import DebriefAnswerView, DebriefDetailView

urlpatterns = [
    path("debriefs/<int:session_id>/", DebriefDetailView.as_view(), name="debrief-detail"),
    path(
        "debriefs/<int:session_id>/answer/",
        DebriefAnswerView.as_view(),
        name="debrief-answer",
    ),
]
