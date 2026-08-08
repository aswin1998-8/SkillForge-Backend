from django.urls import path

from apps.users.views import ProfileView

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
]
