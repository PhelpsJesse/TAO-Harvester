import os

def main():
    url = os.getenv("ARCHIVE_RPC_URL", "wss://archive.chain.opentensor.ai:443")
    try:
        import bittensor as bt
        st = bt.Subtensor(chain_endpoint=url)
        try:
            num = st.substrate.get_block_number()
        except Exception:
            head = st.substrate.get_block_header()
            num = head.get("number")
            if isinstance(num, str) and num.startswith("0x"):
                num = int(num, 16)
        print(f"Block number (Subtensor): {num}")
        bh = st.substrate.get_block_hash(num)
        print(f"Block hash (Subtensor): {bh}")
    except Exception as e:
        print(f"Subtensor error: {e}")

if __name__ == "__main__":
    main()
