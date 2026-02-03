# Taostats API Integration Summary

## What Was Added

I've created a complete Taostats API integration for the Bittensor Harvester with the following components:

### 1. **New Files Created**

| File | Purpose |
|------|---------|
| `src/taostats.py` | Taostats API client with methods to fetch earnings, validator info, and subnet data |
| `.env.example` | Configuration template with all environment variables |
| `TAOSTATS_SETUP.md` | Comprehensive setup and usage guide |
| `test_taostats_api.py` | Testing utility to validate API key and fetch data |
| `examples_taostats_api.py` | Code examples showing integration patterns |

### 2. **Configuration Updated**

Modified `src/config.py` to include:
```python
taostats_api_key: str = os.getenv("TAOSTATS_API_KEY", "")
```

## Quick Start

### Step 1: Get API Key
Visit https://taostats.io and generate an API key

### Step 2: Configure
```bash
# Create .env file
cp .env.example .env

# Edit .env and add:
TAOSTATS_API_KEY=your_api_key_here
HARVESTER_WALLET_ADDRESS=5YOUR_ADDRESS
```

### Step 3: Test
```bash
# Validate API connection
python test_taostats_api.py --test-connection

# Get earnings for your validator
python test_taostats_api.py --get-earnings 5YOUR_ADDRESS --netuid 1

# Get subnet information
python test_taostats_api.py --get-subnet 1
```

## API Methods Available

```python
from src.config import HarvesterConfig
from src.taostats import TaostatsClient

config = HarvesterConfig.from_env()
client = TaostatsClient(api_key=config.taostats_api_key)

# Get earnings statistics
earnings = client.get_validator_earnings(address, netuid)

# Get validator details
validator = client.get_validator_info(address, netuid)

# Get subnet emission data
subnet = client.get_subnet_emissions(netuid)

# Get delegators
delegators = client.get_delegators(validator_address, netuid)

# Validate API key
is_valid = client.check_api_key_valid()
```

## Integration Example

Here's how to add Taostats monitoring to your harvest cycle:

```python
from src.taostats import TaostatsClient

def run_harvest_cycle(config: HarvesterConfig, dry_run: bool = True) -> dict:
    # ... existing setup ...
    
    # Initialize Taostats client
    taostats = TaostatsClient(api_key=config.taostats_api_key)
    
    # Get current earnings before harvest
    earnings_before = taostats.get_validator_earnings(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )
    logger.info(f"Earnings before: {earnings_before.get('total_earnings')} TAO")
    
    # ... run harvest cycle ...
    
    # Get earnings after harvest
    earnings_after = taostats.get_validator_earnings(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )
    delta = earnings_after.get('total_earnings') - earnings_before.get('total_earnings')
    logger.info(f"Earned during cycle: {delta} TAO")
```

## Available Test Commands

```bash
# Test API connection
python test_taostats_api.py --test-connection

# Get validator earnings
python test_taostats_api.py --get-earnings 5YOUR_ADDRESS --netuid 1

# Get validator details
python test_taostats_api.py --get-validator 5YOUR_ADDRESS --netuid 1

# Get subnet information
python test_taostats_api.py --get-subnet 1

# Get delegators for validator
python test_taostats_api.py --get-delegators 5YOUR_ADDRESS --netuid 1

# Run all examples
python examples_taostats_api.py
```

## Security Notes

- **API Key Security**: Never commit `.env` to git (it's in `.gitignore`)
- **Production**: Use environment variables instead of .env files
- **Rate Limits**: Authenticated requests get 10x higher rate limits
- **Best Practice**: Use read-only API keys when possible

## Troubleshooting

### "No API key configured"
→ Add `TAOSTATS_API_KEY` to .env or set environment variable

### "API key validation failed"
→ Check API key validity on https://taostats.io
→ Verify internet connection

### 401 Unauthorized
→ API key is invalid or expired
→ Generate new key on taostats.io

## Next Steps

1. **Complete Setup**: Follow steps in TAOSTATS_SETUP.md
2. **Test Connection**: Run `python test_taostats_api.py --test-connection`
3. **Explore Data**: Try test commands to see what data is available
4. **Integrate**: Add Taostats calls to your harvest cycle in main.py
5. **Monitor**: Use earnings tracking for automated testing

## Files Reference

- **Setup Guide**: Read `TAOSTATS_SETUP.md` for detailed instructions
- **API Client**: See `src/taostats.py` for all available methods
- **Test Script**: Use `test_taostats_api.py` for validation and data fetching
- **Examples**: Run `examples_taostats_api.py` to see integration patterns
- **Config**: Edit `.env` (copied from `.env.example`) with your API key
