from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.users.urls_auth")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.roles.urls")),
    path("api/v1/", include("apps.diagnostics.urls")),
    path("api/v1/", include("apps.gaps.urls")),
    path("api/v1/", include("apps.challenges.urls")),
    path("api/v1/", include("apps.debriefs.urls")),
    path("api/v1/", include("apps.sessions.urls")),
    path("api/v1/", include("apps.progress.urls")),
]
