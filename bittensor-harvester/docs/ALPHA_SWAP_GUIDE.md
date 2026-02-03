# Alpha-to-TAO Swap Testing Guide

## Overview

You now have:
1. **Consolidated earnings report** (`earnings_report.py`) - Shows daily alpha earnings summed per subnet per day
2. **Alpha swap module** (`src/alpha_swap.py`) - Dry-run alpha-to-TAO swap preparation
3. **Swap CLI** (`test_alpha_swap.py`) - Command-line interface to test swaps
4. **Wallet monitor** (`monitor_wallet.py`) - Monitor your Nova wallet for TAO receipt

## Current Status

### Earnings Report (✓ Fixed)
The earnings report now shows consolidated daily earnings per subnet:
```
2026-02-01 SN60: 0.380476 alpha → 0.190238 TAO harvestable (50% fraction)
```

**Key change**: Previously showed multiple rows per subnet (one per source/transfer).
Now shows ONE row per subnet per day with totals summed.

### Alpha Swap Rates (⚠️ Placeholder)
Currently using estimated rates:
- SN60: 1 alpha ≈ 0.012 TAO (likely wrong)
- Other subnets: ~0.008-0.011 TAO per alpha

**⚠️ These are placeholders.** Real rates depend on subnet DEX liquidity and market conditions.

## How to Test a Real Swap

### Option 1: Manual Swap (Recommended for First Test)

1. **Check available harvestable alpha**:
   ```powershell
   # View today's report
   gc reports/earnings_report_2026-02-01.csv | Select-String "2026-02-01.*,60," | Select-Object -First 1
   ```
   Shows: `0.380476 alpha` with `0.190238 TAO` harvestable

2. **Use your wallet/DEX to swap a small amount**:
   - Open your Bittensor wallet UI (Polkadot.js, Nova, etc.)
   - Navigate to SN60 or another subnet with alpha
   - Look for "Swap Alpha → TAO" or similar
   - Swap a small amount (e.g., 0.01 alpha) to test

3. **Confirm receipt in Nova wallet**:
   ```powershell
   # Monitor wallet for incoming TAO (requires Taostats API access)
   python monitor_wallet.py --wallet 5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh --expected 0.0001 --timeout 300
   ```

### Option 2: Use This Tool (Once Rates Verified)

```powershell
# Dry-run test
python test_alpha_swap.py --netuid 60 --amount 0.01

# Real swap (after confirming rates are correct)
python test_alpha_swap.py --netuid 60 --amount 0.01 --real
```

**⚠️ Don't use `--real` until you've:**
1. Manually verified the swap rate on SN60
2. Confirmed the tool's rate matches the DEX rate
3. Updated the hardcoded rates in `src/alpha_swap.py`

## Next Steps

### 1. Get Real Swap Rates
You need to determine actual alpha-to-TAO swap rates for each subnet.

Options:
- **Check Taostats**: Does it show DEX or swap rates? If so, update `src/alpha_swap.py`
- **Check subnet DEX**: If SN60 has a Uniswap/Curve-like DEX, query the liquidity pool
- **Manual observation**: Use wallet UI to see quote for 1 alpha → TAO on each subnet
- **On-chain oracle**: If Bittensor has an oracle contract, query it

### 2. Update Swap Rates
Once you know real rates, update `src/alpha_swap.py`:

```python
def _get_swap_rates(self) -> Dict[int, float]:
    """Get current alpha-to-TAO swap rates per subnet."""
    return {
        29: 0.015,  # Update these with real rates
        60: 0.018,  # SN60 typically has highest rate
        # ... etc
    }
```

### 3. Implement Real Swap Execution
Currently `execute_swap()` is stubbed out for real execution.
To enable real swaps, you'll need to:

1. **Provide signing credentials**:
   - Private key (in `.env` or secure keystore)
   - Or connect to signing service (Ledger, etc.)

2. **Implement RPC calls**:
   - Connect to subnet RPC endpoint
   - Call alpha swap pallet or DEX contract
   - Sign and broadcast transaction

3. **Verify settlement**:
   - Monitor Taostats for balance updates
   - Confirm TAO arrival in wallet

## File Locations

| File | Purpose |
|------|---------|
| `earnings_report.py` | Daily earnings tracking (consolidated) |
| `src/alpha_swap.py` | Alpha-to-TAO swap logic |
| `test_alpha_swap.py` | CLI for testing swaps |
| `monitor_wallet.py` | Monitor Nova wallet for TAO receipt |
| `reports/earnings_report_2026-02-01.csv` | Today's earnings (one row per subnet) |

## Troubleshooting

### "Swap rates are wrong"
- Update `src/alpha_swap.py` `_get_swap_rates()` with correct rates
- Verify with manual wallet swap first

### "TAO not arriving in wallet"
- Check transaction hash in Taostats
- Verify correct destination wallet address
- Check subnet RPC for pending transactions
- May take a few blocks to settle (5-30 seconds typically)

### "Monitor not detecting receipt"
- Ensure `TAOSTATS_API_KEY` is set and valid
- Taostats may not have real-time balance updates
- May need to add 30-60s delay before checking

## Security Notes

⚠️ **Before implementing real swaps:**
1. Never hardcode private keys in code
2. Use environment variables or secure keystores
3. Implement rate slippage checks
4. Add transaction limits and approval steps
5. Test thoroughly on testnet first

## Example: Full Workflow

```powershell
# 1. Check earnings
python earnings_report.py
# Output: SN60 has 0.38 alpha today

# 2. Prepare dry-run swap
python test_alpha_swap.py --netuid 60 --amount 0.01
# Output: Would receive ~0.00012 TAO (using placeholder rate)

# 3. Manual swap in wallet UI
# (Use Polkadot.js or Nova to swap 0.01 alpha for actual TAO)

# 4. Monitor wallet for receipt
python monitor_wallet.py --wallet 5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh --expected 0.0001
# Output: Receipt detected after ~30s

# 5. Verify in Taostats
# (Check https://taostats.io/account/5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh)
```

## Questions?

For now, I recommend:
1. **Step 1**: Manually swap 0.01 alpha to confirm rates and wallet setup
2. **Step 2**: Update the tool with real rates
3. **Step 3**: Implement signing credentials for real execution

Let me know what rates you see from Taostats/DEX and I'll update the module!
