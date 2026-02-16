# Add these endpoints after the existing client management endpoints in admin_server.py

@app.post("/api/clients/{chat_id}/toggle-signals")
async def toggle_signals(chat_id: str):
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
async def toggle_dashboard(chat_id: str):
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
async def quick_extend(chat_id: str, days: int = 30):
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
