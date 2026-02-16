from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import sqlite3
import os
import json
import stripe
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from core.client_manager import ClientManager

# Stripe Configuration
stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

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

def ensure_db_schema():
    """V18.1: Automatic Schema Migration - Ensures all required columns exist."""
    if not os.path.exists(DB_SIGNALS):
        return
    
    conn = None
    try:
        conn = sqlite3.connect(DB_SIGNALS)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        # Required columns for High Fidelity Dashboard
        required_cols = [
            ("trade_type", "TEXT DEFAULT 'SCALP'"),
            ("quality_score", "REAL DEFAULT 0.0"),
            ("regime", "TEXT DEFAULT 'UNKNOWN'"),
            ("expected_hold", "TEXT DEFAULT 'UNKNOWN'"),
            ("risk_details", "TEXT DEFAULT '{}'"),
            ("score_details", "TEXT DEFAULT '{}'")
        ]
        
        for col_name, col_def in required_cols:
            try:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_def}")
                print(f"✅ Auto-added missing column: {col_name}")
            except sqlite3.OperationalError:
                # Column likely already exists
                pass
        
        conn.commit()
    finally:
        if conn:
            conn.close()

# Run migration on startup
ensure_db_schema()

def ensure_config_table():
    """Ensure system_config table exists and has required defaults."""
    conn = None
    try:
        conn = sqlite3.connect(DB_CLIENTS)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                type TEXT
            )
        """)
        
        # Ensure defaults exist (INSERT OR IGNORE)
        defaults = [
            ("system_status", "ACTIVE", "str"),
            ("risk_per_trade", "2.0", "float"),
            ("max_concurrent_trades", "4", "int"),
            ("min_quality_score", "5.0", "float"),
            ("news_filter_minutes", "30", "int")
        ]
        
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR IGNORE INTO system_config (key, value, type) 
            VALUES (?, ?, ?)
        """, defaults)
        
        conn.commit()
        print("✅ Verified system_config defaults")
            
    except Exception as e:
        print(f"⚠️ Config table init failed: {e}")
    finally:
        if conn: conn.close()

ensure_config_table()

