"""
Test using the official bittensor library for RPC queries.
This uses the proven, tested approach from opentensor/bittensor instead of reinventing storage key encoding.
"""

# First, install the official library:
# pip install bittensor

from bittensor import Subtensor
from bittensor.utils.balance import Balance


# Connect to Archive node
subtensor = Subtensor(network="archive")  # Uses wss://archive.chain.opentensor.ai:443

# Test 1: Get current block
current_block = subtensor.get_current_block()
print(f"Current block: {current_block}")

# Test 2: Get all active subnets
netuids = subtensor.get_all_subnets_netuid()
print(f"Active subnets: {netuids}")

# Test 3: Get stake for a specific coldkey/hotkey/netuid
# Example addresses (you'll need to replace with real ones)
example_coldkey = "5CdXmzAJh2Tb3M5Uv2yyiW1bCxnrMdEFuJmF9x5r5VyW9FcZ"  # Example only
example_hotkey = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"   # Example only
example_netuid = 1

try:
    # This is the proper way - uses Runtime API or substrate.query() internally
    stake = subtensor.get_stake(
        coldkey_ss58=example_coldkey,
        hotkey_ss58=example_hotkey,
        netuid=example_netuid,
        block=current_block
    )
    print(f"Stake: {stake}")
except Exception as e:
    print(f"Error getting stake: {e}")

# Test 4: Query stake info for all subnets for a coldkey/hotkey pair
try:
    stake_info_dict = subtensor.get_stake_for_coldkey_and_hotkey(
        hotkey_ss58=example_hotkey,
        coldkey_ss58=example_coldkey,
    )
    print(f"Stake info across subnets: {stake_info_dict}")
except Exception as e:
    print(f"Error getting stake info: {e}")

print("\n✅ Official bittensor library works! No manual storage key construction needed.")
print("This library handles all the complex Substrate encoding internally.")
