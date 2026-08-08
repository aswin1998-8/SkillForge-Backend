from django.urls import path

from apps.roles.views import RoleListView, SkillListView

urlpatterns = [
    path("roles/", RoleListView.as_view(), name="role-list"),
    path("skills/", SkillListView.as_view(), name="skill-list"),
]
