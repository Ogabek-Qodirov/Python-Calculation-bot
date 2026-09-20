import os
import re
import sys
import json
import time
import datetime
import logging
import requests
from flask import Flask, jsonify, request
import threading
import io
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')

telegram_bot = None


def build_webhook_path(token):
    if not token:
        return '/'
    return f'/{token}'


def build_webhook_url(base_url, token):
    if not base_url:
        return None
    cleaned = base_url.rstrip('/')
    path = build_webhook_path(token)
    if path == '/':
        return cleaned
    if cleaned.endswith(path):
        return cleaned
    return f"{cleaned}{path}"


@app.route('/')
def home():
    return "I'm alive!"


def register_webhook_route():
    path = build_webhook_path(TELEGRAM_BOT_TOKEN)
    if path == '/':
        return

    @app.route(path, methods=['POST'])
    def webhook():
        global telegram_bot
        if telegram_bot is None:
            return jsonify({'ok': False, 'error': 'bot not initialized'}), 500
        payload = request.get_json(silent=True) or {}
        if payload:
            telegram_bot.handle_message(payload)
        return jsonify({'ok': True})


register_webhook_route()


def run_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = 'user_data'
os.makedirs(DATA_DIR, exist_ok=True)

# ── NLP ────────────────────────────────────────────────────────────────────
EXPENSE_KEYWORDS = [
    'bought','spent','paid','ate','drank','purchased','got','ordered',
    'subscribed','rented','hired','fee','bill','cost','price',
    'sotib','xarajat','yedim','ichdim',"to'ladim",'berdim',
]
INCOME_KEYWORDS = [
    'earned','received','got paid','salary','income','profit','bonus',
    'dividend','refund','sold','transfer','deposited','freelance',
    'oldim','ishlab topdim','maosh','daromad','sotdim','topdim',
]
TODO_KEYWORDS = [
    'should','need to','have to','must','going to','want to',
    'plan to','will',"i'll",'remember to',"don't forget",
    'kerak','borish kerak','qilish kerak','eslatma','unutma',
    'boray','qilay','boraman','qilaman','eslab qol','yodda tut',
]

AMOUNT_PATTERN = re.compile(
    r"(\d[\d\s,\.]*\d|\d+)\s*(sum|so\'m|som|uzs)?", re.IGNORECASE
)

def parse_amount(text):
    for raw, _ in AMOUNT_PATTERN.findall(text):
        cleaned = raw.replace(' ','').replace(',','').replace('.','')
        try:    return float(cleaned)
        except: continue
    return None

def parse_natural_language(text):
    tl     = text.lower()
    amount = parse_amount(tl)
    if amount is None:
        return None, None, text
    is_expense = any(kw in tl for kw in EXPENSE_KEYWORDS)
    is_income  = any(kw in tl for kw in INCOME_KEYWORDS)
    tx_type = 'income' if (is_income and not is_expense) else 'expense'
    return tx_type, amount, text

def is_todo_message(text):
    return any(kw in text.lower() for kw in TODO_KEYWORDS)

# ── Per-User Data ───────────────────────────────────────────────────────────
def _user_file(cid):
    return os.path.join(DATA_DIR, f'{cid}.json')

def load_user_data(cid):
    path = _user_file(cid)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Fayl buzilgan ({cid}), yangidan boshlanmoqda.")
    return {}

