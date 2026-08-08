from django.urls import path

from apps.sessions.views import SessionDetailView, SessionListView

urlpatterns = [
    path("sessions/", SessionListView.as_view(), name="session-list"),
    path("sessions/<int:session_id>/", SessionDetailView.as_view(), name="session-detail"),
]
