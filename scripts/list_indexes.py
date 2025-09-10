#!/usr/bin/env python3
"""
List all indexes and definitions from Supabase for a schema (default: public).
Requires migration 014 (public.list_indexes) to be applied.

Usage:
  python scripts/list_indexes.py [schema]

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (reads .env if available)
"""

import os
import sys
import json
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

schema = sys.argv[1] if len(sys.argv) > 1 else 'public'
base = os.environ.get('SUPABASE_URL', '').rstrip('/')
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
if not base or not key:
    print('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY')
    sys.exit(1)

url = f"{base}/rest/v1/rpc/list_indexes"
headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}
payload = json.dumps({'p_schema': schema}).encode('utf-8')

req = Request(url, data=payload, headers=headers, method='POST')
with urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode('utf-8'))

from collections import defaultdict
grouped = defaultdict(list)
for row in data:
    t = f"{row['schemaname']}.{row['tablename']}"
    grouped[t].append((row['indexname'], row['indexdef']))

print(f"Indexes in schema '{schema}':")
for table, idxs in grouped.items():
    print(f"- {table}")
    for name, definition in idxs:
        print(f"    • {name}: {definition}")
