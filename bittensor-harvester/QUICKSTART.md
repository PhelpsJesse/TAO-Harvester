# Quick Start

Requirements & Setup

1. Clone or open the project in your workspace.
2. Create a Python 3.12+ virtual environment and activate it.

```bash
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy the example .env and edit it with your configuration (do NOT commit secrets):

```bash
copy .env.example .env  # Windows
# or
cp .env.example .env    # macOS / Linux
```

Run a Test Cycle (dry-run)

```bash
python quickstart.py --test-cycle
```

Validate Config

```bash
python quickstart.py --check-config
```

Run a Live Cycle (only after validating .env and understanding risks)

```bash
python quickstart.py --run-cycle
```

Notes

- Use `--test-cycle` to perform mock/dry-run runs that do not submit transactions.
- All state is stored in `harvester.db` (SQLite). Do not commit this file.
- CSV exports are generated in the project root after each run: `rewards.csv`, `harvest.csv`, `sales.csv`, `withdrawals.csv`.
