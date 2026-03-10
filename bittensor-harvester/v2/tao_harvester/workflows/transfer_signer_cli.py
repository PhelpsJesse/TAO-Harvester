from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TAO Harvester transfer signer CLI (Tier 3)")
    parser.add_argument("--batch-date", required=True, help="Batch date (YYYY-MM-DD)")
    parser.add_argument("--wallet-address", required=True, help="Wallet address for pending batch")
    parser.add_argument("--dry-run", action="store_true", help="Keep read-only mode")
    return parser


def main() -> int:
    parser = build_parser()
    _ = parser.parse_args()
    raise NotImplementedError("Tier 3 transfer signing CLI not implemented in this phase")


if __name__ == "__main__":
    raise SystemExit(main())
