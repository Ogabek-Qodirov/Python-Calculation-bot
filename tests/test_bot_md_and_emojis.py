import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_calculationbot as bot

def test_generate_md_content_periods():
    data = {
        '2026-09-01': {
            'total_income': 1000000,
            'total_expense': 100000,
            'balance': 900000,
            'transactions': [
                {'type': 'income', 'amount': 1000000, 'description': 'Oylik', 'timestamp': '2026-09-01T09:00:00'}
            ],
            'todos': [
                {'task': 'Oy boshi rejasi', 'done': True}
            ]
        },
        '2026-09-20': {
            'total_income': 500000,
            'total_expense': 50000,
            'balance': 450000,
            'transactions': [
                {'type': 'expense', 'amount': 50000, 'description': 'Taksi', 'timestamp': '2026-09-20T11:00:00'},
                {'type': 'note', 'amount': 0, 'description': 'Muhim eslatma', 'timestamp': '2026-09-20T12:00:00'}
            ],
            'todos': [
                {'task': 'Ertalabki majlis', 'done': True},
                {'task': 'Hisobot topshirish', 'done': False}
            ]
        }
    }

    # Test single day
    content_today = bot.generate_md_content(data, 'today')
    assert "# 📋 Vazifalar va Qaydlar — Bugun" in content_today

    # Test month (single consolidated .md file)
    content_month = bot.generate_md_content(data, 'month')
    assert "# 📋 Vazifalar va Qaydlar — Bu Oy" in content_month
    assert "## 📅 2026-09-01" in content_month
    assert "## 📅 2026-09-20" in content_month
    assert "Oy boshi rejasi" in content_month
    assert "Ertalabki majlis" in content_month

    # Test Qaydlar.md generation
    content_journal = bot.generate_journal_md_content(data, 'month')
    assert "# 📝 Qaydlar va Kundalik — Bu Oy" in content_journal
    assert "🟢 Daromad: 1,000,000 so'm — Oylik" in content_journal
    assert "📝 Muhim eslatma" in content_journal
    assert "Oy boshi rejasi" not in content_journal  # Qaydlar.md contains notes/transactions only

def test_serious_emojis_in_messages():
    data = {}
    res_inc = bot.add_transaction('income', 100000, 'Sinov', data)
    assert '🟢' in res_inc
    assert '🤩' not in res_inc

    res_todo = bot.add_todo('Yangi vazifa', data)
    assert '✅' in res_todo
    assert '💪' not in res_todo