def ensure_users_table():
    """Ensure admin_users table exists and create default admin if missing."""
    conn = None
    try:
        conn = sqlite3.connect(DB_CLIENTS)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                last_login TEXT
            )
        """)
        
        # Check if users exist
        cursor = conn.cursor()
        if cursor.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0] == 0:
            # Create default admin
            default_salt = secrets.token_hex(8)
            password = "admin123"
            pwd_hash = hashlib.sha256((password + default_salt).encode()).hexdigest()
            stored_pwd = f"{default_salt}${pwd_hash}"
            
            cursor.execute("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", ("admin", stored_pwd))
            conn.commit()
            print("✅ Initialized admin_users with default credentials (admin/admin123)")
            
    except Exception as e:
        print(f"⚠️ Users table init failed: {e}")
    finally:
        if conn: conn.close()

ensure_users_table()

# Auth Configuration
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

class AuthToken(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str

def verify_password(plain_password, stored_password):
    try:
        salt, hash_val = stored_password.split('$')
        check_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
        return check_hash == hash_val
    except:
        return False

async def get_current_user(token: str = Depends(oauth2_scheme)):
    import base64
    try:
        # Simple token format for MVP: base64(username:expiry_iso)
        # In production, use python-jose or PyJWT
        decoded = base64.b64decode(token).decode()
        username, expiry_str = decoded.split(':', 1)
        expiry = datetime.fromisoformat(expiry_str)
        
        if datetime.now() > expiry:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return User(username=username)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.post("/api/token", response_model=AuthToken)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection(DB_CLIENTS)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM admin_users WHERE username = ?", (form_data.username,)).fetchone()
    conn.close()
    
    if not user:
        # Dummy check to prevent timing attacks (skipping for MVP speed)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not verify_password(form_data.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate simple token
    import base64
    expiry = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = f"{user['username']}:{expiry.isoformat()}"
    token_b64 = base64.b64encode(token_data.encode()).decode()
    
    return {"access_token": token_b64, "token_type": "bearer"}

@app.get("/api/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

class ConfigUpdate(BaseModel):
    key: str
    value: str

@app.get("/api/config")
async def get_config(current_user: User = Depends(get_current_user)):
    """Get all system configuration settings"""
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        rows = conn.execute("SELECT key, value, type FROM system_config").fetchall()
        config = {}
        for row in rows:
            val = row['value']
            if row['type'] == 'int': val = int(val)
            elif row['type'] == 'float': val = float(val)
            elif row['type'] == 'bool': val = (val.lower() == 'true')
            config[row['key']] = val
        return config
    except Exception as e:
        print(f"Error fetching config: {e}")
        return {}
    finally:
        if conn: conn.close()

@app.post("/api/config")
async def update_config(update: ConfigUpdate, current_user: User = Depends(get_current_user)):
    """Update a specific configuration setting"""
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        conn.execute("UPDATE system_config SET value = ? WHERE key = ?", (str(update.value), update.key))
        conn.commit()
        return {"status": "success", "key": update.key, "value": update.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

class ClientUpdate(BaseModel):
    account_balance: Optional[float] = None
    risk_percent: Optional[float] = None
    subscription_days: Optional[int] = None
    tier: Optional[str] = None
    is_active: Optional[bool] = None
    dashboard_access: Optional[bool] = None


def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/clients")
async def get_clients(current_user: User = Depends(get_current_user)):
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        clients = conn.execute("SELECT * FROM clients").fetchall()
        return [dict(ix) for ix in clients]
    finally:
        if conn:
            conn.close()

@app.post("/api/clients/{chat_id}")
async def update_client(chat_id: str, update: ClientUpdate, current_user: User = Depends(get_current_user)):
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        client = conn.execute("SELECT * FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
        
        if not client:
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
        
        # Add dashboard_access field handling
        if hasattr(update, 'dashboard_access') and update.dashboard_access is not None:
            fields.append("dashboard_access = ?")
            values.append(1 if update.dashboard_access else 0)

            
        if fields:
            fields.append("updated_at = ?")
            values.append(datetime.now())
            values.append(chat_id)
            
            query = f"UPDATE clients SET {', '.join(fields)} WHERE telegram_chat_id = ?"
            conn.execute(query, values)
            conn.commit()
        
        return {"status": "success"}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        print(f"Error updating client {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/clients/{chat_id}/toggle-signals")
async def toggle_signals(chat_id: str, current_user: User = Depends(get_current_user)):
    """Toggle Telegram signal delivery for a client"""
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        client = conn.execute("SELECT is_active FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        new_status = 0 if client['is_active'] else 1
        conn.execute("""
            UPDATE clients 
            SET is_active = ?, updated_at = ? 
            WHERE telegram_chat_id = ?
        """, (new_status, datetime.now(), chat_id))
        conn.commit()
        
        return {
            "status": "success",
            "is_active": bool(new_status),
            "message": f"Telegram signals {'enabled' if new_status else 'disabled'}"
        }
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/clients/{chat_id}/toggle-dashboard")
async def toggle_dashboard(chat_id: str, current_user: User = Depends(get_current_user)):
    """Toggle dashboard access for a client"""
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        client = conn.execute("SELECT dashboard_access FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        new_status = 0 if client['dashboard_access'] else 1
        conn.execute("""
            UPDATE clients 
            SET dashboard_access = ?, updated_at = ? 
            WHERE telegram_chat_id = ?
        """, (new_status, datetime.now(), chat_id))
        conn.commit()
        
        return {
            "status": "success",
            "dashboard_access": bool(new_status),
            "message": f"Dashboard access {'granted' if new_status else 'revoked'}"
        }
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/clients/{chat_id}/extend")
async def quick_extend(chat_id: str, days: int = 30, current_user: User = Depends(get_current_user)):
    """Quick extend subscription by specified days (default 30)"""
    conn = None
    try:
        conn = get_db_connection(DB_CLIENTS)
        client = conn.execute("SELECT subscription_expiry FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
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
        
        new_expiry = start_date + timedelta(days=days)
        
        conn.execute("""
            UPDATE clients 
            SET subscription_expiry = ?, updated_at = ? 
            WHERE telegram_chat_id = ?
        """, (new_expiry.strftime("%Y-%m-%d %H:%M:%S"), datetime.now(), chat_id))
        conn.commit()
        
        return {
            "status": "success",
            "new_expiry": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
            "message": f"Subscription extended by {days} days"
        }
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not STRIPE_WEBHOOK_SECRET:
        print("⚠️ STRIPE_WEBHOOK_SECRET not set. Webhook bypass for DEBUG only.")
    
    try:
        event = None
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        else:
            # Fallback for debug if secret is missing
            event = json.loads(payload)
            
    except Exception as e:
        print(f"⚠️ Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # Extract metadata
        metadata = session.get("metadata", {})
        chat_id = metadata.get("telegram_chat_id")
        days = int(metadata.get("subscription_days", 30))
        tier = metadata.get("tier", "BASIC")
        
        if chat_id:
            print(f"💰 PAYMENT SUCCESS: Activating {chat_id} for {days} days ({tier})")
            client_manager = ClientManager(DB_CLIENTS)
            result = client_manager.update_subscription(chat_id, days, tier)
            
            # Also ensure client is marked as active
            if result.get('status') == 'success':
                conn = get_db_connection(DB_CLIENTS)
                conn.execute("UPDATE clients SET is_active = 1 WHERE telegram_chat_id = ?", (chat_id,))
                conn.commit()
                conn.close()
                print(f"✅ Client {chat_id} activated automatically.")
            else:
                print(f"❌ Failed to activate client {chat_id}: {result.get('message')}")
        else:
            print("⚠️ Webhook received but no telegram_chat_id in metadata.")

    return {"status": "success"}

@app.get("/api/signals")
async def get_signals(current_user: User = Depends(get_current_user)):
    conn = None
    try:
        conn = get_db_connection(DB_SIGNALS)
        # V18.0: Fetch all signal fidelity fields
        cursor = conn.execute("""
            SELECT 
                timestamp, symbol, direction, entry_price, sl, tp1, tp2, 
                reasoning, timeframe, confidence,
                trade_type, quality_score, regime, expected_hold, risk_details, score_details
            FROM signals 
            ORDER BY timestamp DESC LIMIT 50
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching signals: {e}")
        return []
    finally:
        if conn:
            conn.close()

