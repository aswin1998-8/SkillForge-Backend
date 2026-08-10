from django.urls import path

from apps.users.views import ProfileView, StaffResetProgressView

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "admin/reset-progress/",
        StaffResetProgressView.as_view(),
        name="staff-reset-progress",
    ),
]
