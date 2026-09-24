"""
Complete Supabase setup: add RLS policy, index, and verify table.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import psycopg2

conn = psycopg2.connect(
    host='aws-0-ap-southeast-1.pooler.supabase.com',
    port=6543,
    dbname='postgres',
    user='postgres.htnfigggnxwdnqdlnxcy',
    password='qod1rovogabek',
    sslmode='require',
    connect_timeout=10
)
conn.autocommit = True
cur = conn.cursor()

# Ensure table exists
cur.execute("""
    CREATE TABLE IF NOT EXISTS public.user_data (
        chat_id    TEXT PRIMARY KEY,
        data       JSONB NOT NULL DEFAULT '{}',
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
""")
print("Table: OK")

# Enable RLS
cur.execute("ALTER TABLE public.user_data ENABLE ROW LEVEL SECURITY;")
print("RLS enabled: OK")

# RLS policy
cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = 'user_data' AND policyname = 'Allow all for anon'
        ) THEN
            CREATE POLICY "Allow all for anon" ON public.user_data
                FOR ALL USING (true) WITH CHECK (true);
        END IF;
    END $$;
""")
print("RLS policy: OK")

# Index
cur.execute("CREATE INDEX IF NOT EXISTS idx_user_data_chat_id ON public.user_data (chat_id);")
print("Index: OK")

# Verify columns
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'user_data'
    ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print(f"\nTable columns:")
for col in cols:
    print(f"  - {col[0]} ({col[1]})")

conn.close()
print("\nSupabase setup complete!")
