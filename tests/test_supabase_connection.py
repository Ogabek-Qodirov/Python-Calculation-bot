"""Full read/write/delete round-trip test for Supabase."""
import sys, os, datetime
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

TEST_CHAT_ID = "test_999999999"
test_data = {
    "2026-09-20": {
        "total_income": 500000,
        "total_expense": 50000,
        "balance": 450000,
        "transactions": [{"type": "income", "amount": 500000, "description": "test maosh"}],
        "todos": [{"task": "Test vazifa", "done": False}]
    }
}

print("1. Writing test data...")
res = client.table('user_data').upsert({
    'chat_id': TEST_CHAT_ID,
    'data': test_data,
    'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()
}).execute()
print(f"   Write OK: {len(res.data)} row(s) upserted")

print("2. Reading back...")
res = client.table('user_data').select('data').eq('chat_id', TEST_CHAT_ID).execute()
loaded = res.data[0]['data']
assert loaded['2026-09-20']['balance'] == 450000, "Data mismatch!"
print(f"   Read OK: balance = {loaded['2026-09-20']['balance']:,} so'm")

print("3. Deleting test row...")
client.table('user_data').delete().eq('chat_id', TEST_CHAT_ID).execute()
res = client.table('user_data').select('chat_id').eq('chat_id', TEST_CHAT_ID).execute()
assert len(res.data) == 0, "Delete failed!"
print(f"   Delete OK: row gone")

print("\nAll Supabase tests passed! Bot is ready to use Supabase.")
