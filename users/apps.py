import os
from django.apps import AppConfig
import firebase_admin
from firebase_admin import credentials

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        try:
            firebase_admin.get_app()
        except ValueError:
            try:
                # Use the service account key if it exists
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                key_path = os.path.join(base_dir, 'serviceAccountKey.json')
                
                # Check for env variable JSON content first, then file, then fallback
                firebase_creds_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
                
                if firebase_creds_json:
                    import json
                    cred_dict = json.loads(firebase_creds_json)
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                elif os.path.exists(key_path):
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred)
                else:
                    project_id = os.environ.get('FIREBASE_PROJECT_ID') or os.environ.get('GOOGLE_CLOUD_PROJECT') or 'ailook-flutter-dev'
                    firebase_admin.initialize_app(options={'projectId': project_id})
            except Exception as e:
                print(f"Warning initialize_app: {e}")

        self._maybe_preload_embedder()

    def _maybe_preload_embedder(self):
        """BGE-M3 선로드 제거 (Gemini 전용 전환)"""
        pass

