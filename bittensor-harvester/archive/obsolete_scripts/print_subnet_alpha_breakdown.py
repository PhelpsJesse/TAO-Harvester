from src.taostats import TaostatsClient

if __name__ == "__main__":
    client = TaostatsClient()
    result = client.get_alpha_balance_by_subnet('5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh')
    print('Subnet alpha breakdown:')
    for k, v in sorted(result.get('subnet_alpha', {}).items()):
        print(f'SN{k}: {v}')
    print(f"Total subnets: {len(result.get('subnet_alpha', {}))}")
    print(f"Total alpha: {result.get('total_alpha', 0.0)}")
