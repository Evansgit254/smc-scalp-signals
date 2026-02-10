import os
import json
import pytest
# Legacy test - audit module removed
pytest.skip("Audit module removed", allow_module_level=True)
# from unittest.mock import patch
# from datetime import datetime
# from audit.quota_manager import QuotaManager

@pytest.fixture
def mock_quota_file(tmp_path):
    file_path = tmp_path / "quota_tracking.json"
    return str(file_path)

def test_quota_manager_init(mock_quota_file):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(QuotaManager, "_FILE_PATH", mock_quota_file)
        qm = QuotaManager(max_daily_signals=4)
        assert qm.get_total_sent() == 0
        assert qm.can_send_signal("EURUSD=X") is True

def test_quota_manager_limit(mock_quota_file):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(QuotaManager, "_FILE_PATH", mock_quota_file)
        qm = QuotaManager(max_daily_signals=2)
        
        qm.log_signal("EURUSD=X")
        assert qm.get_total_sent() == 1
        assert qm.can_send_signal("GBPUSD=X") is True
        
        qm.log_signal("GBPUSD=X")
        assert qm.get_total_sent() == 2
        assert qm.can_send_signal("GC=F") is False

def test_quota_manager_gold_tracking(mock_quota_file):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(QuotaManager, "_FILE_PATH", mock_quota_file)
        qm = QuotaManager(max_daily_signals=4)
        
        assert qm.is_gold_sent() is False
        qm.log_signal("GC=F")
        assert qm.is_gold_sent() is True

def test_quota_manager_persistence(mock_quota_file):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(QuotaManager, "_FILE_PATH", mock_quota_file)
        qm = QuotaManager(max_daily_signals=4)
        qm.log_signal("EURUSD=X")
        
        # New instance should load existing data
        # V18.4: Patch out the test reset logic to test persistence
        with patch("os.getenv", side_effect=lambda k, d=None: None if k == "PYTEST_CURRENT_TEST" else d):
            qm2 = QuotaManager(max_daily_signals=4)
            assert qm2.get_total_sent() == 1
            assert qm2.can_send_signal("GBPUSD=X") is True

def test_quota_manager_reset_on_new_day(mock_quota_file):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(QuotaManager, "_FILE_PATH", mock_quota_file)
        
        # Create "yesterday's" data
        os.makedirs(os.path.dirname(mock_quota_file), exist_ok=True)
        with open(mock_quota_file, 'w') as f:
            json.dump({
                'date': '2000-01-01',
                'total_sent': 4,
                'gold_sent': True,
                'signals': []
            }, f)
            
        qm = QuotaManager(max_daily_signals=4)
        # Should reset because the date changed
        assert qm.get_total_sent() == 0
        assert qm.data['date'] == datetime.now().strftime("%Y-%m-%d")
