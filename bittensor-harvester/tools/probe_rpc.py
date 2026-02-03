import requests, json

ENDPOINTS = [
    "https://archive-api.bittensor.com/rpc",
    "https://archive.bittensor.org/rpc",
    "https://archive.bittensor.com",
    "https://api.bittensor.com/rpc",
    "https://rpc.bittensor.com",
    "https://node.bittensor.com/rpc",
    "http://localhost:9933",
]

payload = {"jsonrpc":"2.0","method":"system_blockNumber","params":[],"id":1}

results = []
for e in ENDPOINTS:
    try:
        r = requests.post(e, json=payload, timeout=10)
        status = r.status_code
        text = r.text[:500]
        ok = False
        try:
            j = r.json()
            if 'result' in j:
                ok = True
        except Exception:
            j = None
        results.append((e, status, ok, text))
    except Exception as ex:
        results.append((e, None, False, str(ex)))

print(json.dumps(results, indent=2))
