#!/usr/bin/env python3
"""
Interactive CLI to review properties from a CSV export and update
account_number and appraised_value via the API.

Usage:
  python scripts/quick_update_cli.py --csv properties_export.csv --update-api \
      --output updated_properties.csv --auto-open

Options:
  --csv PATH            Input CSV exported from scripts/export_property_fields.py
  --output PATH         Output CSV to write updates (default: properties_export.updated.csv)
  --filter              Which rows to review: all | missing | missing-account | missing-appraised
  --api-url URL         API base URL (default: env API_URL or http://localhost:8000)
  --update-api          Actually call the API to persist changes (otherwise dry-run)
  --auto-open           Automatically open the tax bill link in browser for each row

Controls (during review):
  [Enter]  skip/next
  o        open tax link in browser
  e        edit and save (prompts for values; calls API if --update-api)
  s        save current values to output CSV only (no API call)
  q        quit
"""

import argparse
import csv
import os
import sys
import webbrowser
from typing import Dict, List, Any, Tuple

try:
    # Optional: direct Supabase mode
    from supabase import create_client as create_supabase_client  # type: ignore
except Exception:
    create_supabase_client = None  # Only needed for --direct-supabase

import requests


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Review and update property fields from CSV")
    p.add_argument("--csv", required=True, help="Path to input CSV export")
    p.add_argument("--output", default=None, help="Path to output CSV (defaults to <input>.updated.csv)")
    p.add_argument(
        "--filter",
        choices=["all", "missing", "missing-account", "missing-appraised"],
        default="missing",
        help="Rows to review"
    )
    p.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    p.add_argument("--update-api", action="store_true", help="Persist updates via API")
    p.add_argument("--auto-open", action="store_true", help="Auto-open tax link for each row")
    p.add_argument(
        "--direct-supabase",
        action="store_true",
        help="Bypass API and update Supabase directly (requires SUPABASE_URL and key in env)",
    )
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
    print(f"  Jurisdiction: {row.get('jurisdiction', '')}  State: {row.get('state', '')}")
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
        return float(s.replace(",", ""))
    except Exception:
        return None


def push_update(api_url: str, ident: Dict[str, Any], account_number: str | None, appraised_value: float | None) -> Dict[str, Any]:
    # ident should contain server-accepted identifier; prefer id, else property_id
    payload_update: Dict[str, Any] = {}
    if "id" in ident and ident["id"]:
        payload_update["id"] = ident["id"]
    elif "property_id" in ident and ident["property_id"]:
        payload_update["property_id"] = ident["property_id"]
    else:
        raise RuntimeError("Missing identifier (id or property_id)")

    payload = {"updates": [payload_update]}
    if account_number is not None:
        payload_update["account_number"] = account_number or None
    if appraised_value is not None:
        payload_update["appraised_value"] = appraised_value
    payload["validate"] = True

    resp = requests.put(f"{api_url}/api/v1/properties/bulk", json=payload, timeout=20)
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"API {resp.status_code}: {data}")
    return data


def get_direct_supabase_client():
    if not create_supabase_client:
        raise RuntimeError("Supabase client not installed. pip install supabase")
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL and key in environment for --direct-supabase mode")
    return create_supabase_client(url, key)


def push_update_direct(supabase_client, property_id: str, account_number: str | None, appraised_value: float | None) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if account_number is not None:
        data["account_number"] = account_number or None
    if appraised_value is not None:
        data["appraised_value"] = appraised_value
    if not data:
        return {"message": "no-op"}
    resp = supabase_client.table("properties").update(data).eq("property_id", property_id).execute()
    return {"count": len(resp.data or [])}


def fetch_id_map(api_url: str, page_size: int = 1000, max_pages: int = 1000) -> Dict[str, str]:
    """Fetch mapping from property_id -> id using the API.
    Requires the API to support select_fields on /api/v1/properties.
    """
    mapping: Dict[str, str] = {}
    offset = 0
    for _ in range(max_pages):
        params = {
            "limit": page_size,
            "offset": offset,
            "select_fields": "id,property_id",
            "sort_by": "id",
            "sort_order": "asc",
        }
        resp = requests.get(f"{api_url}/api/v1/properties", params=params, timeout=20)
        if resp.status_code != 200:
            break
        data = resp.json() or {}
        rows = data.get("properties") or data.get("data") or []
        if not rows:
            break
        for r in rows:
            pid = r.get("property_id")
            rid = r.get("id")
            if pid and rid:
                mapping[str(pid)] = str(rid)
        if len(rows) < page_size:
            break
        offset += page_size
    return mapping


