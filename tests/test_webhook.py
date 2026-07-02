import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_calculationbot as bot


def test_build_webhook_path_and_url():
    assert bot.build_webhook_path("abc123") == "/abc123"
    assert bot.build_webhook_url("https://example.com", "abc123") == "https://example.com/abc123"
    assert bot.build_webhook_url("https://example.com/abc123", "abc123") == "https://example.com/abc123"
