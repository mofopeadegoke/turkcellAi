import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

try:
    print("🔌 Connecting to Supabase...")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    
    # Test query
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"✅ Connected! PostgreSQL version: {version['version']}")
    
    # Check if vector extension exists
    cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
    vector_ext = cursor.fetchone()
    if vector_ext:
        print("✅ Vector extension is enabled!")
    else:
        print("⚠️  Vector extension not found. Run: CREATE EXTENSION vector;")
    
    # List all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    print(f"\n📋 Found {len(tables)} tables:")
    for table in tables:
        print(f"   • {table['table_name']}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\n💡 Troubleshooting:")
    print("   1. Check your DATABASE_URL in .env")
    print("   2. Make sure your IP is allowed in Supabase (Settings → Database → Connection Pooling)")
    print("   3. Verify password is correct")