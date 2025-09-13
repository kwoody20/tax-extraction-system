#!/usr/bin/env python3
"""
Export selected fields from the `properties` table to CSV/JSON.

Fields exported by default:
  - property_id
  - property_name
  - tax_bill_link
  - account_number
  - appraised_value (if the column exists)

Environment:
  - SUPABASE_URL (required)
  - SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY or SUPABASE_ANON_KEY (one required)

Usage examples:
  python scripts/export_property_fields.py --output properties.csv
  python scripts/export_property_fields.py --format json --output properties.json
  python scripts/export_property_fields.py --state TX --jurisdiction "Harris County"
"""

import os
import sys
import csv
import json
import argparse
from typing import List, Dict, Any

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # Optional

try:
    from supabase import create_client
except Exception as e:
    print("Supabase client not installed. Please `pip install supabase`.", file=sys.stderr)
    raise


def get_supabase_client():
    if load_dotenv:
        load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )

    if not url or not key:
        print("Missing SUPABASE_URL or key (SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY/SUPABASE_ANON_KEY)", file=sys.stderr)
        sys.exit(2)

    return create_client(url, key)


def column_exists(client, table: str, column: str) -> bool:
    try:
        # Minimal test query to check column presence
        client.table(table).select(column).limit(1).execute()
        return True
    except Exception:
        return False


def fetch_properties(
    client,
    fields: List[str],
    state: str = None,
    jurisdiction: str = None,
    parent_entity_id: str = None,
    page_size: int = 1000,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    offset = 0

    while True:
        query = client.table("properties").select(
            ",".join(fields)
        )

        if state:
            query = query.eq("state", state)
        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)
        if parent_entity_id:
            # properties.parent_entity_id references entities.entity_id
            query = query.eq("parent_entity_id", parent_entity_id)

        query = query.range(offset, offset + page_size - 1)

        resp = query.execute()
        data = resp.data or []
        results.extend(data)
        if len(data) < page_size:
            break
        offset += page_size

    return results


def write_csv(rows: List[Dict[str, Any]], output_path: str, fields: List[str]):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            # Ensure only requested fields are written
            writer.writerow({k: r.get(k) for k in fields})


def write_json(rows: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Export selected fields from properties table")
    parser.add_argument("--output", "-o", default="properties_export.csv", help="Output file path")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv", help="Output format")
    parser.add_argument("--state", help="Filter by state (exact match)")
    parser.add_argument("--jurisdiction", help="Filter by jurisdiction (exact match)")
    parser.add_argument("--entity", dest="parent_entity_id", help="Filter by parent entity ID (entities.entity_id)")
    args = parser.parse_args()

    client = get_supabase_client()

    # Base fields to export
    fields = [
        "property_id",
        "property_name",
        "tax_bill_link",
        "account_number",
    ]

    # Add appraised_value if present
    if column_exists(client, "properties", "appraised_value"):
        fields.append("appraised_value")
    else:
        print("Note: 'appraised_value' column not found; exporting without it.")

    try:
        rows = fetch_properties(
            client,
            fields=fields,
            state=args.state,
            jurisdiction=args.jurisdiction,
            parent_entity_id=args.parent_entity_id,
        )
    except Exception as e:
        print(f"Query failed with selected fields: {e}", file=sys.stderr)
        print("Retrying without 'appraised_value' if present...")
        fallback_fields = [c for c in fields if c != "appraised_value"]
        rows = fetch_properties(
            client,
            fields=fallback_fields,
            state=args.state,
            jurisdiction=args.jurisdiction,
            parent_entity_id=args.parent_entity_id,
        )
        fields = fallback_fields

    if args.format == "csv":
        write_csv(rows, args.output, fields)
    else:
        write_json(rows, args.output)

    print(f"Exported {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()

