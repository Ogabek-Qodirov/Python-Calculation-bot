"""Patch daily_calculationbot.py with emotional emoji messages."""
import re

with open('daily_calculationbot.py', 'r', encoding='utf-8-sig') as f:
    src = f.read()

# ── 1. add_transaction return block ──────────────────────────────────────
old_tx = '''\
    balance = data[today]['balance']
    sign    = '+' if balance >= 0 else ''
    return (
        f"{icon} *{label}!*\\n"
        f"📝 _{description}_\\n"
        f"💵 Miqdor: *{amount:,.0f} so'm*\\n\\n"
        f"⚖️ Bugungi balans: *{sign}{balance:,.0f} so'm*"
    )'''

new_tx = '''\
    balance = data[today]['balance']
    sign    = '+' if balance >= 0 else ''
    if tx_type == 'income':
        mood = '🤩 Barakalla!' if amount >= 500000 else '😊 Ajoyib!'
        return (
            f"💰 *Daromad qo\\'shildi!* {mood}\\n"
            f"📝 _{description}_\\n"
            f"💵 Miqdor: *{amount:,.0f} so\\'m*\\n\\n"
            f"⚖️ Bugungi balans: *{sign}{balance:,.0f} so\\'m* {'😍' if balance >= 0 else '😢'}"
        )
    else:
        mood = '😢 Ko\\'p ketdi!' if amount >= 200000 else '😅 Yaxshi!'
        return (
            f"💸 *Xarajat qo\\'shildi!* {mood}\\n"
            f"📝 _{description}_\\n"
            f"💵 Miqdor: *{amount:,.0f} so\\'m*\\n\\n"
            f"⚖️ Bugungi balans: *{sign}{balance:,.0f} so\\'m* {'😊' if balance >= 0 else '😰'}"
        )'''

src = src.replace(old_tx, new_tx, 1)

# ── 2. add_todo return ────────────────────────────────────────────────────
old_todo_ret = "    return f\"✅ #{idx} vazifa qo'shildi:\\n_{task_text}_\""
new_todo_ret = """\
    return (
        f"✅ *Vazifa qo'shildi!* 💪\\n"
        f"_{task_text}_\\n\\n"
        f"📋 Siz bugun *{idx} ta* vazifa qo'shdingiz. Zo'r!"
    )"""
src = src.replace(old_todo_ret, new_todo_ret, 1)

# ── 3. list_todos empty ───────────────────────────────────────────────────
old_empty = "        return \"📋 Bugun hali vazifalar yo'q!\\n\\nQo'shish uchun tugmani bosing 👇\""
new_empty = "        return \"😴 Bugun hali hech qanday vazifa yo'q!\\n\\n💡 Kichik qadam — katta natija! Birinchi vazifangizni qo'shing 🌟\""
src = src.replace(old_empty, new_empty, 1)

# ── 4. list_todos header+lines ───────────────────────────────────────────
old_list = '''\
    lines = ["📋 *Bugungi Vazifalar:*\\n"]
    for i, t in enumerate(todos, 1):
        check = '✅' if t['done'] else '⬜'
        lines.append(f"{check} {i}. {t['task']}")
    return '\\n'.join(lines)'''

new_list = '''\
    done_count = sum(1 for t in todos if t['done'])
    total      = len(todos)
    header     = f"💪 *Bugungi Vazifalar* ({done_count}/{total} bajarildi) \\n\\n"
    lines      = [header]
    for i, t in enumerate(todos, 1):
        check = '✅' if t['done'] else '⬜'
        lines.append(f"{check} {i}. {t['task']}")
    if done_count == total and total > 0:
        lines.append("\\n🎉 *Barakalla! Barcha vazifalar bajarildi!* 🏆")
    elif done_count > 0:
        lines.append(f"\\n🔥 *{done_count} ta bajarildi, davom eting!*")
    else:
        lines.append("\\n💡 _Birinchi vazifani boshlash vaqti!_")
    return '\\n'.join(lines)'''
src = src.replace(old_list, new_list, 1)

# ── 5. complete_todo messages ─────────────────────────────────────────────
old_done_err = "        return f\"❌ #{num} vazifa topilmadi. Sizda {len(todos)} ta vazifa bor.\""
new_done_err = "        return f\"😕 #{num} vazifa topilmadi. Sizda {len(todos)} ta vazifa bor.\""
src = src.replace(old_done_err, new_done_err, 1)

old_done_ok = "    return f\"🎉 #{num} vazifa bajarildi!\\n_{todos[num-1]['task']}_\""
new_done_ok = "    return f\"🎉 *Barakalla!* #{num} vazifa bajarildi! 💪\\n\\n✅ _{todos[num-1]['task']}_\\n\\nDavom eting, siz zo'rsiz! 🔥\""
src = src.replace(old_done_ok, new_done_ok, 1)

# ── 6. delete_todo messages ───────────────────────────────────────────────
old_del_err = "        return f\"❌ #{num} vazifa topilmadi.\""
new_del_err = "        return f\"😕 #{num} vazifa topilmadi.\""
src = src.replace(old_del_err, new_del_err, 1)

old_del_ok = "    return f\"🗑️ #{num} vazifa o'chirildi:\\n_{removed['task']}_\""
new_del_ok = "    return f\"🗑️ #{num} vazifa o'chirildi.\\n_'{removed['task']}'_\\n\\n😌 Yaxshi qaror!\""
src = src.replace(old_del_ok, new_del_ok, 1)

