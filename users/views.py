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
        data = [{'role': m.role, 'text': m.text, 'image_url': get_dynamic_url(m.image_url, request)} for m in messages]
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

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            ai_reply = "API 키가 설정되지 않았습니다."
            ChatMessage.objects.create(session=session, user=request.user, role='ai', text=ai_reply)
            return Response({"reply": ai_reply})

        try:
            client = genai.Client(api_key=api_key)

            # Build a personalized profile context string.
            profile_context = ""
            if not profile_data:
                try:
                    profile = request.user.profile
                    profile_data = {
                        'gender': profile.gender,
                        'age': profile.age,
                        'height': profile.height,
                        'weight': profile.weight,
                        'nickname': profile.nickname,
                    }
                except UserProfile.DoesNotExist:
                    profile_data = None

            if profile_data:
                parts = []
                if profile_data.get('gender'): parts.append("성별: " + str(profile_data['gender']))
                if profile_data.get('age'): parts.append("연령대: " + str(profile_data['age']))
                if profile_data.get('height'): parts.append("키: " + str(profile_data['height']) + "cm")
                if profile_data.get('weight'): parts.append("몸무게: " + str(profile_data['weight']) + "kg")
                if profile_data.get('nickname'): parts.append("닉네임: " + str(profile_data['nickname']))
                if parts:
                    profile_context = "사용자 프로필 정보:\n" + "\n".join(parts) + "\n\n"

            # Build context from previous messages in this session (exclude last user msg)
            all_history = list(session.messages.order_by('created_at'))
            history_context = ""
            for msg in all_history[:-1]:  # list slicing works fine on Python lists
                role_label = "사용자" if msg.role == "user" else "AI"
                history_context += f"{role_label}: {msg.text}\n"

            prompt = (
                "당신은 친절하고 전문적이며 센스 있는 패션 코디네이터 AI인 'AI Closet Stylist'입니다. "
                "아래 사용자 프로필을 바탕으로 사용자의 신체 특성과 스타일에 맞는 코디를 평가하고 추천해주세요. "
                "어울리는 추천 아이템이나 스타일링 팁을 한국어로 구체적이고 다정하게 알려주세요.\n\n"
                + profile_context
                + (("이전 대화:\n" + history_context + "\n") if history_context else "")
                + "사용자: " + user_message
            )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            ai_reply = response.text
        except Exception as e:
            ai_reply = "AI API 호출 중 오류가 발생했습니다: " + str(e)

        ChatMessage.objects.create(session=session, user=request.user, role='ai', text=ai_reply)
        # Touch updated_at on session so it sorts to the top
        session.save(update_fields=['updated_at'])
        return Response({"reply": ai_reply})


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
