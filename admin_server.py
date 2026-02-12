from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI(title="Trading Expert Admin Dashboard")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CLIENTS = "database/clients.db"
DB_SIGNALS = "database/signals.db"

class ClientUpdate(BaseModel):
    account_balance: Optional[float] = None
    risk_percent: Optional[float] = None
    subscription_days: Optional[int] = None
    tier: Optional[str] = None
    is_active: Optional[bool] = None

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/clients")
async def get_clients():
    conn = get_db_connection(DB_CLIENTS)
    clients = conn.execute("SELECT * FROM clients").fetchall()
    conn.close()
    return [dict(ix) for ix in clients]

@app.post("/api/clients/{chat_id}")
async def update_client(chat_id: str, update: ClientUpdate):
    conn = get_db_connection(DB_CLIENTS)
    client = conn.execute("SELECT * FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
    
    if not client:
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    fields = []
    values = []
    
    if update.account_balance is not None:
        fields.append("account_balance = ?")
        values.append(update.account_balance)
    
    if update.risk_percent is not None:
        fields.append("risk_percent = ?")
        values.append(update.risk_percent)
        
    if update.is_active is not None:
        fields.append("is_active = ?")
        values.append(1 if update.is_active else 0)
        
    if update.subscription_days is not None:
        # Calculate new expiry
        current_expiry_str = client['subscription_expiry']
        now = datetime.now()
        if current_expiry_str:
            try:
                current_expiry = datetime.strptime(current_expiry_str, "%Y-%m-%d %H:%M:%S.%f") if "." in current_expiry_str else datetime.strptime(current_expiry_str, "%Y-%m-%d %H:%M:%S")
                start_date = max(now, current_expiry)
            except:
                start_date = now
        else:
            start_date = now
        
        new_expiry = start_date + timedelta(days=update.subscription_days)
        fields.append("subscription_expiry = ?")
        values.append(new_expiry.strftime("%Y-%m-%d %H:%M:%S"))
        
    if update.tier is not None:
        fields.append("subscription_tier = ?")
        values.append(update.tier)
        
    if fields:
        fields.append("updated_at = ?")
        values.append(datetime.now())
        values.append(chat_id)
        
        query = f"UPDATE clients SET {', '.join(fields)} WHERE telegram_chat_id = ?"
        conn.execute(query, values)
        conn.commit()
    
    conn.close()
    return {"status": "success"}

@app.get("/api/signals")
async def get_signals():
    try:
        conn = sqlite3.connect(DB_SIGNALS)
        conn.row_factory = sqlite3.Row
        # V18.0: Fetch all signal fidelity fields
        cursor = conn.execute("""
            SELECT 
                timestamp, symbol, direction, entry_price, sl, tp1, tp2, 
                reasoning, timeframe, confidence,
                trade_type, quality_score, regime, expected_hold, risk_details, score_details
            FROM signals 
            ORDER BY timestamp DESC LIMIT 50
        """)
        signals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return signals
    except Exception as e:
        print(f"Error fetching signals: {e}")
        return []

@app.get("/api/stats")
async def get_stats():
    conn_c = get_db_connection(DB_CLIENTS)
    active_clients = conn_c.execute("SELECT COUNT(*) FROM clients WHERE is_active = 1").fetchone()[0]
    conn_c.close()
    
    signals_today = 0
    if os.path.exists(DB_SIGNALS):
        conn_s = get_db_connection(DB_SIGNALS)
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            signals_today = conn_s.execute("SELECT COUNT(*) FROM signals WHERE DATE(timestamp) = ?", (today,)).fetchone()[0]
        except:
            pass
        conn_s.close()
        
    return {
        "active_clients": active_clients,
        "signals_today": signals_today,
        "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# Mount static files for the dashboard
if os.path.exists("dashboard"):
    app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
