from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ImageUploadView, ChatSessionListView, ChatSessionDetailView, UserProfileView, ItemViewSet, CodyViewSet

router = DefaultRouter()
router.register(r'items', ItemViewSet, basename='item')
router.register(r'codies', CodyViewSet, basename='cody')

urlpatterns = [
    path('upload/image/', ImageUploadView.as_view(), name='image_upload'),
    path('chat/sessions/', ChatSessionListView.as_view(), name='chat_sessions'),
    path('chat/sessions/<int:session_id>/', ChatSessionDetailView.as_view(), name='chat_session_detail'),
    path('user/profile/', UserProfileView.as_view(), name='user_profile'),
    path('', include(router.urls)),
]
