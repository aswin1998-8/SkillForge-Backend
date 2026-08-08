from django.urls import path

from apps.gaps.views import UserSkillGapListView

urlpatterns = [
    path("gaps/", UserSkillGapListView.as_view(), name="gap-list"),
]
