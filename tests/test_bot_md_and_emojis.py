import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_calculationbot as bot

def test_generate_md_content():
    data = {
        '2026-09-20': {
            'total_income': 500000,
            'total_expense': 50000,
            'balance': 450000,
            'transactions': [
                {'type': 'income', 'amount': 500000, 'description': 'Maosh', 'timestamp': '2026-09-20T10:00:00'},
                {'type': 'expense', 'amount': 50000, 'description': 'Taksi', 'timestamp': '2026-09-20T11:00:00'},
                {'type': 'note', 'amount': 0, 'description': 'Muhim eslatma', 'timestamp': '2026-09-20T12:00:00'}
            ],
            'todos': [
                {'task': 'Ertalabki majlis', 'done': True, 'created': '2026-09-20T09:00:00'},
                {'task': 'Hisobot topshirish', 'done': False, 'created': '2026-09-20T09:30:00'}
            ]
        }
    }
    content = bot.generate_md_content(data, '2026-09-20')
    assert "# 📋 Bugungi Vazifalar va Qaydlar — 2026-09-20" in content
    assert "- [x] 1. Ertalabki majlis" in content
    assert "- [ ] 2. Hisobot topshirish" in content
    assert "🟢 Daromad: 500,000 so'm — Maosh" in content
    assert "🔴 Xarajat: 50,000 so'm — Taksi" in content
    assert "📝 Muhim eslatma" in content

def test_save_user_md_file():
    data = {'2026-09-20': {'todos': [], 'transactions': [], 'balance': 0, 'total_income': 0, 'total_expense': 0}}
    path, content = bot.save_user_md_file("test_user", data, "2026-09-20")
    assert os.path.exists(path)
    with open(path, 'r', encoding='utf-8') as f:
        saved_text = f.read()
    assert saved_text == content
    os.remove(path)

def test_serious_emojis_in_messages():
    data = {}
    res_inc = bot.add_transaction('income', 100000, 'Sinov', data)
    assert '🟢' in res_inc
    assert '🤩' not in res_inc
    assert '😍' not in res_inc

    res_todo = bot.add_todo('Yangi vazifa', data)
    assert '✅' in res_todo
    assert '💪' not in res_todo
    assert 'Zo\'r!' not in res_todo