@app.get("/api/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    active_clients = 0
    signals_today = 0
    
    conn_c = None
    try:
        conn_c = get_db_connection(DB_CLIENTS)
        active_clients = conn_c.execute("SELECT COUNT(*) FROM clients WHERE is_active = 1").fetchone()[0]
    except Exception as e:
        print(f"Error fetching client stats: {e}")
    finally:
        if conn_c: conn_c.close()
    
    conn_s = None
    if os.path.exists(DB_SIGNALS):
        try:
            conn_s = get_db_connection(DB_SIGNALS)
            today = datetime.now().strftime('%Y-%m-%d')
            signals_today = conn_s.execute("SELECT COUNT(*) FROM signals WHERE DATE(timestamp) = ?", (today,)).fetchone()[0]
        except Exception as e:
            print(f"Error fetching signal stats: {e}")
        finally:
            if conn_s: conn_s.close()
        
    return {
        "active_clients": active_clients,
        "signals_today": signals_today,
        "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

@app.get("/api/analytics/daily")
async def get_daily_analytics(current_user: User = Depends(get_current_user)):
    conn = None
    try:
        conn = get_db_connection(DB_SIGNALS)
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 1. Overall Summary
        summary = conn.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(quality_score) as avg_quality
            FROM signals 
            WHERE DATE(timestamp) = ?
        """, (today,)).fetchone()
        
        # 2. Performance by Trade Type (SCALP vs SWING)
        type_stats = conn.execute("""
            SELECT 
                trade_type,
                COUNT(*) as total,
                SUM(CASE WHEN result IN ('TP1', 'TP2', 'TP3') OR max_tp_reached > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'SL' THEN 1 ELSE 0 END) as losses,
                AVG(quality_score) as avg_quality
            FROM signals 
            WHERE DATE(timestamp) = ?
            GROUP BY trade_type
        """, (today,)).fetchall()
        
        stats_by_type = {row['trade_type']: dict(row) for row in type_stats}
        
        # 3. BUY vs SELL Bias
        bias_rows = conn.execute("""
            SELECT direction, COUNT(*) as count 
            FROM signals 
            WHERE DATE(timestamp) = ?
            GROUP BY direction
        """, (today,)).fetchall()
        
        bias = {row['direction']: row['count'] for row in bias_rows}
        
        # 4. Top Assets (by volume and quality)
        asset_rows = conn.execute("""
            SELECT 
                symbol, 
                COUNT(*) as count,
                AVG(quality_score) as avg_quality,
                SUM(CASE WHEN result IN ('TP1', 'TP2', 'TP3') OR max_tp_reached > 0 THEN 1 ELSE 0 END) as wins
            FROM signals 
            WHERE DATE(timestamp) = ?
            GROUP BY symbol
            ORDER BY count DESC
            LIMIT 5
        """, (today,)).fetchall()
        
        assets = [dict(row) for row in asset_rows]
        
        # 5. Hourly Heatmap
        hourly_rows = conn.execute("""
            SELECT STRFTIME('%H', timestamp) as hour, COUNT(*) as count
            FROM signals
            WHERE DATE(timestamp) = ?
            GROUP BY hour
        """, (today,)).fetchall()
        
        hourly = {row['hour']: row['count'] for row in hourly_rows}
        
        # 6. Best Performing Symbol & Strategy
        best_symbol = conn.execute("""
            SELECT symbol, COUNT(*) as count, SUM(CASE WHEN result IN ('TP1', 'TP2', 'TP3') OR max_tp_reached > 0 THEN 1 ELSE 0 END) as wins
            FROM signals 
            WHERE DATE(timestamp) = ?
            GROUP BY symbol
            ORDER BY wins DESC, count DESC
            LIMIT 1
        """, (today,)).fetchone()

        return {
            "total_signals": summary['total'] or 0,
            "avg_quality": round(summary['avg_quality'] or 0, 1),
            "stats_by_type": stats_by_type,
            "bias": bias,
            "top_assets": assets,
            "hourly_heatmap": hourly,
            "top_performer": dict(best_symbol) if best_symbol else None
        }
    except Exception as e:
        print(f"Error calculating analytics: {e}")
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()

# Mount static files for the dashboard
if os.path.exists("dashboard"):
    app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
