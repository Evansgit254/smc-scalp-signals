import sqlite3
import os

DB_PATH = "database/signals.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns_to_add = [
        ("trade_type", "TEXT DEFAULT 'SCALP'"),
        ("quality_score", "REAL DEFAULT 0.0"),
        ("regime", "TEXT DEFAULT 'UNKNOWN'"),
        ("expected_hold", "TEXT DEFAULT 'UNKNOWN'"),
        ("risk_details", "TEXT DEFAULT '{}'"),
        ("score_details", "TEXT DEFAULT '{}'")
    ]
    
    print("🔄 Starting migration...")
    
    for col_name, col_def in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_def}")
            print(f"✅ Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e):
                print(f"ℹ️  Column {col_name} already exists. Skipping.")
            else:
                print(f"❌ Error adding {col_name}: {e}")
    
    conn.commit()
    conn.close()
    print("🎉 Migration completed successfully!")

if __name__ == "__main__":
    migrate()
