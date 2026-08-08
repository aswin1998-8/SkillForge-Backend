from django.urls import path

from apps.progress.views import DashboardView, RoadmapView

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("roadmap/", RoadmapView.as_view(), name="roadmap"),
]
