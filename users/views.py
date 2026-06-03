import os
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from google import genai
from urllib.parse import urlparse
from .models import UserProfile, Item, Cody, ChatSession, ChatMessage
from .serializers import UserProfileSerializer, ItemSerializer, CodySerializer

def get_dynamic_url(url_string, request):
    if not url_string or not request:
        return url_string
    parsed = urlparse(url_string)
    if parsed.scheme and parsed.netloc:
        path = parsed.path
        if parsed.query:
            path += f"?{parsed.query}"
    else:
        path = url_string
    return request.build_absolute_uri(path)


class ImageUploadView(APIView):
    """Upload an image file and get back its served URL."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Save to media/uploads/<filename>
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        import uuid
        ext = os.path.splitext(image_file.name)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, 'wb') as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        # Build the URL (served via Django's media serving)
        image_url = request.build_absolute_uri(f"/media/uploads/{filename}")
        return Response({'image_url': image_url}, status=status.HTTP_201_CREATED)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.profile
            serializer = UserProfileSerializer(profile)
            return Response({"exists": True, "profile": serializer.data})
        except UserProfile.DoesNotExist:
            return Response({"exists": False, "profile": None})

    def post(self, request):
        try:
            profile = request.user.profile
            serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        except UserProfile.DoesNotExist:
            serializer = UserProfileSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "Profile updated successfully.", "profile": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatSessionListView(APIView):
    """List all sessions or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = ChatSession.objects.filter(user=request.user)
        data = []
        for s in sessions:
            first_msg = s.messages.filter(role='user').first()
            data.append({
                'id': s.id,
                'title': s.title or (first_msg.text[:50] if first_msg else '새 대화'),
                'created_at': s.created_at.isoformat(),
                'updated_at': s.updated_at.isoformat(),
            })
        return Response({'sessions': data})

    def post(self, request):
        title = request.data.get('title', '')
        session = ChatSession.objects.create(user=request.user, title=title)
        return Response({'id': session.id, 'title': session.title}, status=status.HTTP_201_CREATED)


class ChatSessionDetailView(APIView):
    """Get messages for a session or send a new message in a session."""
    permission_classes = [IsAuthenticated]

    def _get_session(self, request, session_id):
        try:
            return ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return None

    def delete(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        messages = session.messages.all()
        data = [{'role': m.role, 'text': m.text,
                 'image_url': get_dynamic_url(m.image_url, request),
                 'outfits': m.outfits,
                 'anchor_item_id': m.anchor_item_id,
                 'anchor_category': m.anchor_category} for m in messages]
        return Response({'session_id': session.id, 'title': session.title, 'messages': data})

    def post(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        user_message = request.data.get("message", "")
        image_url = request.data.get("image_url", "")
        profile_data = request.data.get("profile", None)

        # Save user message
        ChatMessage.objects.create(
            session=session, user=request.user,
            role='user', text=user_message, image_url=image_url
        )

        # Auto-set session title based on first user message
        if not session.title and user_message:
            session.title = user_message[:50]
            session.save(update_fields=['title'])

        # RAG 코디 추천 (의도 분기 + 검색 + 생성) — rag_service에 위임
        from . import rag_service
        result = rag_service.handle(
            request, session, user_message,
            anchor_item_id=request.data.get("anchor_item_id"),
            profile_data=profile_data,
        )

        ChatMessage.objects.create(
            session=session, user=request.user, role='ai',
            text=result["reply"], outfits=result.get("outfits", []),
            anchor_item_id=result.get("anchor_item_id"),
            anchor_category=result.get("anchor_category") or "",
        )
        # Touch updated_at on session so it sorts to the top
        session.save(update_fields=['updated_at'])
        return Response({
            "reply": result["reply"],
            "outfits": result.get("outfits", []),
            "anchor_item_id": result.get("anchor_item_id"),
            "anchor_category": result.get("anchor_category") or "",
        })


class ItemViewSet(viewsets.ModelViewSet):
    serializer_class = ItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only show items belonging to the current user (and maybe global ones if user is None, 
        # but for 'My Closet' we primarily care about user's items)
        qs = Item.objects.filter(user=self.request.user).order_by('-created_at')
        
        category = self.request.query_params.get('category')
        if category and category != 'all':
            qs = qs.filter(category=category)
            
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
            
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CodyViewSet(viewsets.ModelViewSet):
    serializer_class = CodySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Cody.objects.filter(user=self.request.user).order_by('-created_at')
        if self.request.query_params.get('favorite') == 'true':
            qs = qs.filter(is_favorite=True)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='toggle_favorite')
    def toggle_favorite(self, request, pk=None):
        cody = self.get_object()
        cody.is_favorite = not cody.is_favorite
        cody.save(update_fields=['is_favorite'])
        return Response({'is_favorite': cody.is_favorite})
