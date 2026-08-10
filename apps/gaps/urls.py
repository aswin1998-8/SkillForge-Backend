from django.urls import path

from apps.gaps.views import SkillGapAnalysisView, UserSkillGapListView

urlpatterns = [
    path("gaps/analysis/", SkillGapAnalysisView.as_view(), name="gap-analysis"),
    path("gaps/", UserSkillGapListView.as_view(), name="gap-list"),
]
