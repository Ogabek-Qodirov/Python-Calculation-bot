import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_calculationbot as bot

def test_supabase_fallback_to_local(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, 'supabase_client', None)
    monkeypatch.setattr(bot, 'DATA_DIR', str(tmp_path))

    cid = "test_user_123"
    data = {"2026-09-20": {"total_income": 10000, "total_expense": 5000, "balance": 5000, "transactions": [], "todos": []}}

    bot.save_user_data(cid, data)
    loaded = bot.load_user_data(cid)

    assert loaded == data
    assert loaded["2026-09-20"]["balance"] == 5000
