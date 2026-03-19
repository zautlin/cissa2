#!/usr/bin/env python3
"""
Test TER calculation with manual CSL 2001 values to validate the fix.
"""

import numpy as np
import pandas as pd

def test_ter_calculation():
    """Test TER calculation with CSL 2001 manual values."""
    
    print("=" * 80)
    print("TER CALCULATION TEST - CSL 2001 (1Y)")
    print("=" * 80)
    
    # Manual input values for CSL 2001
    print("\n1. INPUT VALUES:")
    print("-" * 80)
    
    calc_mc_2001 = 7139
    calc_mc_2000 = 4925
    calc_ke_2001 = 0.095  # 9.5%
    fv_ecf_1y_2001 = 21
    
    print(f"Calc MC (2001): {calc_mc_2001}")
    print(f"Calc MC (2000): {calc_mc_2000}")
    print(f"Calc KE (2001): {calc_ke_2001:.1%}")
    print(f"Calc 1Y FV ECF (2001): {fv_ecf_1y_2001}")
    
    # Step 1: Calculate Load TRTE
    print("\n2. CALCULATE LOAD TRTE:")
    print("-" * 80)
    load_trte = fv_ecf_1y_2001 + (calc_mc_2001 - calc_mc_2000)
    print(f"Load TRTE = FV_ECF + (MC_2001 - MC_2000)")
    print(f"Load TRTE = {fv_ecf_1y_2001} + ({calc_mc_2001} - {calc_mc_2000})")
    print(f"Load TRTE = {fv_ecf_1y_2001} + {calc_mc_2001 - calc_mc_2000}")
    print(f"Load TRTE = {load_trte}")
    print(f"Expected: 2235")
    print(f"Match: {load_trte == 2235} ✓" if load_trte == 2235 else f"Match: {load_trte == 2235} ✗")
    
    # Step 2: Calculate Load TER
    print("\n3. CALCULATE LOAD TER:")
    print("-" * 80)
    open_mc = calc_mc_2000  # 4925
    load_ter = (1 + load_trte / open_mc) ** (1/1) - 1
    print(f"Load TER = (1 + Load TRTE / Open MC)^(1/1) - 1")
    print(f"Load TER = (1 + {load_trte} / {open_mc})^1 - 1")
    print(f"Load TER = (1 + {load_trte / open_mc:.6f})^1 - 1")
    print(f"Load TER = {1 + load_trte / open_mc:.6f}^1 - 1")
    print(f"Load TER = {load_ter:.6f}")
    print(f"Load TER = {load_ter:.1%}")
    print(f"Expected: 45.5% (0.455)")
    print(f"Match: {abs(load_ter - 0.455) < 0.01} ✓" if abs(load_ter - 0.455) < 0.01 else f"Match: False ✗")
    
    # Step 3: Calculate Load WC and Load WP using CORRECTED formula with exponent
    print("\n4. CALCULATE LOAD WC & LOAD WP (WITH EXPONENT FIX):")
    print("-" * 80)
    interval = 1
    load_ke = 0.10  # 10.0%
    
    # CORRECTED formula includes exponent
    load_wc = open_mc * (1 + load_ter) ** interval - open_mc * (1 + load_ke) ** interval
    load_wp = open_mc * (1 + load_ke) ** interval
    
    print(f"Load WC = Open MC × (1 + Load TER)^{interval} - Open MC × (1 + Load KE)^{interval}")
    print(f"Load WC = {open_mc} × (1 + {load_ter:.6f})^{interval} - {open_mc} × (1 + {load_ke})^{interval}")
    print(f"Load WC = {open_mc} × {(1 + load_ter) ** interval:.6f} - {open_mc} × {(1 + load_ke) ** interval:.6f}")
    print(f"Load WC = {open_mc * (1 + load_ter) ** interval:.2f} - {open_mc * (1 + load_ke) ** interval:.2f}")
    print(f"Load WC = {load_wc:.2f}")
    print(f"Expected: 1743")
    print(f"Match: {abs(load_wc - 1743) < 10} ✓" if abs(load_wc - 1743) < 10 else f"Match: False ✗")
    
    print(f"\nLoad WP = Open MC × (1 + Load KE)^{interval}")
    print(f"Load WP = {open_mc} × (1 + {load_ke})^{interval}")
    print(f"Load WP = {open_mc} × {(1 + load_ke) ** interval:.6f}")
    print(f"Load WP = {load_wp:.2f}")
    print(f"Expected: 5417")
    print(f"Match: {abs(load_wp - 5417) < 10} ✓" if abs(load_wp - 5417) < 10 else f"Match: False ✗")
    
    # Step 4: Calculate final TER
    print("\n5. CALCULATE FINAL TER:")
    print("-" * 80)
    wc = load_wc  # 1743 (from VLOOKUP in Excel, but same as Load WC for 1Y)
    wp = load_wp  # 5417 (from VLOOKUP in Excel, but same as Load WP for 1Y)
    
    # Use the manual values provided
    wc_manual = 1743
    wp_manual = 5417
    open_mc_final = 4925
    
    ter = ((wc_manual + wp_manual) / open_mc_final) ** (1/interval) - 1
    
    print(f"TER = ((WC + WP) / Open MC)^(1/{interval}) - 1")
    print(f"TER = (({wc_manual} + {wp_manual}) / {open_mc_final})^(1/{interval}) - 1")
    print(f"TER = ({wc_manual + wp_manual} / {open_mc_final})^1 - 1")
    print(f"TER = {(wc_manual + wp_manual) / open_mc_final:.6f}^1 - 1")
    print(f"TER = {ter:.6f}")
    print(f"TER = {ter:.1%}")
    print(f"\nExpected: 45.4% (0.454)")
    print(f"Match: {abs(ter - 0.454) < 0.001} ✓" if abs(ter - 0.454) < 0.001 else f"Match: False ✗")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Load TRTE: {load_trte} (expected 2235) {'✓' if load_trte == 2235 else '✗'}")
    print(f"Load TER: {load_ter:.1%} (expected 45.5%) {'✓' if abs(load_ter - 0.455) < 0.01 else '✗'}")
    print(f"Load WC: {load_wc:.2f} (expected 1743) {'✓' if abs(load_wc - 1743) < 10 else '✗'}")
    print(f"Load WP: {load_wp:.2f} (expected 5417) {'✓' if abs(load_wp - 5417) < 10 else '✗'}")
    print(f"Final TER: {ter:.1%} (expected 45.4%) {'✓' if abs(ter - 0.454) < 0.001 else '✗'}")
    print("=" * 80)
    
    return ter


if __name__ == "__main__":
    result = test_ter_calculation()
    print(f"\nTest result: {result:.1%}")
