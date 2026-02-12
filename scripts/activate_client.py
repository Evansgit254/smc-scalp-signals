#!/usr/bin/env python3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.client_manager import ClientManager

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 activate_client.py <telegram_chat_id> <days> [tier]")
        print("Example: python3 activate_client.py 123456789 30 PREMIUM")
        sys.exit(1)

    chat_id = sys.argv[1]
    try:
        days = int(sys.argv[2])
    except ValueError:
        print("Error: Days must be an integer.")
        sys.exit(1)

    tier = sys.argv[3] if len(sys.argv) > 3 else "BASIC"

    manager = ClientManager()
    
    # Check if client exists
    # We use a raw query check because get_client filters for is_active=1
    # and we might want to activate a deactivated client (re-registration)
    import sqlite3
    conn = sqlite3.connect("database/clients.db")
    client = conn.execute("SELECT * FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
    conn.close()

    if not client:
        print(f"❌ Error: Client with Chat ID {chat_id} not found in database.")
        print("Ask the user to run /register first.")
        sys.exit(1)

    print(f"⚙️ Activating {chat_id} for {days} days (Tier: {tier})...")
    result = manager.update_subscription(chat_id, days, tier)

    if result['status'] == 'success':
        print(f"✅ Success! New expiry: {result['new_expiry']}")
        
        # Ensure client is marked as active
        conn = sqlite3.connect("database/clients.db")
        conn.execute("UPDATE clients SET is_active = 1 WHERE telegram_chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        print(f"🔓 Client marked as ACTIVE in database.")
    else:
        print(f"❌ Failed: {result['message']}")

if __name__ == "__main__":
    main()
