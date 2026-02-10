"""
Test suite for ClientManager

Validates client registration, balance updates, and database operations.
"""
import pytest
import os
import sqlite3
from core.client_manager import ClientManager

@pytest.fixture
def client_manager():
    """Create a test ClientManager with temporary database."""
    test_db = "database/test_clients.db"
    
    # Remove existing test database
    if os.path.exists(test_db):
        os.remove(test_db)
    
    manager = ClientManager(test_db)
    yield manager
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)

def test_register_client(client_manager):
    """Test client registration."""
    result = client_manager.register_client("123456789", 500.0, 2.0)
    
    assert result['status'] == 'registered'
    assert result['account_balance'] == 500.0
    assert result['risk_percent'] == 2.0
    print(f"✅ Client registered: {result}")

def test_duplicate_registration(client_manager):
    """Test that duplicate registration is prevented."""
    client_manager.register_client("123456789", 500.0)
    result = client_manager.register_client("123456789", 600.0)
    
    assert result['status'] == 'error'
    assert 'already registered' in result['message']
    print(f"✅ Duplicate registration blocked: {result}")

def test_get_client(client_manager):
    """Test retrieving client information."""
    client_manager.register_client("123456789", 500.0, 2.0)
    client = client_manager.get_client("123456789")
    
    assert client is not None
    assert client['account_balance'] == 500.0
    assert client['risk_percent'] == 2.0
    print(f"✅ Client retrieved: {client}")

def test_update_balance(client_manager):
    """Test updating client balance."""
    client_manager.register_client("123456789", 500.0)
    result = client_manager.update_balance("123456789", 750.0)
    
    assert result['status'] == 'success'
    assert result['new_balance'] == 750.0
    
    # Verify update
    client = client_manager.get_client("123456789")
    assert client['account_balance'] == 750.0
    print(f"✅ Balance updated: {client}")

def test_get_all_active_clients(client_manager):
    """Test retrieving all active clients."""
    client_manager.register_client("111", 100.0)
    client_manager.register_client("222", 200.0)
    client_manager.register_client("333", 300.0)
    
    clients = client_manager.get_all_active_clients()
    
    assert len(clients) == 3
    assert clients[0]['account_balance'] == 100.0
    assert clients[1]['account_balance'] == 200.0
    print(f"✅ Retrieved {len(clients)} active clients")

def test_deactivate_client(client_manager):
    """Test client deactivation."""
    client_manager.register_client("123456789", 500.0)
    result = client_manager.deactivate_client("123456789")
    
    assert result['status'] == 'success'
    
    # Verify client is no longer active
    client = client_manager.get_client("123456789")
    assert client is None
    print(f"✅ Client deactivated")

def test_client_count(client_manager):
    """Test client count."""
    client_manager.register_client("111", 100.0)
    client_manager.register_client("222", 200.0)
    
    count = client_manager.get_client_count()
    assert count == 2
    
    client_manager.deactivate_client("111")
    count = client_manager.get_client_count()
    assert count == 1
    print(f"✅ Client count: {count}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
