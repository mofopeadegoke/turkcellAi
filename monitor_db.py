import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import time

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def monitor_interactions():
    """Monitor interaction_history table in real-time"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    
    print("👀 Monitoring database for new interactions...")
    print("   (Press Ctrl+C to stop)")
    print("="*60)
    
    last_count = 0
    
    while True:
        try:
            # Get total count
            cursor.execute("SELECT COUNT(*) as count FROM interaction_history")
            current_count = cursor.fetchone()['count']
            
            if current_count > last_count:
                # New interaction(s) detected!
                print(f"\n🔔 NEW INTERACTION DETECTED! Total: {current_count}")
                
                # Get the latest interaction
                cursor.execute("""
                    SELECT 
                        ih.timestamp,
                        ih.channel,
                        ih.user_message,
                        ih.ai_response,
                        c.full_name,
                        c.preferred_language
                    FROM interaction_history ih
                    LEFT JOIN customers c ON ih.customer_id = c.customer_id
                    ORDER BY ih.timestamp DESC
                    LIMIT 1
                """)
                
                latest = cursor.fetchone()
                
                if latest:
                    print(f"   Time: {latest['timestamp']}")
                    print(f"   Channel: {latest['channel']}")
                    print(f"   Customer: {latest['full_name'] or 'Unknown'}")
                    print(f"   Language: {latest['preferred_language'] or 'N/A'}")
                    print(f"   User: {latest['user_message']}")
                    print(f"   AI: {latest['ai_response'][:100]}...")
                    print("="*60)
                
                last_count = current_count
            
            time.sleep(2)  # Check every 2 seconds
            
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    monitor_interactions()