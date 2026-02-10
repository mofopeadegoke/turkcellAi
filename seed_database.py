import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')  

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("🌱 Seeding database with test data...")

# 1. Insert Packages
print("📦 Creating packages...")
packages = [
    ('TOURIST_WELCOME_50GB', 'Tourist Welcome Pack 50GB', 400, 51200, 1000, 100, 30, 'TOURIST', 'ACTIVE'),
    ('TOURIST_STARTER_30GB', 'Tourist Starter 30GB', 300, 30720, 500, 50, 30, 'TOURIST', 'ACTIVE'),
]

for pkg in packages:
    cursor.execute('''
        INSERT INTO packages (package_id, package_name, price_try, data_mb, voice_minutes, sms_count, validity_days, package_type, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (package_id) DO NOTHING
    ''', pkg)

# 2. Insert Test Customer (USE YOUR REAL PHONE NUMBER)
print("👤 Creating test customer...")
cursor.execute('''
    INSERT INTO customers (passport_number, full_name, nationality, preferred_language, whatsapp_number, customer_type)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (whatsapp_number) DO NOTHING
    RETURNING customer_id
''', ('P12345678', 'Test User', 'American', 'EN', '+905338856528', 'TOURIST'))  # AYO'S NUMBER, NEED TO DOUBLE CHECK

result = cursor.fetchone()
if result:
    customer_id = result[0]
    print(f"   ✓ Customer created: {customer_id}")
    
    # 3. Create Subscription
    print("📱 Creating subscription...")
    cursor.execute('''
        INSERT INTO subscriptions (customer_id, package_id, msisdn, iccid, status, activation_date, expiry_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING subscription_id
    ''', (customer_id, 'TOURIST_WELCOME_50GB', '+905321234567', '8990011234567890', 'ACTIVE', 
          datetime.now(), datetime.now() + timedelta(days=25)))
    
    subscription_id = cursor.fetchone()[0]
    print(f"   ✓ Subscription created: {subscription_id}")
    
    # 4. Create Balance
    print("💰 Creating balance...")
    cursor.execute('''
        INSERT INTO balances (subscription_id, data_total_mb, data_used_mb, voice_total_min, voice_used_min, sms_total, sms_used)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (subscription_id, 51200, 12500, 1000, 145, 100, 23))
    print("   ✓ Balance created")

# 5. Insert Knowledge Base
print("📚 Creating knowledge base entries...")
# run a separate script to "embed" them using OpenAI.
kb_entries = [
    ('SIM Activation Guide', 'To activate your SIM card: 1) Insert the SIM into your phone 2) Restart your device 3) Wait 5-10 minutes for automatic activation. If it doesn\'t work, check Settings > Mobile Data is ON.', 'SIM_ACTIVATION', 'EN', 'ALL', ['sim', 'activation', 'not working', 'new card']),
    ('Internet Troubleshooting', 'If internet is not working: 1) Check Mobile Data is ON in Settings 2) Enable Data Roaming 3) Restart your phone 4) Check if you see Turkcell network name. For iPhone: Settings > Cellular. For Android: Settings > Network.', 'INTERNET_ISSUES', 'EN', 'ALL', ['internet', 'data', 'slow', 'not connecting', '4g', '5g']),
]

for title, content, category, language, device_os, keywords in kb_entries:
    cursor.execute('''
        INSERT INTO knowledge_base (title, content, category, language, device_os, keywords)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (title, content, category, language, device_os, keywords))

print("   ✓ Knowledge base created")

conn.commit()
print("\n✅ Database seeded successfully!")

cursor.close()
conn.close()