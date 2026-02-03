# Taostats API Setup Guide

## Overview

This guide explains how to set up and use the Taostats API integration with the Bittensor Harvester for retrieving earnings statistics.

## Step 1: Get Your API Key

1. Visit [https://taostats.io](https://taostats.io)
2. Sign up for an account
3. Navigate to your API settings
4. Copy your API key

**Note:** Public endpoints work without authentication, but authenticated requests have higher rate limits.

## Step 2: Configure the API Key

### Option A: Using .env File (Recommended for Local Testing)

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key:
   ```
   TAOSTATS_API_KEY=your_api_key_here
   ```

3. The config system will automatically load it:
   ```python
   from src.config import HarvesterConfig
   config = HarvesterConfig.from_env()
   # config.taostats_api_key is now populated
   ```

### Option B: Environment Variable (Recommended for Production)

Set the environment variable before running:

**Linux/macOS:**
```bash
export TAOSTATS_API_KEY=your_api_key_here
python test_taostats_api.py --test-connection
```

**Windows PowerShell:**
```powershell
$env:TAOSTATS_API_KEY = "your_api_key_here"
python test_taostats_api.py --test-connection
```

**Windows Command Prompt:**
```cmd
set TAOSTATS_API_KEY=your_api_key_here
python test_taostats_api.py --test-connection
```

## Step 3: Test Your Configuration

Use the provided test script to verify your API key works:

```bash
# Test API connection
python test_taostats_api.py --test-connection

# Get validator earnings
python test_taostats_api.py --get-earnings 5YOUR_ADDRESS --netuid 1

# Get subnet information
python test_taostats_api.py --get-subnet 1

# Get validator details
python test_taostats_api.py --get-validator 5YOUR_ADDRESS --netuid 1
```

## Usage in Code

### Basic Usage

```python
from src.config import HarvesterConfig
from src.taostats import TaostatsClient

# Load config (includes API key from environment)
config = HarvesterConfig.from_env()

# Initialize client
client = TaostatsClient(api_key=config.taostats_api_key)

# Get validator earnings
earnings = client.get_validator_earnings(
    address="5YOUR_ADDRESS",
    netuid=1
)
print(earnings)

# Get subnet emissions
subnet_info = client.get_subnet_emissions(netuid=1)
print(subnet_info)

# Get validator details
validator = client.get_validator_info(
    address="5YOUR_ADDRESS",
    netuid=1
)
print(validator)

# Get delegators for a validator
delegators = client.get_delegators(
    validator_address="5YOUR_ADDRESS",
    netuid=1
)
print(delegators)
```

## Available Methods

### `get_validator_earnings(address, netuid)`
Retrieve earnings statistics for a validator:
- Total earnings
- Daily/hourly earnings rates
- 24h, 7d, 30d period data

### `get_subnet_emissions(netuid)`
Get subnet-level emission statistics:
- Total daily emissions
- Number of validators
- Average earnings per validator

### `get_validator_info(address, netuid)`
Get detailed validator information:
- Stake amount
- Delegation amount
- Trust score
- Incentive metrics
- Emission rates

### `get_delegators(validator_address, netuid)`
List all delegators for a specific validator and their delegation amounts

### `check_api_key_valid()`
Validate that your API key is working:
```python
if client.check_api_key_valid():
    print("API key is valid!")
else:
    print("API key is invalid")
```

## Troubleshooting

### "No API key configured"
- **Cause:** `TAOSTATS_API_KEY` environment variable not set
- **Fix:** Set the environment variable (see Step 2 above)

### "API key validation failed"
- **Cause:** Invalid API key or connection issue
- **Fix:** 
  1. Verify your API key is correct on taostats.io
  2. Check your internet connection
  3. Try using a VPN if you're in a restricted region

### 401 Unauthorized
- **Cause:** Invalid or expired API key
- **Fix:** Generate a new API key on taostats.io

### Rate Limited (429 errors)
- **Cause:** Too many requests without authentication
- **Fix:** Ensure you're using your API key (see Step 2)

## Integration with Harvester

To integrate Taostats earnings data into the main harvester cycle, add this to `src/main.py`:

```python
from src.taostats import TaostatsClient

def run_harvest_cycle(config: HarvesterConfig, dry_run: bool = True) -> dict:
    # ... existing code ...
    
    # Initialize Taostats client for earnings tracking
    taostats = TaostatsClient(api_key=config.taostats_api_key)
    
    # Fetch validator earnings
    earnings = taostats.get_validator_earnings(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )
    logger.info(f"Current earnings: {earnings}")
    
    # ... continue with harvest cycle ...
```

## Security Best Practices

1. **Never commit `.env` files** - Add to `.gitignore` (already done)
2. **Use environment variables** in production instead of `.env`
3. **Rotate API keys** periodically if they're exposed
4. **Use read-only API keys** when possible to limit damage from exposure
5. **Don't share your API key** in error reports or logs

## API Rate Limits

- **Without API key:** ~100 requests/minute (public rate limit)
- **With API key:** ~1000 requests/minute (authenticated)
- **Batch requests:** Use multiple calls in sequence, wait between batches

## Taostats API Documentation

For more details on the Taostats API:
- Main Site: https://taostats.io
- API Docs: https://api.taostats.io/docs (if available)
- Community: Ask in Bittensor Discord/forums
