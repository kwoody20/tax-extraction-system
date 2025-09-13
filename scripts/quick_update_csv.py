#!/usr/bin/env python3
"""
Quick CSV-only updater for property fields.

This interactive CLI lets you review each property row from a CSV export
and update account_number and appraised_value locally. No API/DB calls
are made — when finished, import the updated CSV back into your system.

Usage:
  python scripts/quick_update_csv.py --csv properties_export.csv --auto-open --filter missing

Options:
  --csv PATH            Input CSV exported from scripts/export_property_fields.py
  --output PATH         Output CSV (default: <input>.updated.csv)
  --filter              all | missing | missing-account | missing-appraised (default: missing)
  --auto-open           Automatically open the tax bill link for each row
  --save-every N        Autosave after every N processed rows (default: 10)

Controls (during review):
  [Enter]  skip/next
  o        open tax link in browser
  e        edit and save (prompts for values; updates CSV in-memory)
  s        save to output CSV now
  q        save and quit
"""

import argparse
import csv
import os
import sys
import webbrowser
from typing import Dict, List, Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CSV-only property updater")
    p.add_argument("--csv", required=True, help="Path to input CSV export")
    p.add_argument("--output", default=None, help="Path to output CSV (defaults to <input>.updated.csv)")
    p.add_argument(
        "--filter",
        choices=["all", "missing", "missing-account", "missing-appraised"],
        default="missing",
        help="Which rows to review"
    )
    p.add_argument("--auto-open", action="store_true", help="Auto-open tax link for each row")
    p.add_argument("--save-every", type=int, default=10, help="Autosave cadence (rows)")
    return p.parse_args()


def want_row(row: Dict[str, Any], mode: str) -> bool:
    acct = (row.get("account_number") or "").strip()
    appr = (row.get("appraised_value") or "").strip()
    if mode == "all":
        return True
    if mode == "missing":
        return (not acct) or (not appr)
    if mode == "missing-account":
        return not acct
    if mode == "missing-appraised":
        return not appr
    return True


def load_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def save_csv(path: str, rows: List[Dict[str, Any]], fieldnames: List[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def print_row(row: Dict[str, Any], index: int, total: int):
    print("-" * 80)
    print(f"[{index+1}/{total}] {row.get('property_name') or ''}  ({row.get('property_id')})")
    print(f"  Account #:   {row.get('account_number') or ''}")
    print(f"  Appraised $: {row.get('appraised_value') or ''}")
    print(f"  Tax URL:     {row.get('tax_bill_link') or ''}")


def to_float_or_none(value: str):
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        # Allow comma separators
        return float(s.replace(",", ""))
    except Exception:
        return None


def main():
    args = parse_args()
    rows = load_csv(args.csv)
    out_path = args.output or (os.path.splitext(args.csv)[0] + ".updated.csv")

    # Ensure target columns exist in output
    fieldnames = list(rows[0].keys()) if rows else [
        "property_id", "property_name", "tax_bill_link", "account_number", "appraised_value"
    ]
    for col in ("account_number", "appraised_value"):
        if col not in fieldnames:
            fieldnames.append(col)

    # Determine rows under review
    candidates = [r for r in rows if want_row(r, args.filter)]
    total = len(candidates)
    if total == 0:
        print("No rows matched the selected filter.")
        # Still write a pass-through CSV for consistency
        save_csv(out_path, rows, fieldnames)
        print(f"Wrote {out_path}")
        return

    processed = 0
    for idx, row in enumerate(candidates):
        print_row(row, idx, total)

        if args.auto_open and row.get("tax_bill_link"):
            try:
                webbrowser.open(row["tax_bill_link"], new=2)
            except Exception:
                pass

        while True:
            cmd = input("Command [Enter=skip | o=open | e=edit | s=save-csv | q=quit]: ").strip().lower()
            if cmd == "":
                break  # next row
            if cmd == "q":
                save_csv(out_path, rows, fieldnames)
                print(f"Saved progress to {out_path}")
                sys.exit(0)
            if cmd == "o":
                url = row.get("tax_bill_link")
                if url:
                    webbrowser.open(url, new=2)
                else:
                    print("No tax URL available.")
                continue
            if cmd == "s":
                save_csv(out_path, rows, fieldnames)
                print(f"Saved CSV to {out_path}")
                continue
            if cmd == "e":
                current_acct = (row.get("account_number") or "").strip()
                current_appr = (row.get("appraised_value") or "").strip()
                new_acct = input(f"  Account Number [{current_acct}]: ").strip()
                new_appr_raw = input(f"  Appraised Value [{current_appr}]: ").strip()
                new_appr = to_float_or_none(new_appr_raw) if new_appr_raw != "" else None

                # Update local row
                row["account_number"] = new_acct if new_acct != "" else current_acct
                if new_appr_raw != "":
                    # If the user entered a non-empty value but it failed to parse, keep original
                    if new_appr is not None:
                        row["appraised_value"] = new_appr
                    else:
                        print("  Invalid number; appraised value unchanged.")
                print("  Updated locally.")
                break  # next row

        processed += 1
        if args.save_every and processed % args.save_every == 0:
            save_csv(out_path, rows, fieldnames)
            print(f"Auto-saved to {out_path}")

    # Final write-out
    save_csv(out_path, rows, fieldnames)
    print(f"Done. Wrote {out_path}")


if __name__ == "__main__":
    main()

