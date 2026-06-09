from django.test import TestCase
from unittest.mock import patch, MagicMock
import time
from django.conf import settings
from users import rag_service
from users.models import ChatSession

class RagServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        # Ensure we have a dummy API key for tests
        self.original_api_key = settings.GEMINI_API_KEY
        settings.GEMINI_API_KEY = "dummy_key"
        # Reset cache of _genai_client if it exists
        rag_service._genai_client.cache_clear()

    def tearDown(self):
        settings.GEMINI_API_KEY = self.original_api_key
        super().tearDown()

    @patch("users.rag_service._genai_client")
    def test_gen_success_first_try(self, mock_client_func):
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Hello world"
        mock_client.models.generate_content.return_value = mock_response

        res = rag_service._gen("test prompt")
        self.assertEqual(res.text, "Hello world")
        mock_client.models.generate_content.assert_called_once()

    @patch("users.rag_service._genai_client")
    @patch("time.sleep")
    def test_gen_retry_on_transient_error(self, mock_sleep, mock_client_func):
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # First call: Rate limit exception with small wait time
        # Second call: Success
        mock_response = MagicMock()
        mock_response.text = "Success after retry"
        
        mock_client.models.generate_content.side_effect = [
            Exception("Rate limited (429): please retry in 2.5s"),
            mock_response
        ]

        res = rag_service._gen("test prompt")
        self.assertEqual(res.text, "Success after retry")
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        mock_sleep.assert_called_once_with(3.0)  # 2.5s + 0.5s = 3.0s

    @patch("users.rag_service._genai_client")
    @patch("time.sleep")
    def test_gen_caps_wait_time_to_five_seconds(self, mock_sleep, mock_client_func):
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # Rate limit exception with a long wait time (26s)
        mock_client.models.generate_content.side_effect = Exception("Rate limited (429): please retry in 26.2s")

        with self.assertRaises(Exception) as context:
            rag_service._gen("test prompt")
        
        self.assertIn("rate limited (429)", str(context.exception).lower())
        # Should call sleep 2 times with 5.0s (attempts 1 & 2)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(5.0)
        self.assertEqual(mock_client.models.generate_content.call_count, 3)

    @patch("users.rag_service._gen")
    def test_handle_graceful_fallback(self, mock_gen):
        mock_gen.side_effect = Exception("Rate limited (429): please retry in 26.2s")
        
        # Create a mock request and session
        user = MagicMock()
        user.profile = MagicMock(gender="man", age="20s", height=180, weight=75, nickname="Tester")
        
        request = MagicMock()
        request.user = user
        
        session = MagicMock()
        session.messages.order_by.return_value = []
        
        res = rag_service.handle(request, session, "오늘 옷 뭐입지?")
        self.assertIn("잠시 요청이 많아 응답이 지연되고 있어요", res["reply"])
        self.assertEqual(res["outfits"], [])



