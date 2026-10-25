"""
URL configuration for scr project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from app.views import web_app_view

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # Do'kon interfeysi (Skaner va boshqaruv paneli)
    path('', web_app_view, name='home'),

    # REST Framework API lari
    path('api/', include('app.urls')),

    # Swagger va OpenAPI Hujjatlashtirish
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Media files (Barcodes, QR codes, Book covers) in both development & production
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
