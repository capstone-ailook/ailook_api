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

        self._maybe_preload_embedder()

    def _maybe_preload_embedder(self):
        """BGE-M3를 서버 부팅 경로에서만 선로드 (design.md D6).

        migrate/makemigrations/shell 등 관리 명령에서는 2GB 모델 로드를 피한다.
        runserver autoreload는 워커(RUN_MAIN=true)에서만 1회 로드.
        """
        import sys
        argv0 = sys.argv[0] if sys.argv else ""
        is_runserver = "runserver" in sys.argv
        is_wsgi = "gunicorn" in argv0 or "uvicorn" in argv0 or "daphne" in argv0
        if not (is_runserver or is_wsgi):
            return
        if is_runserver and os.environ.get("RUN_MAIN") != "true":
            return  # autoreload watcher 프로세스 — 건너뜀
        try:
            from . import rag_service
            rag_service.warm_up()
            print("BGE-M3 preloaded.")
        except Exception as e:
            print(f"BGE-M3 preload skipped: {e}")

