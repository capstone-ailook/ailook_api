import firebase_admin
from firebase_admin import auth, credentials
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth.models import User

class FirebaseAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        # Format: Bearer <token>
        parts = auth_header.split()
        if parts[0].lower() != 'bearer':
            return None
        
        if len(parts) == 1 or len(parts) > 2:
            return None

        id_token = parts[1]

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token.get('uid')
            email = decoded_token.get('email', '')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Invalid Firebase token: {e}')

        if not uid:
            raise exceptions.AuthenticationFailed('No UID in token')

        # Get or create the user in Django
        user, created = User.objects.get_or_create(username=uid)
        if created and email:
            user.email = email
            user.save()

        return (user, None)