def save_user_data(cid, data):
    with open(_user_file(cid), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_today():
    return datetime.date.today().strftime('%Y-%m-%d')

def ensure_today(data):
    today = get_today()
    if today not in data:
        data[today] = {
            'total_income':  0,
            'total_expense': 0,
            'balance':       0,
            'transactions':  [],
            'todos':         [],
        }
    if 'todos' not in data[today]:
        data[today]['todos'] = []
    return today

# ── Transactions ────────────────────────────────────────────────────────────
def add_transaction(tx_type, amount, description, data):
    today = ensure_today(data)
    if tx_type == 'income':
        data[today]['total_income'] += amount
        data[today]['balance']      += amount
    else:
        data[today]['total_expense'] += amount
        data[today]['balance']       -= amount
    data[today]['transactions'].append({
        'type':        tx_type,
        'amount':      amount,
        'description': description,
        'timestamp':   datetime.datetime.now().isoformat(),
    })
    balance = data[today]['balance']
    sign    = '+' if balance >= 0 else ''
    if tx_type == 'income':
        return (
            f"🟢 *Daromad qo'shildi!*\n"
            f"📝 _{description}_\n"
            f"💵 Miqdor: *{amount:,.0f} so'm*\n\n"
            f"⚖️ Bugungi balans: *{sign}{balance:,.0f} so'm*"
        )
    else:
        return (
            f"🔴 *Xarajat qo'shildi!*\n"
            f"📝 _{description}_\n"
            f"💵 Miqdor: *{amount:,.0f} so'm*\n\n"
            f"⚖️ Bugungi balans: *{sign}{balance:,.0f} so'm*"
        )

# ── To-Do & Markdown Notes ──────────────────────────────────────────────────
def add_todo(task_text, data):
    today = ensure_today(data)
    todos = data[today]['todos']
    todos.append({'task': task_text, 'done': False,
                  'created': datetime.datetime.now().isoformat()})
    idx = len(todos)
    return (
        f"✅ *Vazifa saqlandi!*\n"
        f"_{task_text}_\n\n"
        f"📋 Jami vazifalar soni: *{idx} ta*"
    )

def list_todos(data):
    today = ensure_today(data)
    todos = data[today]['todos']
    if not todos:
        return (
            "📋 Bugun hali hech qanday vazifa kiritilmadi.\n\n"
            "Yangi vazifa qo'shish uchun quyidagi tugmani bosing 👇"
        )
    done_count = sum(1 for t in todos if t['done'])
    total      = len(todos)
    lines      = [f"📋 *Bugungi Vazifalar* ({done_count}/{total} bajarildi)\n"]
    for i, t in enumerate(todos, 1):
        check = '✅' if t['done'] else '⬜'
        lines.append(f"{check} {i}. {t['task']}")
    if done_count == total and total > 0:
        lines.append("\n✅ *Barcha vazifalar bajarildi.*")
    elif done_count > 0:
        lines.append(f"\nℹ️ *{done_count}/{total} ta vazifa bajarildi.*")
    else:
        lines.append("\nℹ️ _Bajarish uchun vazifani tanlang._")
    return '\n'.join(lines)

def complete_todo(num, data):
    today = ensure_today(data)
    todos = data[today]['todos']
    if num < 1 or num > len(todos):
        return f"⚠️ #{num}-sonli vazifa topilmadi. Jami: {len(todos)} ta vazifa bor."
    todos[num - 1]['done'] = True
    return (
        f"✅ *#{num}-sonli vazifa bajarildi:*\n"
        f"_{todos[num-1]['task']}_"
    )

def delete_todo(num, data):
    today = ensure_today(data)
    todos = data[today]['todos']
    if num < 1 or num > len(todos):
        return f"⚠️ #{num}-sonli vazifa topilmadi."
    removed = todos.pop(num - 1)
    return f"🗑️ #{num}-sonli vazifa o'chirildi:\n_'{removed['task']}'_"

# ── Markdown (.md) File System ──────────────────────────────────────────────
def generate_md_content(data, today=None):
    if today is None:
        today = get_today()
    d = data.get(today, {'todos': [], 'transactions': [], 'balance': 0, 'total_income': 0, 'total_expense': 0})
    todos = d.get('todos', [])
    txs   = d.get('transactions', [])
    bal   = d.get('balance', 0)
    sign  = '+' if bal >= 0 else ''

    lines = [
        f"# 📋 Bugungi Vazifalar va Qaydlar — {today}",
        "",
        f"**Kunlik Balans:** `{sign}{bal:,.0f} so'm` | **Daromad:** `{d.get('total_income',0):,.0f} so'm` | **Xarajat:** `{d.get('total_expense',0):,.0f} so'm`",
        "",
        "## 📋 Vazifalar Ro'yxati",
    ]
    if todos:
        for i, t in enumerate(todos, 1):
            check = "x" if t.get('done') else " "
            lines.append(f"- [{check}] {i}. {t.get('task','')}")
    else:
        lines.append("_Bugun hali vazifalar kiritilmadi._")

    lines.extend([
        "",
        "## 📝 Kunlik Qaydlar va Amallar",
    ])

    if txs:
        for tx in txs:
            tt   = tx.get('type', 'expense')
            desc = tx.get('description', '')
            amt  = tx.get('amount', 0)
            ts   = tx.get('timestamp', '')
            try:
                tstr = datetime.datetime.fromisoformat(ts).strftime('%H:%M')
            except Exception:
                tstr = ''
            time_prefix = f"[{tstr}] " if tstr else ""
            if tt == 'note':
                lines.append(f"- {time_prefix}📝 {desc}")
            elif tt == 'income':
                lines.append(f"- {time_prefix}🟢 Daromad: {amt:,.0f} so'm — {desc}")
            else:
                lines.append(f"- {time_prefix}🔴 Xarajat: {amt:,.0f} so'm — {desc}")
    else:
        lines.append("_Bugun hali qaydlar kiritilmadi._")

    lines.extend([
        "",
        "---",
        f"*Hujjat yaratilgan vaqti: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "*Kunlik Moliya va Vazifalar Boti*"
    ])

    return "\n".join(lines)


def save_user_md_file(cid, data, today=None):
    if today is None:
        today = get_today()
    content = generate_md_content(data, today)
    md_path = os.path.join(DATA_DIR, f"{cid}_vazifalar_{today}.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return md_path, content

# ── Summary ─────────────────────────────────────────────────────────────────
def show_summary(data):
    today   = ensure_today(data)
    d       = data[today]
    balance = d['balance']
    sign    = '+' if balance >= 0 else ''
    lines = [
        f"📊 *Bugungi Hisobot* — {today}\n",
        f"💰 Daromad:  *{d['total_income']:,.0f} so'm*",
        f"💸 Xarajat:  *{d['total_expense']:,.0f} so'm*",
        f"⚖️ Balans:   *{sign}{balance:,.0f} so'm*",
    ]
    if d['transactions']:
        lines.append("\n📝 *Bugungi amallar:*")
        for tx in d['transactions'][-10:]:
            tt   = tx.get('type','expense')
            desc = tx.get('description','')
            if tt == 'note':
                lines.append(f"📝 _(eslatma)_ {desc}")
            else:
                icon = '🟢' if tt == 'income' else '🔴'
                lines.append(f"{icon} {tx['amount']:,.0f} so'm — _{desc}_")
    if d['todos']:
        done  = sum(1 for t in d['todos'] if t['done'])
        total = len(d['todos'])
        lines.append(f"\n📋 *Vazifalar:* {done}/{total} bajarildi")
        for i, t in enumerate(d['todos'], 1):
            check = '✅' if t['done'] else '⬜'
            lines.append(f"{check} {i}. {t['task']}")
    if not d['transactions'] and not d['todos']:
        lines.append("\nℹ️ _Bugun hali hech qanday ma'lumot kiritilmadi._")
    return '\n'.join(lines)

def show_weekly_summary(data):
    today    = datetime.date.today()
    start    = today - datetime.timedelta(days=today.weekday())
    total_in = total_ex = 0
    lines    = ["📊 *Haftalik Hisobot*\n"]
    for i in range(7):
        d = (start + datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        if d in data:
            day_data = data[d]
            total_in += day_data['total_income']
            total_ex += day_data['total_expense']
            bal  = day_data['balance']
            sign = '+' if bal >= 0 else ''
            lines.append(f"📅 {d}: {sign}{bal:,.0f} so'm")
    bal  = total_in - total_ex
    sign = '+' if bal >= 0 else ''
    lines += [
        f"\n💰 Jami Daromad:   *{total_in:,.0f} so'm*",
        f"💸 Jami Xarajat:   *{total_ex:,.0f} so'm*",
        f"⚖️ Haftalik Balans: *{sign}{bal:,.0f} so'm*",
    ]
    return '\n'.join(lines)

def show_monthly_summary(data):
    today    = datetime.date.today()
    month    = today.strftime('%Y-%m')
    total_in = total_ex = 0
    for d, di in data.items():
        if d.startswith(month):
            total_in += di['total_income']
            total_ex += di['total_expense']
    bal  = total_in - total_ex
    sign = '+' if bal >= 0 else ''
    return (
        f"📊 *Oylik Hisobot* — {month}\n\n"
        f"💰 Daromad:  *{total_in:,.0f} so'm*\n"
        f"💸 Xarajat:  *{total_ex:,.0f} so'm*\n"
        f"⚖️ Balans:   *{sign}{bal:,.0f} so'm*"
    )

# ── Excel ────────────────────────────────────────────────────────────────────
def generate_excel(data, period='today'):
    if not EXCEL_AVAILABLE:
        return None, "openpyxl o'rnatilmagan. Bajaring: pip install openpyxl"

    wb = openpyxl.Workbook()

    header_font  = Font(bold=True, color='FFFFFF', size=11)
    income_fill  = PatternFill('solid', fgColor='27AE60')
    expense_fill = PatternFill('solid', fgColor='E74C3C')
    note_fill    = PatternFill('solid', fgColor='3498DB')
    header_fill  = PatternFill('solid', fgColor='2C3E50')
    alt_fill     = PatternFill('solid', fgColor='ECF0F1')
    center       = Alignment(horizontal='center', vertical='center')
    thin         = Side(style='thin', color='BDC3C7')
    border       = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_header(cell, fill=None):
        cell.font      = header_font
        cell.fill      = fill or header_fill
        cell.alignment = center
        cell.border    = border

    def style_cell(cell, alt=False):
        if alt: cell.fill = alt_fill
        cell.alignment = center
        cell.border    = border

    today = get_today()
    if period == 'today':
        dates = [today]; title = f"Kunlik Hisobot — {today}"
    elif period == 'week':
        base  = datetime.date.today()
        start = base - datetime.timedelta(days=base.weekday())
        dates = [(start + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        title = f"Haftalik Hisobot — {start}"
    elif period == 'month':
        base  = datetime.date.today(); month = base.strftime('%Y-%m')
        dates = sorted([d for d in data if d.startswith(month)])
        title = f"Oylik Hisobot — {month}"
    else:
        dates = sorted(data.keys()); title = "Barcha Hisobot"

    ws = wb.active
    ws.title = "Tranzaksiyalar"; ws.sheet_properties.tabColor = "2C3E50"
    ws.merge_cells('A1:F1')
    ws['A1'].value     = f"💰 {title}"
    ws['A1'].font      = Font(bold=True, size=14, color='FFFFFF')
    ws['A1'].fill      = header_fill; ws['A1'].alignment = center
    ws.row_dimensions[1].height = 30

    headers = ["Sana","Vaqt","Tur","Miqdor (so'm)","Tavsif","Balans"]
    ws.append([]); ws.row_dimensions[2].height = 5
    ws.append(headers)
    for col, h in enumerate(headers, 1):
        style_header(ws.cell(row=3, column=col, value=h))
    ws.row_dimensions[3].height = 22

    row_num = 4; running_balance = 0; txs = []
    for date in dates:
        if date in data:
            for tx in data[date]['transactions']:
                ts = tx.get('timestamp','')
                try:   tstr = datetime.datetime.fromisoformat(ts).strftime('%H:%M')
                except: tstr = ''
                txs.append((date, tstr, tx))

    for i, (date, tstr, tx) in enumerate(txs):
        alt = (i % 2 == 1); tt = tx.get('type','expense')
        if tt == 'income':   running_balance += tx['amount']; lbl = "🟢 Daromad"
        elif tt == 'note':   lbl = "📝 Eslatma"
        else:                running_balance -= tx['amount']; lbl = "🔴 Xarajat"
        ws.append([date, tstr, lbl, tx['amount'] if tt != 'note' else 0,
                   tx.get('description',''), running_balance])
        for col in range(1, 7): style_cell(ws.cell(row=row_num, column=col), alt)
        tc      = ws.cell(row=row_num, column=3)
        tc.fill = income_fill if tt == 'income' else (note_fill if tt == 'note' else expense_fill)
        tc.font = Font(bold=True, color='FFFFFF')
        ws.cell(row=row_num, column=4).number_format = '#,##0'
        ws.cell(row=row_num, column=6).number_format = '#,##0'
        row_num += 1

    for col, w in zip('ABCDEF', [14,10,14,18,40,18]):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("Hisobot"); ws2.sheet_properties.tabColor = "27AE60"
    ws2.merge_cells('A1:C1')
    ws2['A1'].value = "📊 Kunlar bo'yicha Hisobot"
    ws2['A1'].font  = Font(bold=True, size=13, color='FFFFFF')
    ws2['A1'].fill  = header_fill; ws2['A1'].alignment = center
    ws2.row_dimensions[1].height = 28
    ws2.append([]); ws2.append(["Sana","Daromad (so'm)","Xarajat (so'm)","Balans (so'm)"])
    for col in range(1, 5): style_header(ws2.cell(row=3, column=col))
    ws2.row_dimensions[3].height = 22

    total_in = total_ex = 0
    for i, date in enumerate(dates):
        if date in data:
            day_data = data[date]; total_in += day_data['total_income']; total_ex += day_data['total_expense']
            ws2.append([date, day_data['total_income'], day_data['total_expense'], day_data['balance']])
            ri = 4 + i
            for col in range(1,5): style_cell(ws2.cell(row=ri, column=col), i % 2 == 1)
            for col in [2,3,4]: ws2.cell(row=ri, column=col).number_format = '#,##0'
            ws2.cell(row=ri, column=4).font = Font(bold=True,
                color='27AE60' if day_data['balance'] >= 0 else 'E74C3C')

    tr = 4 + len(dates)
    ws2.append(['JAMI', total_in, total_ex, total_in - total_ex])
    for col in range(1,5):
        c = ws2.cell(row=tr, column=col)
        c.font = Font(bold=True, color='FFFFFF'); c.fill = header_fill
        c.border = border; c.alignment = center
    for col in [2,3,4]: ws2.cell(row=tr, column=col).number_format = '#,##0'
    for col, w in zip('ABCD', [14,18,18,18]): ws2.column_dimensions[col].width = w

    ws3 = wb.create_sheet("Vazifalar"); ws3.sheet_properties.tabColor = "E67E22"
    ws3.merge_cells('A1:C1')
    ws3['A1'].value = "📋 Vazifalar Ro'yxati"
    ws3['A1'].font  = Font(bold=True, size=13, color='FFFFFF')
    ws3['A1'].fill  = PatternFill('solid', fgColor='E67E22'); ws3['A1'].alignment = center
    ws3.row_dimensions[1].height = 28
    ws3.append([]); ws3.append(['#','Vazifa','Holat','Sana'])
    for col in range(1,5):
        style_header(ws3.cell(row=3,column=col), PatternFill('solid',fgColor='E67E22'))
    ws3.row_dimensions[3].height = 22

    task_row = 4
    for date in dates:
        if date in data:
            for j, todo in enumerate(data[date].get('todos',[]), 1):
                status = '✅ Bajarildi' if todo['done'] else '⬜ Kutilmoqda'
                ws3.append([j, todo['task'], status, date])
                for col in range(1,5): style_cell(ws3.cell(row=task_row,column=col), task_row % 2 == 1)
                ws3.cell(row=task_row,column=3).font = Font(
                    color='27AE60' if todo['done'] else 'E74C3C', bold=True)
                task_row += 1
    for col, w in zip('ABCD', [6,45,18,14]): ws3.column_dimensions[col].width = w

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf, None

# ── Telegram Bot ─────────────────────────────────────────────────────────────
class TelegramBot:
    def __init__(self):
        self.user_cache     = {}
        self.user_states    = {}
        self.last_update_id = 0
        self.base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        logger.info("Bot ishga tushdi ✅")

    STATE_IDLE            = 'idle'
    STATE_TODO_ADD        = 'todo_add'
    STATE_JOURNAL_INCOME  = 'journal_income'
    STATE_JOURNAL_EXPENSE = 'journal_expense'
    STATE_JOURNAL_NOTE    = 'journal_note'

    def get_state(self, c): return self.user_states.get(c, self.STATE_IDLE)
    def set_state(self, c, s): self.user_states[c] = s
    def clear_state(self, c): self.user_states[c] = self.STATE_IDLE

    def get_data(self, cid):
        if cid not in self.user_cache:
            self.user_cache[cid] = load_user_data(cid)
        return self.user_cache[cid]

    def save(self, cid): save_user_data(cid, self.user_cache[cid])

    # ── Keyboards ─────────────────────────────────────────────────────────
    def kb_main(self):
        return {"inline_keyboard": [
            [{"text":"📋 Vazifalar (.md)",       "callback_data":"todo_menu"},
             {"text":"📝 Qayd / Kundalik",     "callback_data":"journal_menu"}],
            [{"text":"📊 Hisobot",             "callback_data":"cmd_summary"},
             {"text":"📁 Excel Yuklash",       "callback_data":"cmd_excel"}],
        ]}

    def kb_todo(self):
        return {"inline_keyboard": [
            [{"text":"➕ Vazifa / Qayd Qo'shish",    "callback_data":"todo_add"}],
            [{"text":"📄 .md Faylni Yuklash",       "callback_data":"todo_download_md"}],
            [{"text":"📋 Vazifalarni Ko'rish",       "callback_data":"todo_view"}],
            [{"text":"✏️ O'zgartirish",              "callback_data":"todo_changes"}],
            [{"text":"🏠 Asosiy Menyu",              "callback_data":"main_menu"}],
        ]}

    def kb_journal(self):
        return {"inline_keyboard": [
            [{"text":"🟢 Daromad Qo'shish (+)",       "callback_data":"journal_income"}],
            [{"text":"🔴 Xarajat Qo'shish (−)",      "callback_data":"journal_expense"}],
            [{"text":"📝 Qayd Yozish",                "callback_data":"journal_note"}],
            [{"text":"🏠 Asosiy Menyu",               "callback_data":"main_menu"}],
        ]}

    def kb_changes(self, todos):
        rows = []
        for i, t in enumerate(todos, 1):
            icon  = '✅' if t['done'] else '⬜'
            label = t['task'][:22] + '…' if len(t['task']) > 22 else t['task']
            rows.append([
                {"text":f"{icon} {i}. {label}", "callback_data":f"todo_toggle_{i}"},
                {"text":"🗑️ O'chirish",          "callback_data":f"todo_del_{i}"},
            ])
        rows.append([{"text":"⬅️ Orqaga",            "callback_data":"todo_menu"},
                     {"text":"🏠 Asosiy Menyu",      "callback_data":"main_menu"}])
        return {"inline_keyboard": rows}

    def kb_back(self):
        return {"inline_keyboard": [[{"text":"🏠 Asosiy Menyu","callback_data":"main_menu"}]]}

    def kb_after_todo(self):
        return {"inline_keyboard": [
            [{"text":"➕ Yana Qo'shish",              "callback_data":"todo_add"},
             {"text":"📄 .md Yuklash",                "callback_data":"todo_download_md"}],
            [{"text":"📋 Vazifalarni Ko'rish",       "callback_data":"todo_view"}],
            [{"text":"🏠 Asosiy Menyu",              "callback_data":"main_menu"}],
        ]}

    def kb_after_tx(self):
        return {"inline_keyboard": [
            [{"text":"🟢 Daromad","callback_data":"journal_income"},
             {"text":"🔴 Xarajat","callback_data":"journal_expense"}],
            [{"text":"📝 Qayd",   "callback_data":"journal_note"},
             {"text":"🏠 Asosiy", "callback_data":"main_menu"}],
        ]}

    # ── Telegram API ──────────────────────────────────────────────────────
    def set_webhook(self, url):
        try:
            r = requests.post(f"{self.base_url}/setWebhook",
                              data={'url': url, 'drop_pending_updates': True}, timeout=20)
            payload = r.json()
            if payload.get('ok'):
                logger.info(f"Webhook o'rnatildi: {url}")
            else:
                logger.warning(f"Webhook xato: {payload}")
            return payload
        except Exception as e:
            logger.warning(f"Webhook xato: {e}")
            return None

    def delete_webhook(self):
        try:
            r = requests.post(f"{self.base_url}/deleteWebhook",
                              data={'drop_pending_updates': False}, timeout=10)
            if r.json().get('result'): logger.info("Webhook o'chirildi ✅")
        except Exception as e: logger.warning(f"Webhook xato: {e}")

    def get_updates(self):
        try:
            r = requests.get(f"{self.base_url}/getUpdates",
                             params={'offset': self.last_update_id + 1, 'timeout': 30},
                             timeout=35)
            r.raise_for_status(); return r.json().get('result', [])
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 409:
                logger.warning("409 Conflict — webhook o'chirilmoqda...")
                self.delete_webhook(); time.sleep(5)
            else: logger.error(f"get_updates HTTP xato: {e}")
            return []
        except Exception as e: logger.error(f"get_updates xato: {e}"); return []

    def send_msg(self, cid, text, kb=None):
        try:
            d = {'chat_id': cid, 'text': text, 'parse_mode': 'Markdown'}
            if kb: d['reply_markup'] = json.dumps(kb)
            requests.post(f"{self.base_url}/sendMessage", data=d, timeout=10)
        except Exception as e: logger.error(f"send_msg xato: {e}")

    def edit_msg(self, cid, mid, text, kb=None):
        try:
            d = {'chat_id': cid, 'message_id': mid, 'text': text, 'parse_mode': 'Markdown'}
            if kb: d['reply_markup'] = json.dumps(kb)
            requests.post(f"{self.base_url}/editMessageText", data=d, timeout=10)
        except Exception as e: logger.error(f"edit_msg xato: {e}")

    def answer_cb(self, cbid):
        try:
            requests.post(f"{self.base_url}/answerCallbackQuery",
                          data={'callback_query_id': cbid}, timeout=10)
        except Exception as e: logger.error(f"answer_cb xato: {e}")

    def send_doc(self, cid, buf, fname, caption='', mime='application/octet-stream'):
        try:
            requests.post(f"{self.base_url}/sendDocument",
                          data={'chat_id': cid, 'caption': caption, 'parse_mode': 'Markdown'},
                          files={'document': (fname, buf, mime)},
                          timeout=30)
        except Exception as e: logger.error(f"send_doc xato: {e}")

    def send_md_doc(self, cid, data, today=None):
        if today is None:
            today = get_today()
        md_path, content = save_user_md_file(cid, data, today)
        buf = io.BytesIO(content.encode('utf-8'))
        fname = f"vazifalar_{today}.md"
        caption = f"📄 *Vazifalar va Qaydlar (.md)*\n_{today}_"
        self.send_doc(cid, buf, fname, caption=caption, mime='text/markdown')

    # ── Callback handler ──────────────────────────────────────────────────
    def handle_cb(self, update):
        cq = update.get('callback_query')
        if not cq: return
        cbid = cq['id']; cid = cq['message']['chat']['id']
        mid  = cq['message']['message_id']; cb = cq.get('data','')
        self.answer_cb(cbid); self.last_update_id = update['update_id']
        data = self.get_data(cid); ensure_today(data)

        if cb == 'main_menu':
            self.clear_state(cid)
            self.edit_msg(cid, mid,
                "🏠 *Asosiy Menyu*\n\nKerakli bo'limni tanlang:", self.kb_main())

        elif cb == 'todo_menu':
            self.clear_state(cid)
            self.edit_msg(cid, mid,
                "📋 *Vazifalar va Qaydlar (.md)*\n\nQuyidagi bo'limni tanlang yoki `.md` faylingizni yuklab oling:", self.kb_todo())
            self.send_md_doc(cid, data)

        elif cb == 'todo_download_md':
            self.send_md_doc(cid, data)
            self.edit_msg(cid, mid,
                "📄 *Vazifalar (.md) fayli yuborildi!*", self.kb_todo())

        elif cb == 'todo_add':
            self.set_state(cid, self.STATE_TODO_ADD)
            self.edit_msg(cid, mid,
                "📝 *Vazifa / Qayd Qo'shish*\n\n"
                "Vazifa yoki kunlik qaydingizni yozing 👇\n\n"
                "_Misol: Bugungi loyihani tugatish_\n"
                "_Misol: Soat 15:00 da uchrashuv_")

        elif cb == 'todo_view':
            bk = {"inline_keyboard": [
                [{"text":"📄 .md Faylni Yuklash","callback_data":"todo_download_md"}],
                [{"text":"✏️ O'zgartirish",      "callback_data":"todo_changes"}],
                [{"text":"⬅️ Orqaga",            "callback_data":"todo_menu"},
                 {"text":"🏠 Asosiy Menyu",      "callback_data":"main_menu"}],
            ]}
            self.edit_msg(cid, mid, list_todos(data), bk)
            self.send_md_doc(cid, data)

        elif cb == 'todo_changes':
            todos = data[get_today()]['todos']
            if not todos:
                self.edit_msg(cid, mid,
                    "📋 Bugun hali vazifalar kiritilmadi.",
                    {"inline_keyboard": [
                        [{"text":"➕ Vazifa Qo'shish","callback_data":"todo_add"}],
                        [{"text":"🏠 Asosiy Menyu",   "callback_data":"main_menu"}],
                    ]})
            else:
                self.edit_msg(cid, mid,
                    "✏️ *Vazifalarni Boshqarish*\n\n"
                    "Holatni o'zgartirish uchun vazifani bosing (✅/⬜).\n"
                    "O'chirish uchun 🗑️ tugmasini bosing:",
                    self.kb_changes(todos))

        elif cb.startswith('todo_toggle_'):
            num = int(cb.split('_')[2]); today = get_today()
            todos = data[today]['todos']
            if 1 <= num <= len(todos):
                todos[num-1]['done'] = not todos[num-1]['done']; self.save(cid)
                save_user_md_file(cid, data, today)
            self.edit_msg(cid, mid,
                "✏️ *Vazifalarni Boshqarish*\n\n"
                "Holatni o'zgartirish uchun vazifani bosing (✅/⬜).\n"
                "O'chirish uchun 🗑️ tugmasini bosing:",
                self.kb_changes(data[today]['todos']))

        elif cb.startswith('todo_del_'):
            num = int(cb.split('_')[2]); today = get_today()
            todos = data[today]['todos']
            if 1 <= num <= len(todos):
                todos.pop(num-1); self.save(cid)
                save_user_md_file(cid, data, today)
            remaining = data[today]['todos']
            if remaining:
                self.edit_msg(cid, mid,
                    "✏️ *Vazifalarni Boshqarish*\n\n"
                    "Holatni o'zgartirish uchun vazifani bosing (✅/⬜).\n"
                    "O'chirish uchun 🗑️ tugmasini bosing:",
                    self.kb_changes(remaining))
            else:
                self.edit_msg(cid, mid,
                    "🗑️ Barcha vazifalar o'chirildi.",
                    {"inline_keyboard": [
                        [{"text":"➕ Vazifa Qo'shish","callback_data":"todo_add"}],
                        [{"text":"🏠 Asosiy Menyu",   "callback_data":"main_menu"}],
                    ]})

        elif cb == 'journal_menu':
            self.clear_state(cid)
            self.edit_msg(cid, mid,
                "📝 *Kundalik / Qaydlar*\n\nKerakli bo'limni tanlang:", self.kb_journal())

        elif cb == 'journal_income':
            self.set_state(cid, self.STATE_JOURNAL_INCOME)
            self.edit_msg(cid, mid,
                "🟢 *Daromad Qo'shish*\n\n"
                "*Miqdor* va tavsifni yozing:\n\n"
                "_Misollar:_\n"
                "• `500000 maosh`\n"
                "• `200000 freelance`\n"
                "• `1000000 bonus`")

        elif cb == 'journal_expense':
            self.set_state(cid, self.STATE_JOURNAL_EXPENSE)
            self.edit_msg(cid, mid,
                "🔴 *Xarajat Qo'shish*\n\n"
                "*Miqdor* va tavsifni yozing:\n\n"
                "_Misollar:_\n"
                "• `50000 taksi`\n"
                "• `120000 tushlik`")

        elif cb == 'journal_note':
            self.set_state(cid, self.STATE_JOURNAL_NOTE)
            self.edit_msg(cid, mid,
                "📝 *Eslatma / Qayd Yozish*\n\n"
                "Istalgan qayd yoki eslatmani yozing:\n"
                "_(Balans o'zgarmadi)_\n\n"
                "_Misollar:_\n"
                "• _Bugungi majlis soat 15:00 da boshlandi_\n"
                "• _Hujjatlar tayyorlandi_")

        elif cb == 'cmd_summary':
            self.edit_msg(cid, mid, show_summary(data), self.kb_back())

        elif cb == 'cmd_excel':
            self.edit_msg(cid, mid,
                "📁 *Excel Yuklash*\n\nDavrni tanlang:",
                {"inline_keyboard": [
                    [{"text":"📅 Bugun",       "callback_data":"excel_today"},
                     {"text":"📅 Bu Hafta",    "callback_data":"excel_week"}],
                    [{"text":"📅 Bu Oy",       "callback_data":"excel_month"},
                     {"text":"📁 Hammasi",     "callback_data":"excel_all"}],
                    [{"text":"🏠 Asosiy Menyu","callback_data":"main_menu"}],
                ]})

        elif cb.startswith('excel_'):
            period = cb.split('_',1)[1]
            names  = {'today':'Bugun','week':'Bu Hafta','month':'Bu Oy','all':'Hammasi'}
            self.edit_msg(cid, mid,
                f"⏳ *{names.get(period,period)}* uchun Excel tayyorlanmoqda…",
                self.kb_back())
            self.do_excel(cid, data, period)

    # ── Message handler ───────────────────────────────────────────────────
    def handle_message(self, update):
        if 'callback_query' in update:
            self.handle_cb(update); return
        try:
            msg  = update.get('message') or update.get('edited_message')
            if not msg: return
            cid  = msg['chat']['id']
            text = msg.get('text','').strip()
            self.last_update_id = update['update_id']
            if not text: return
            data  = self.get_data(cid)
            state = self.get_state(cid)

            if state == self.STATE_TODO_ADD:
                self.clear_state(cid); ensure_today(data)
                res_msg = add_todo(text, data)
                self.save(cid)
                save_user_md_file(cid, data)
                self.send_msg(cid, res_msg, self.kb_after_todo())
                self.send_md_doc(cid, data)
                return

            elif state == self.STATE_JOURNAL_INCOME:
                self.clear_state(cid); ensure_today(data)
                amount = parse_amount(text)
                if not amount:
                    self.send_msg(cid,
                        "⚠️ *Miqdor topilmadi!*\n\n"
                        "_Raqam kiriting. Misol: `500000 maosh`_",
                        {"inline_keyboard": [
                            [{"text":"🔄 Qayta Urinish","callback_data":"journal_income"},
                             {"text":"🏠 Asosiy Menyu", "callback_data":"main_menu"}],
                        ]})
                else:
                    self.send_msg(cid, add_transaction('income', amount, text, data),
                                  self.kb_after_tx())
                    self.save(cid)
                    save_user_md_file(cid, data)
                return

            elif state == self.STATE_JOURNAL_EXPENSE:
                self.clear_state(cid); ensure_today(data)
                amount = parse_amount(text)
                if not amount:
                    self.send_msg(cid,
                        "⚠️ *Miqdor topilmadi!*\n\n"
                        "_Raqam kiriting. Misol: `20000 tushlik`_",
                        {"inline_keyboard": [
                            [{"text":"🔄 Qayta Urinish","callback_data":"journal_expense"},
                             {"text":"🏠 Asosiy Menyu", "callback_data":"main_menu"}],
                        ]})
                else:
                    self.send_msg(cid, add_transaction('expense', amount, text, data),
                                  self.kb_after_tx())
                    self.save(cid)
                    save_user_md_file(cid, data)
                return

            elif state == self.STATE_JOURNAL_NOTE:
                self.clear_state(cid); today = ensure_today(data)
                data[today]['transactions'].append({
                    'type': 'note', 'amount': 0,
                    'description': text,
                    'timestamp': datetime.datetime.now().isoformat(),
                })
                self.save(cid)
                save_user_md_file(cid, data, today)
                self.send_msg(cid,
                    f"📝 *Eslatma saqlandi!*\n\n_{text}_\n\n"
                    "_(Balans o'zgarmadi)_",
                    {"inline_keyboard": [
                        [{"text":"📝 Yana Qayd Yozish","callback_data":"journal_note"},
                         {"text":"📄 .md Yuklash",     "callback_data":"todo_download_md"}],
                        [{"text":"📝 Kundalik",        "callback_data":"journal_menu"},
                         {"text":"🏠 Asosiy",          "callback_data":"main_menu"}],
                    ]})
                return

            resp = self.route(text, cid, data)
            if resp:
                if isinstance(resp, tuple): self.send_msg(cid, resp[0], resp[1])
                else: self.send_msg(cid, resp)
        except Exception as e:
            logger.error(f"handle_message xato: {e}")

    # ── Command router ────────────────────────────────────────────────────
    def route(self, text, cid, data):
        cmd = text.split()[0].lower()
        if   cmd in ('/start','/menu'):      return self.cmd_start(cid)
        elif cmd == '/help':                  return self.cmd_help()
        elif cmd in ('/summary','/hisobot'): return show_summary(data)
        elif cmd in ('/week','/hafta'):       return show_weekly_summary(data)
        elif cmd in ('/month','/oy'):         return show_monthly_summary(data)
        elif cmd in ('/excel','/export'):
            parts  = text.split()
            period = parts[1].lower() if len(parts) > 1 else 'today'
            if period not in ('today','week','month','all'): period = 'today'
            self.do_excel(cid, data, period); return None
        elif cmd in ('/todo','/vazifa'):
            task = text.split(' ',1)[1].strip() if ' ' in text else ''
            if not task:
                self.send_md_doc(cid, data)
                return ("📋 Vazifa yoki qaydingizni kiriting:\n"
                        "`/vazifa Loyihani yakunlash`\n\n"
                        "Yoki menyudan tanlang: /menu")
            ensure_today(data); r = add_todo(task, data); self.save(cid)
            save_user_md_file(cid, data)
            self.send_md_doc(cid, data)
            return r
        elif cmd in ('/todos', '/vazifalar'):
            self.send_md_doc(cid, data)
            return list_todos(data)
        elif cmd == '/done':
            parts = text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                return "ℹ️ Foydalanish: `/done <raqam>`\nMisol: `/done 1`"
            ensure_today(data); r = complete_todo(int(parts[1]), data)
            self.save(cid)
            save_user_md_file(cid, data)
            return r
        elif cmd == '/deltodo':
            parts = text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                return "ℹ️ Foydalanish: `/deltodo <raqam>`"
            ensure_today(data); r = delete_todo(int(parts[1]), data)
            self.save(cid)
            save_user_md_file(cid, data)
            return r
        elif cmd in ('/income','/daromad'):
            rest   = text.split(' ',1)[1].strip() if ' ' in text else ''
            amount = parse_amount(rest)
            if not amount: return "ℹ️ Foydalanish: `/daromad 500000 maosh`"
            ensure_today(data)
            r = add_transaction('income', amount, rest or 'Daromad', data)
            self.save(cid)
            save_user_md_file(cid, data)
            return r
        elif cmd in ('/expense','/xarajat'):
            rest   = text.split(' ',1)[1].strip() if ' ' in text else ''
            amount = parse_amount(rest)
            if not amount: return "ℹ️ Foydalanish: `/xarajat 20000 taksi`"
            ensure_today(data)
            r = add_transaction('expense', amount, rest or 'Xarajat', data)
            self.save(cid)
            save_user_md_file(cid, data)
            return r
        else: return self.nlp(text, cid, data)

    def nlp(self, text, cid, data):
        tx_type, amount, desc = parse_natural_language(text)
        if amount is None:
            if is_todo_message(text):
                ensure_today(data); r = add_todo(text, data)
                self.save(cid)
                save_user_md_file(cid, data)
                self.send_md_doc(cid, data)
                return r
            return (
                "⚠️ *Noma'lum buyruq.* Mana misollar:\n\n"
                "• _taksi uchun 20000 to'ladim_\n"
                "• _maosh 5000000 oldim_\n"
                "• _ertaga majlisga borish kerak_\n\n"
                "Yoki menyuni oching: /menu"
            )
        ensure_today(data); r = add_transaction(tx_type, amount, desc, data)
        self.save(cid)
        save_user_md_file(cid, data)
        return r

    # ── Excel sender ──────────────────────────────────────────────────────
    def do_excel(self, cid, data, period):
        if not EXCEL_AVAILABLE:
            self.send_msg(cid,
                "❌ openpyxl o'rnatilmagan.\nBajaring: `pip install openpyxl`")
            return
        buf, err = generate_excel(data, period)
        if err: self.send_msg(cid, f"❌ {err}"); return
        today  = get_today()
        names  = {'today':'bugun','week':'hafta','month':'oy','all':'hammasi'}
        fname  = f"hisobot_{names.get(period,period)}_{today}.xlsx"
        caption = f"📊 *Excel Hisobot* — {period}\n_{today}_"
        self.send_doc(cid, buf, fname, caption, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        logger.info(f"Excel yuborildi: {fname}")

    # ── /start ────────────────────────────────────────────────────────────
    def cmd_start(self, cid=None):
        if cid is not None:
            data  = self.get_data(cid)
            today = ensure_today(data)
            bal   = data[today]['balance']
            sign  = '+' if bal >= 0 else ''
            return (
                f"📋 *Kunlik Moliya va Vazifalar Boti*\n\n"
                f"⚖️ Bugungi balans: *{sign}{bal:,.0f} so'm*\n\n"
                "Quyidagi bo'limlardan birini tanlang 👇",
                self.kb_main()
            )
        return "Boshlash uchun /start bosing."

    def cmd_help(self):
        return (
            "📖 *Barcha Buyruqlar*\n\n"
            "━━━━ 🏠 *Menyu* ━━━━\n"
            "  `/menu` yoki `/start` — Asosiy menyu\n\n"
            "━━━━ 💰 *Moliya* ━━━━\n"
            "  _taksi uchun 20000 to'ladim_\n"
            "  _maosh 5000000 oldim_\n"
            "  `/xarajat 20000 taksi`\n"
            "  `/daromad 500000 maosh`\n\n"
            "━━━━ 📋 *Vazifalar & Qaydlar (.md)* ━━━━\n"
            "  `/vazifa <matn>` — Qo'shish\n"
            "  `/todos` — Vazifalarni ko'rish va .md yuklash\n"
            "  `/done <n>` — Bajarildi deb belgilash\n"
            "  `/deltodo <n>` — O'chirish\n\n"
            "━━━━ 📊 *Hisobotlar* ━━━━\n"
            "  `/hisobot` | `/hafta` | `/oy`\n"
            "  `/excel` — Excel yuklash\n"
        )

    # ── Run loop ──────────────────────────────────────────────────────────
    def run(self):
        logger.info("Webhook o'chirilmoqda...")
        self.delete_webhook(); time.sleep(1)
        logger.info("Bot ishlamoqda... To'xtatish uchun Ctrl+C bosing.")
        self.send_msg(
            TELEGRAM_CHAT_ID,
            "✅ *Bot ishga tushdi.*\n\n"
            "Menyuni ochish uchun /menu bosing 👇",
            self.kb_main()
        )
        while True:
            try:
                updates = self.get_updates()
                for upd in updates: self.handle_message(upd)
                time.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("Bot to'xtatildi. Xayr!"); break
            except Exception as e:
                logger.error(f"Bot loop xato: {e}"); time.sleep(5)

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN .env faylida topilmadi!")
        sys.exit(1)
    global telegram_bot
    telegram_bot = TelegramBot()
    threading.Thread(target=run_server, daemon=True).start()
    telegram_bot.run()

if __name__ == '__main__':
    main()