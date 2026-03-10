# INDEX

Short navigation for the repository.

Files you will likely use first:

- `REQUIREMENTS_SPEC_v1.3.md` — Active configuration-control requirements baseline
- `LESSONS_LEARNED_PRESERVED_2026-03-10.md` — Preserved pre-rewrite lessons from existing code
- `IMPLEMENTATION_CHECKLIST_v1.3.md` — Prioritized Phase 1/2/3 implementation plan under v1.3 controls
- `QUICKSTART.md` — Quick setup and run commands
- `README.md` — Full documentation and architecture
- `IMPLEMENTATION_GUIDE.md` — How to implement real Substrate and Kraken APIs
- `PROJECT_SUMMARY.md` — High-level status and next steps
- `src/main.py` — Orchestrator for the daily harvest cycle
- `src/config.py` — Loads `.env` configuration
- `src/database.py` — SQLite schema & helpers
- `src/accounting.py` — Reward delta computation
- `src/harvest.py` — Harvest policy logic
- `src/executor.py` — Execution stubs for on-chain actions
- `src/export.py` — CSV export for taxes
- `src/kraken.py` — Kraken integration stubs

Run tests:

```bash
python -m unittest discover tests -v
```

Run a dry-run harvest:

```bash
python quickstart.py --test-cycle
```

For implementation detail, see `IMPLEMENTATION_GUIDE.md`.
