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
                
                if os.path.exists(key_path):
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            except Exception as e:
                print(f"Warning initialize_app: {e}")

