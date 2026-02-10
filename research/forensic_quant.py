import pandas as pd
import numpy as np
import os

def forensic_audit(csv_path="research/quant_audit_results.csv"):
    if not os.path.exists(csv_path):
        print("Audit data not found.")
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        print("Audit data is empty.")
        return

    df['is_win'] = df['res'] == 'WIN'
    
    print("\n" + "="*50)
    print("🔬 QUANT FORENSIC FACTOR AUDIT")
    print("="*50)

    # 1. Individual Factor Correlation
    v_corr = df['velocity'].corr(df['is_win'])
    z_corr = df['zscore'].corr(df['is_win'])
    
    print(f"{'Alpha Factor':<25} | {'Correlation to Win'}")
    print("-" * 50)
    print(f"{'Velocity Alpha':<25} | {v_corr:>18.4f}")
    print(f"{'Mean Reversion (Z)':<25} | {z_corr:>18.4f}")

    # 2. Performance by Factor Deciles
    print("\n📊 Win Rate by Signal Strength (Deciles)")
    print("-" * 50)
    df['sig_bin'] = pd.qcut(df['signal'].abs(), 10, duplicates='drop')
    bin_wr = df.groupby('sig_bin', observed=True)['is_win'].mean() * 100
    for bin_range, wr in bin_wr.items():
        print(f"Strength {str(bin_range):<25} | WR: {wr:>6.1f}%")

    # 3. Winning vs Losing Feature Centroids
    winners = df[df['is_win']]
    losers = df[~df['is_win']]
    
    print("\n🎯 Feature Centroids (Averaged Math Signature)")
    print("-" * 50)
    print(f"{'Feature':<25} | {'Winners':<10} | {'Losers':<10}")
    print(f"{'Avg Velocity':<25} | {winners['velocity'].mean():>10.4f} | {losers['velocity'].mean():>10.4f}")
    print(f"{'Avg Z-Score':<25} | {winners['zscore'].mean():>10.4f} | {losers['zscore'].mean():>10.4f}")

    # 4. Optimization Recommendations
    print("\n💡 OPTIMIZATION RECOMMENDATIONS")
    print("-" * 50)
    if v_corr > 0.05:
        print("🚀 DEEPEN VELOCITY: Increasing velocity weight will likely improve WR.")
    if abs(winners['zscore'].mean()) > abs(losers['zscore'].mean()) + 0.1:
        print("📐 RE-ZEN: Mean reversion is a strong discriminator at higher Z-scores.")

if __name__ == "__main__":
    forensic_audit()
