import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Create database connection with connection pooling"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def get_customer_by_phone(phone_number):
    """Get customer info by phone number (WhatsApp or MSISDN)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clean phone number (remove whatsapp: prefix, spaces, etc.)
    phone = phone_number.replace('whatsapp:', '').replace(' ', '').replace('+', '').strip()
    
    try:
        cursor.execute('''
            SELECT 
                c.customer_id,
                c.full_name,
                c.preferred_language,
                c.whatsapp_number,
                c.nationality,
                s.subscription_id,
                s.msisdn,
                s.status as subscription_status,
                s.activation_date,
                s.expiry_date,
                p.package_id,
                p.package_name,
                p.price_try,
                p.validity_days,
                b.data_total_mb,
                b.data_used_mb,
                b.data_remaining_mb,
                b.voice_remaining_min,
                b.balance_try
            FROM customers c
            LEFT JOIN subscriptions s ON c.customer_id = s.customer_id AND s.status = 'ACTIVE'
            LEFT JOIN packages p ON s.package_id = p.package_id
            LEFT JOIN balances b ON s.subscription_id = b.subscription_id
            WHERE c.whatsapp_number LIKE %s OR s.msisdn LIKE %s
            ORDER BY s.created_at DESC
            LIMIT 1
        ''', (f'%{phone}%', f'%{phone}%'))
        
        result = cursor.fetchone()
        return dict(result) if result else None
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def log_interaction(customer_id, channel, user_message, ai_response, intent=None, session_id=None):
    """Log AI interaction to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO interaction_history 
            (customer_id, channel, user_message, ai_response, intent_detected, session_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING interaction_id
        ''', (customer_id, channel, user_message, ai_response, intent, session_id))
        
        interaction_id = cursor.fetchone()['interaction_id']
        conn.commit()
        return interaction_id
        
    except Exception as e:
        print(f"❌ Failed to log interaction: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def search_knowledge_base(query, language='EN', limit=3):
    """Search knowledge base by keywords (without vector search for now)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, title, content, category, device_os
            FROM knowledge_base
            WHERE language = %s
            AND (
                title ILIKE %s
                OR content ILIKE %s
                OR %s = ANY(keywords)
            )
            ORDER BY helpful_count DESC, view_count DESC
            LIMIT %s
        ''', (language, f'%{query}%', f'%{query}%', query.lower(), limit))
        
        results = cursor.fetchall()
        return [dict(r) for r in results]
        
    except Exception as e:
        print(f"❌ Knowledge base search error: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def update_balance_usage(subscription_id, data_used_mb=0, voice_used_min=0, sms_used=0):
    """Update customer usage"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE balances
            SET 
                data_used_mb = data_used_mb + %s,
                voice_used_min = voice_used_min + %s,
                sms_used = sms_used + %s,
                last_updated = NOW()
            WHERE subscription_id = %s
        ''', (data_used_mb, voice_used_min, sms_used, subscription_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Failed to update balance: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def check_network_issues(region=None):
    """Check if there are ongoing network issues in a region"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if region:
            cursor.execute('''
                SELECT status_id, region, issue_type, severity, description, started_at
                FROM network_status
                WHERE status = 'ONGOING' AND region ILIKE %s
                ORDER BY severity DESC
            ''', (f'%{region}%',))
        else:
            cursor.execute('''
                SELECT status_id, region, issue_type, severity, description, started_at
                FROM network_status
                WHERE status = 'ONGOING'
                ORDER BY severity DESC
                LIMIT 5
            ''')
        
        results = cursor.fetchall()
        return [dict(r) for r in results]
        
    except Exception as e:
        print(f"❌ Network status check error: {e}")
        return []
    finally:
        cursor.close()
        conn.close()