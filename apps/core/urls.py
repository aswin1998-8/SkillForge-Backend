from django.urls import path

from apps.core.staff_views import (
    StaffUserDetailView,
    StaffUserListView,
    StaffWaitlistInviteView,
    StaffWaitlistListView,
)
from apps.core.views import HealthView, WaitlistJoinView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("waitlist/join/", WaitlistJoinView.as_view(), name="waitlist-join"),
    path("staff/waitlist/", StaffWaitlistListView.as_view(), name="staff-waitlist"),
    path(
        "staff/waitlist/<int:pk>/invite/",
        StaffWaitlistInviteView.as_view(),
        name="staff-waitlist-invite",
    ),
    path("staff/users/", StaffUserListView.as_view(), name="staff-users"),
    path("staff/users/<int:pk>/", StaffUserDetailView.as_view(), name="staff-user-detail"),
]
