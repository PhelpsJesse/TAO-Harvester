import requests
from bs4 import BeautifulSoup

WALLET = "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh"
BASE_URL = f"https://taostats.io/account/{WALLET}"

# Fetch all pages of subnet holdings
def fetch_all_subnet_balances():
    balances = {}
    page = 1
    while True:
        url = f"{BASE_URL}?page={page}"
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Find all rows in the subnet holdings table
        rows = soup.find_all("tr")
        found = 0
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 5:
                # Subnet name and ID
                subnet = cols[0].get_text(strip=True)
                # Balance TAO (last column)
                balance_tao = cols[-1].get_text(strip=True)
                # Try to extract SN number and TAO value
                import re
                sn_match = re.search(r"SN(\d+)", subnet)
                tao_match = re.search(r"τ\s*([\d\.]+)", balance_tao)
                if sn_match and tao_match:
                    sn = int(sn_match.group(1))
                    tao = float(tao_match.group(1))
                    balances[sn] = tao
                    found += 1
        if found == 0:
            break  # No more data
        page += 1
    return balances

if __name__ == "__main__":
    all_balances = fetch_all_subnet_balances()
    print(f"Found {len(all_balances)} subnets with TAO balances:")
    for sn, tao in sorted(all_balances.items()):
        print(f"SN{sn}: {tao} TAO")
