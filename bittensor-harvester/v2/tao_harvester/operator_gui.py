from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Button, Entry, Frame, Label, StringVar, Tk, filedialog, messagebox
from tkinter import scrolledtext, simpledialog

from dotenv import load_dotenv

from v2.tao_harvester.modules.opentensor_staking_foundation import (
    REQUIRED_EXECUTION_CONFIRMATION,
    build_unstake_requests,
    execute_staking_workflow,
)
from v2.tao_harvester.modules.sync_openclaw_db import fetch_remote_db, validate_local_db
from v2.tao_harvester.config.app_config import AppConfig


DEFAULT_MAX_DB_STALENESS_DAYS = 1


def suggest_expected_db_date(report_path: str) -> str:
    try:
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()
    raw = payload.get("report_date")
    if isinstance(raw, str) and raw:
        return raw
    return datetime.now(timezone.utc).date().isoformat()


def build_preview_summary(report_path: str) -> dict[str, object]:
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    requests = build_unstake_requests(payload)
    total_alpha = sum(float(request.alpha_amount) for request in requests)
    return {
        "report_date": str(payload.get("report_date") or "unknown"),
        "request_count": len(requests),
        "total_alpha_to_unstake": total_alpha,
        "netuids": [request.netuid for request in requests],
    }


class OperatorGuiApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("TAO Harvester Operator")
        self.root.geometry("980x720")

        load_dotenv(override=True)
        self.config = AppConfig.from_env()

        self.report_path_var = StringVar(value="reports/v2_calculate_harvest_2026-03-24.json")
        self.expected_db_date_var = StringVar(value=suggest_expected_db_date(self.report_path_var.get()))
        self.output_path_var = StringVar(value="")
        self.status_var = StringVar(value="Ready")

        self._build_layout()
        self._set_status("Ready")

    def _build_layout(self) -> None:
        container = Frame(self.root)
        container.pack(fill=BOTH, expand=True, padx=12, pady=12)

        self._add_row(container, "Harvest Report JSON", self.report_path_var, browse=True)
        self._add_row(container, "Expected DB Date", self.expected_db_date_var)
        self._add_row(container, "Optional Output JSON", self.output_path_var, browse=True, save=True)

        button_bar = Frame(container)
        button_bar.pack(fill=BOTH, pady=(8, 8))
        self.sync_button = Button(button_bar, text="Sync + Validate DB", command=self.sync_db)
        self.sync_button.pack(side=LEFT, padx=(0, 8))
        self.preview_button = Button(button_bar, text="Preview Destake", command=self.preview_requests)
        self.preview_button.pack(side=LEFT, padx=(0, 8))
        self.execute_button = Button(button_bar, text="Execute Destake", command=self.execute_destake)
        self.execute_button.pack(side=LEFT, padx=(0, 8))
        self.open_output_button = Button(button_bar, text="Open Output Folder", command=self.open_output_folder)
        self.open_output_button.pack(side=LEFT)

        status_row = Frame(container)
        status_row.pack(fill=BOTH, pady=(0, 8))
        Label(status_row, text="Status:", width=14, anchor="w").pack(side=LEFT)
        Label(status_row, textvariable=self.status_var, anchor="w").pack(side=LEFT)

        self.output_text = scrolledtext.ScrolledText(container, wrap="word")
        self.output_text.pack(fill=BOTH, expand=True)

    def _add_row(self, parent: Frame, label: str, variable: StringVar, *, browse: bool = False, save: bool = False) -> None:
        row = Frame(parent)
        row.pack(fill=BOTH, pady=(0, 8))
        Label(row, text=label, width=18, anchor="w").pack(side=LEFT)
        entry = Entry(row, textvariable=variable)
        entry.pack(side=LEFT, fill=BOTH, expand=True)
        if browse:
            if save:
                Button(row, text="Browse", command=self.choose_output_path).pack(side=RIGHT, padx=(8, 0))
            else:
                Button(row, text="Browse", command=self.choose_report_path).pack(side=RIGHT, padx=(8, 0))

    def choose_report_path(self) -> None:
        path = filedialog.askopenfilename(
            title="Select calculate_harvest JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self.report_path_var.set(path)
        self.expected_db_date_var.set(suggest_expected_db_date(path))

    def choose_output_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Select output JSON path",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.output_path_var.set(path)

    def sync_db(self) -> None:
        self._run_background_task("Syncing OpenClaw DB", self._sync_db_task)

    def preview_requests(self) -> None:
        self._run_background_task("Building preview", self._preview_task)

    def execute_destake(self) -> None:
        confirmation = simpledialog.askstring(
            "Confirm Destake Execution",
            f"Type {REQUIRED_EXECUTION_CONFIRMATION} to continue:",
            parent=self.root,
        )
        if confirmation != REQUIRED_EXECUTION_CONFIRMATION:
            messagebox.showwarning("Execution cancelled", "Confirmation token mismatch. Execution was not started.")
            return
        self._run_background_task("Executing destake workflow", self._execute_task, confirmation)

    def open_output_folder(self) -> None:
        output_path = self.output_path_var.get().strip()
        if output_path:
            folder = Path(output_path).resolve().parent
        else:
            folder = (Path.cwd() / "reports").resolve()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Open Folder Failed", str(exc))

    def _sync_db_task(self) -> str:
        self.config = AppConfig.from_env()
        fetch_remote_db(self.config)
        report = validate_local_db(
            db_path=self.config.openclaw_handoff.local_db_path,
            expected_date=datetime.fromisoformat(self.expected_db_date_var.get()).date(),
            max_staleness_days=DEFAULT_MAX_DB_STALENESS_DAYS,
            min_snapshots=1,
            min_reconciliations=1,
        )
        return json.dumps(report, indent=2)

    def _preview_task(self) -> str:
        summary = build_preview_summary(self.report_path_var.get())
        return json.dumps(summary, indent=2)

    def _execute_task(self, confirmation: str) -> str:
        payload, output_file = execute_staking_workflow(
            input_path=self.report_path_var.get(),
            execute=True,
            output_path=self.output_path_var.get().strip() or None,
            confirmation=confirmation,
            skip_db_sync_fetch=False,
            expected_db_date=self.expected_db_date_var.get().strip() or None,
            max_db_staleness_days=DEFAULT_MAX_DB_STALENESS_DAYS,
            min_db_snapshots=1,
            min_db_reconciliations=1,
        )
        self.output_path_var.set(output_file.as_posix())
        return json.dumps(payload, indent=2)

    def _run_background_task(self, status: str, target, *args) -> None:
        self._set_status(status)
        self._set_buttons_enabled(False)

        def runner() -> None:
            try:
                result = target(*args)
                self.root.after(0, lambda: self._handle_success(result))
            except Exception as exc:
                detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                stack = traceback.format_exc()
                self.root.after(0, lambda: self._handle_error(detail, stack))

        threading.Thread(target=runner, daemon=True).start()

    def _handle_success(self, output: str) -> None:
        self.output_text.delete("1.0", END)
        self.output_text.insert("1.0", output)
        self._set_status("Complete")
        self._set_buttons_enabled(True)

    def _handle_error(self, detail: str, stack: str) -> None:
        self.output_text.delete("1.0", END)
        self.output_text.insert("1.0", f"ERROR\n\n{detail}\n\n{stack}")
        self._set_status("Failed")
        self._set_buttons_enabled(True)
        messagebox.showerror("TAO Harvester Operator", detail)

    def _set_status(self, value: str) -> None:
        self.status_var.set(value)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (self.sync_button, self.preview_button, self.execute_button, self.open_output_button):
            button.configure(state=state)


def main() -> int:
    root = Tk()
    app = OperatorGuiApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
