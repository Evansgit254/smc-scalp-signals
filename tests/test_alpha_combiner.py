"""
Unit tests for Alpha Combiner
100% coverage target
"""
import pytest
from core.alpha_combiner import AlphaCombiner

class TestAlphaCombiner:
    """Test suite for alpha signal combination logic"""
    
    def test_combine_basic(self):
        """Test basic signal combination"""
        factors = {
            'velocity': 0.5,
            'zscore': 0.3
        }
        
        signal = AlphaCombiner.combine(factors)
        
        assert isinstance(signal, float)
        assert not signal == float('inf')
        assert not signal == float('-inf')
        
    def test_combine_weights(self):
        """Test weighted combination"""
        # With current weights: velocity=0.4, zscore=0.6
        factors = {
            'velocity': 1.0,
            'zscore': 1.0
        }
        
        signal = AlphaCombiner.combine(factors)
        # Expected: (1.0 * 0.4) + (1.0 * 0.6) = 1.0
        assert abs(signal - 1.0) < 0.01
        
    def test_combine_clipping(self):
        """Test outlier clipping at 4.0"""
        factors = {
            'velocity': 10.0,  # Extreme value
            'zscore': 10.0     # Extreme value
        }
        
        signal = AlphaCombiner.combine(factors)
        
        # Should be clipped to 4.0 max
        # (4.0 * 0.4) + (4.0 * 0.6) = 4.0
        assert signal == 4.0
        
    def test_combine_negative_clipping(self):
        """Test negative outlier clipping"""
        factors = {
            'velocity': -10.0,
            'zscore': -10.0
        }
        
        signal = AlphaCombiner.combine(factors)
        assert signal == -4.0
        
    def test_combine_empty_factors(self):
        """Test combination with empty factor dict"""
        signal = AlphaCombiner.combine({})
        assert signal == 0.0
        
    def test_combine_unknown_factor(self):
        """Test combination ignores unknown factors"""
        factors = {
            'unknown_factor': 100.0,
            'velocity': 1.0,
            'zscore': 1.0
        }
        
        signal = AlphaCombiner.combine(factors)
        # Should ignore unknown_factor, only use velocity and zscore
        assert abs(signal - 1.0) < 0.01
        
    def test_combine_rounding(self):
        """Test signal is properly rounded to 4 decimals"""
        factors = {
            'velocity': 0.123456789,
            'zscore': 0.987654321
        }
        
        signal = AlphaCombiner.combine(factors)
        # Check it's rounded to 4 decimal places
        assert len(str(signal).split('.')[-1]) <= 4
