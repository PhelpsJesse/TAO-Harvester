from src.taostats import TaostatsClient
from src.wallet_manager import WalletManager

client = TaostatsClient()
wallet = WalletManager(client, '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh')
holdings = wallet.get_current_holdings(force_refresh=True)
all_subnets = [1,2,3,4,8,9,11,17,41,50,56,62,78,93,116,29,34,44,54,60,64,75,118,120,124]
print('Subnet balances:')
for n in all_subnets:
    print(f'SN{n}:', holdings.get(n, 0.0))
