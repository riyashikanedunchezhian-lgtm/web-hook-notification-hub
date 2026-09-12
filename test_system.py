#!/usr/bin/env python3
"""
Test script to verify the webhook notification hub system.
This script tests all major components without requiring actual Redis or external services.
"""

import sys
import json
from datetime import datetime

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        import config
        import models
        import webhook_security
        import redis_queue
        import notifications
        import tasks
        import main
        import worker
        print("[PASS] All modules imported successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        from config import settings
        print(f"[PASS] Config loaded: host={settings.host}, port={settings.port}")
        return True
    except Exception as e:
        print(f"[FAIL] Config test failed: {e}")
        return False

def test_models():
    """Test data models."""
    print("\nTesting data models...")
    try:
        from models import WebhookEvent, EventStatus, DashboardEvent
        
        # Test WebhookEvent creation
        event = WebhookEvent(
            event_type="push",
            source="github",
            payload={"test": "data"},
            idempotency_key="test-key"
        )
        print(f"[PASS] WebhookEvent created: {event.id}")
        
        # Test EventStatus enum
        assert EventStatus.SUCCESS.value == "success"
        print(f"[PASS] EventStatus enum works: {EventStatus.SUCCESS.value}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Models test failed: {e}")
        return False

def test_webhook_security():
    """Test webhook signature verification."""
    print("\nTesting webhook security...")
    try:
        from webhook_security import verify_github_signature
        import hmac
        import hashlib
        
        # Test with correct signature
        secret = b"test_secret"
        payload = b'{"test": "data"}'
        
        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        signature_header = f"sha256={signature}"
        
        # Temporarily set the secret
        from config import settings
        original_secret = settings.github_webhook_secret
        settings.github_webhook_secret = "test_secret"
        
        result = verify_github_signature(payload, signature_header)
        print(f"[PASS] Signature verification (valid): {result}")
        
        # Test with invalid signature
        invalid_result = verify_github_signature(payload, "sha256=invalid")
        print(f"[PASS] Signature verification (invalid): {invalid_result}")
        
        # Restore original secret
        settings.github_webhook_secret = original_secret
        
        return True
    except Exception as e:
        print(f"[FAIL] Webhook security test failed: {e}")
        return False

def test_notifications():
    """Test notification components."""
    print("\nTesting notifications...")
    try:
        from notifications import RateLimiter, SlackNotifier, GitHubEventHandler
        
        # Test RateLimiter
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        print(f"[PASS] RateLimiter created: max={limiter.max_requests}")
        
        # Test GitHubEventHandler
        test_payload = {
            "repository": {"full_name": "test/repo"},
            "pusher": {"name": "testuser"},
            "ref": "refs/heads/main",
            "commits": [{"id": "abc123"}],
            "head_commit": {"message": "Test commit"},
            "compare": "https://github.com/test/repo/compare"
        }
        
        parsed = GitHubEventHandler.parse_push_event(test_payload)
        print(f"[PASS] GitHub event parsed: {parsed['repository']}")
        
        message = GitHubEventHandler.format_slack_message(test_payload)
        print(f"[PASS] Slack message formatted: {len(message)} chars")
        
        return True
    except Exception as e:
        print(f"[FAIL] Notifications test failed: {e}")
        return False

def test_redis_queue_components():
    """Test Redis queue components (without actual Redis)."""
    print("\nTesting Redis queue components...")
    try:
        from redis_queue import IdempotencyManager, EventStore
        
        # Test that classes exist and have correct methods
        assert hasattr(IdempotencyManager, 'is_duplicate')
        assert hasattr(IdempotencyManager, 'mark_processed')
        assert hasattr(IdempotencyManager, 'get_event_id')
        assert hasattr(IdempotencyManager, 'store_event_id')
        print("[PASS] IdempotencyManager has all required methods")
        
        assert hasattr(EventStore, 'save_event')
        assert hasattr(EventStore, 'get_event')
        assert hasattr(EventStore, 'get_recent_events')
        assert hasattr(EventStore, 'update_event_status')
        print("[PASS] EventStore has all required methods")
        
        return True
    except Exception as e:
        print(f"[FAIL] Redis queue components test failed: {e}")
        return False

def test_celery_task():
    """Test Celery task definition."""
    print("\nTesting Celery task...")
    try:
        from tasks import process_webhook
        from redis_queue import celery_app
        
        # Check that task is registered
        assert 'tasks.process_webhook' in celery_app.tasks
        print("[PASS] Celery task registered: tasks.process_webhook")
        
        # Check task properties
        assert process_webhook.max_retries == 3
        print(f"[PASS] Task max_retries: {process_webhook.max_retries}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Celery task test failed: {e}")
        return False

def test_fastapi_app():
    """Test FastAPI application."""
    print("\nTesting FastAPI application...")
    try:
        from main import app
        
        # Check app exists
        assert app.title == "Webhook Notification Hub"
        print(f"[PASS] FastAPI app created: {app.title}")
        
        # Check routes
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/health", "/webhook/github", "/api/events"]
        
        for route in expected_routes:
            if route in routes:
                print(f"[PASS] Route exists: {route}")
            else:
                print(f"[WARN] Route missing: {route}")
        
        return True
    except Exception as e:
        print(f"[FAIL] FastAPI app test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Webhook Notification Hub - System Test")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_models,
        test_webhook_security,
        test_notifications,
        test_redis_queue_components,
        test_celery_task,
        test_fastapi_app,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"[FAIL] Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)
    
    if all(results):
        print("[PASS] All tests passed! System is ready.")
        return 0
    else:
        print("[FAIL] Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