# ── 7. show_summary balance emoji ────────────────────────────────────────
old_summ = '''\
    lines   = [
        f"📊 *Bugungi Hisobot* ({today})\\n",
        f"💰 Daromad:  *{d['total_income']:,.0f} so'm*",
        f"💸 Xarajat:  *{d['total_expense']:,.0f} so'm*",
        f"⚖️ Balans:   *{sign}{balance:,.0f} so'm*",
    ]
    if d['transactions']:
        lines.append("\\n📋 *Tranzaksiyalar va Eslatmalar:*")
        for tx in d['transactions'][-10:]:
            tx_type = tx.get('type', 'expense')
            desc    = tx.get('description', '')
            if tx_type == 'note':
                lines.append(f"📝 _(eslatma)_ {desc}")
            else:
                icon = '➕' if tx_type == 'income' else '➖'
                lines.append(f"{icon} {tx['amount']:,.0f} so'm — _{desc}_")
    if d['todos']:
        lines.append("\\n📋 *Vazifalar:*")
        for i, t in enumerate(d['todos'], 1):
            check = '✅' if t['done'] else '⬜'
            lines.append(f"{check} {i}. {t['task']}")
    return '\\n'.join(lines)'''

new_summ = '''\
    bal_emoji = '😍' if balance > 100000 else ('😊' if balance >= 0 else '😰')
    lines   = [
        f"📊 *Bugungi Hisobot* 📅 {today}\\n",
        f"💰 Daromad:  *{d['total_income']:,.0f} so'm* 🤩",
        f"💸 Xarajat:  *{d['total_expense']:,.0f} so'm* 😤",
        f"⚖️ Balans:   *{sign}{balance:,.0f} so'm* {bal_emoji}",
    ]
    if d['transactions']:
        lines.append("\\n📋 *Bugungi harakatlar:*")
        for tx in d['transactions'][-10:]:
            tx_type = tx.get('type', 'expense')
            desc    = tx.get('description', '')
            if tx_type == 'note':
                lines.append(f"📝 _(eslatma)_ {desc}")
            else:
                icon = '🟢' if tx_type == 'income' else '🔴'
                lines.append(f"{icon} {tx['amount']:,.0f} so'm — _{desc}_")
    if d['todos']:
        done  = sum(1 for t in d['todos'] if t['done'])
        total = len(d['todos'])
        lines.append(f"\\n✅ *Vazifalar:* {done}/{total} bajarildi {'🏆' if done == total else '💪'}")
        for i, t in enumerate(d['todos'], 1):
            check = '✅' if t['done'] else '⬜'
            lines.append(f"{check} {i}. {t['task']}")
    if not d['transactions'] and not d['todos']:
        lines.append("\\n🌅 _Bugun hali hech narsa yo'q. Yangi kun — yangi imkoniyat!_ ✨")
    return '\\n'.join(lines)'''
src = src.replace(old_summ, new_summ, 1)

# ── 8. cmd_start welcome ─────────────────────────────────────────────────
old_start = "            return (f\"👋 *Kunlik Moliya Botiga xush kelibsiz!*\\n\\n\""
new_start = "            return (f\"🎉 *Kunlik Moliya Botiga xush kelibsiz!* 🌟\\n\\n\""
src = src.replace(old_start, new_start, 1)

old_start2 = "                    f\"⚖️ Bugungi balansiz: *{sign}{bal:,.0f} so'm*\\n\\n\""
new_start2 = "                    f\"⚖️ Bugungi balansiz: *{sign}{bal:,.0f} so'm* {'😍' if bal >= 0 else '😰'}\\n\\n\""
src = src.replace(old_start2, new_start2, 1)

# ── 9. bot started message ───────────────────────────────────────────────
old_started = "            \"✅ *Bot ishga tushdi!*\\n\\nMenyuni ochish uchun /menu bosing 👇\","
new_started = "            \"🚀 *Bot ishga tushdi!* 🎉\\n\\nSalom! Men sizning moliyaviy yordamchingizman! 😊\\n\\nMenyuni ochish uchun /menu bosing 👇\","
src = src.replace(old_started, new_started, 1)

# ── 10. NLP fallback ─────────────────────────────────────────────────────
old_nlp = "            return (\"🤔 Tushunmadim.\\n\\n*Sinab ko'ring:*\\n\\n\""
new_nlp = "            return (\"🤔 *Hmm, tushunmadim...*\\n\\nXavotir olmang! Mana misollar:\\n\\n\""
src = src.replace(old_nlp, new_nlp, 1)

# ── 11. Note saved message ───────────────────────────────────────────────
old_note = "                self.send_msg(cid, f\"📝 *Eslatma saqlandi!*\\n\\n_{text}_\\n\\n_(Balans o'zgarmadi)_\","
new_note = "                self.send_msg(cid, f\"📝 *Eslatma saqlandi!* ✨\\n\\n_{text}_\\n\\n💚 _(Balans o'zgarmadi — bu shunchaki yodgorlik)_\","
src = src.replace(old_note, new_note, 1)

# ── Write back ────────────────────────────────────────────────────────────
with open('daily_calculationbot.py', 'w', encoding='utf-8') as f:
    f.write(src)

print("✅ Patch applied successfully!")