def main():
    args = parse_args()
    rows = load_csv(args.csv)
    out_path = args.output or (os.path.splitext(args.csv)[0] + ".updated.csv")
    total = sum(1 for r in rows if want_row(r, args.filter))
    if total == 0:
        print("No rows matched the selected filter.")
        return

    # Setup update method
    direct_client = None
    id_map: Dict[str, str] = {}
    if args.update_api and not args.direct_supabase:
        try:
            print("Fetching id map from API...")
            id_map = fetch_id_map(args.api_url)
            print(f"Loaded {len(id_map)} id mappings.")
        except Exception as e:
            print(f"Warning: failed to build id map: {e}")
    elif args.direct_supabase:
        try:
            direct_client = get_direct_supabase_client()
            print("Direct Supabase client initialized.")
        except Exception as e:
            print(f"Failed to initialize direct Supabase client: {e}")
            sys.exit(2)

    # Ensure expected columns exist; if not, add them for output
    fieldnames = list(rows[0].keys())
    for col in ("account_number", "appraised_value"):
        if col not in fieldnames:
            fieldnames.append(col)

    seen = 0
    for i, row in enumerate(rows):
        if not want_row(row, args.filter):
            continue
        seen += 1
        print_row(row, seen-1, total)

        if args.auto_open and row.get("tax_bill_link"):
            try:
                webbrowser.open(row["tax_bill_link"], new=2)
            except Exception:
                pass

        while True:
            cmd = input("Command [Enter=skip | o=open | e=edit | s=save-csv | q=quit]: ").strip().lower()
            if cmd == "" :
                break  # next row
            if cmd == "q":
                # Save progress and exit
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
                # Prompt for edits
                current_acct = (row.get("account_number") or "").strip()
                current_appr = (row.get("appraised_value") or "").strip()
                new_acct = input(f"  Account Number [{current_acct}]: ").strip() or current_acct
                new_appr_raw = input(f"  Appraised Value [{current_appr}]: ").strip() or current_appr
                new_appr = to_float_or_none(new_appr_raw)
                if new_appr_raw and new_appr is None:
                    print("  Invalid number; leaving appraised value unchanged.")
                    new_appr = to_float_or_none(current_appr)

                # Update via API or direct Supabase if requested
                if args.update_api and not args.direct_supabase:
                    try:
                        prop_id = str(row.get("property_id")) if row.get("property_id") else None
                        ident: Dict[str, Any] = {}
                        # Prefer server 'id' if available
                        if prop_id and prop_id in id_map:
                            ident["id"] = id_map[prop_id]
                        elif prop_id:
                            ident["property_id"] = prop_id
                        else:
                            raise RuntimeError("Row missing property_id; cannot update")

                        result = push_update(
                            args.api_url,
                            ident,
                            new_acct if new_acct != current_acct else None,
                            new_appr if str(new_appr) != str(current_appr) else None,
                        )
                        print(f"  API updated: {result.get('message') or 'ok'}")
                    except Exception as e:
                        print(f"  API update failed: {e}")
                        # Still allow local CSV save
                elif args.direct_supabase:
                    try:
                        prop_id = str(row.get("property_id")) if row.get("property_id") else None
                        if not prop_id:
                            raise RuntimeError("Row missing property_id; cannot update")
                        result = push_update_direct(
                            direct_client,
                            prop_id,
                            new_acct if new_acct != current_acct else None,
                            new_appr if str(new_appr) != str(current_appr) else None,
                        )
                        print(f"  DB updated: {result}")
                    except Exception as e:
                        print(f"  Direct update failed: {e}")

                # Update in-memory row for output CSV
                row["account_number"] = new_acct
                if new_appr is not None:
                    row["appraised_value"] = new_appr
                print("  Updated locally.")
                break  # move to next row

        # Auto-save every 10 rows processed
        if seen % 10 == 0:
            save_csv(out_path, rows, fieldnames)
            print(f"Auto-saved to {out_path}")

    # Final save
    save_csv(out_path, rows, fieldnames)
    print(f"Done. Wrote {out_path}")


if __name__ == "__main__":
    main()
