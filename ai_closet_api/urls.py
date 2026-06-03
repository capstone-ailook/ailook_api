import os

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    # API Schema and Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # RAG 코퍼스 outfit 이미지 서빙 (RAG/data/images/{gender}/{file})
    path('rag-images/<path:path>', static_serve,
         {'document_root': os.path.join(settings.RAG_DATA_DIR, 'images')}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
