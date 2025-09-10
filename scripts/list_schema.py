#!/usr/bin/env python3
"""
List Supabase tables and columns via RPC (requires migration 013).

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from environment/.env
Usage:
  python scripts/list_schema.py [schema]
"""

import os
import sys
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

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

url = f"{base}/rest/v1/rpc/list_schema"
headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}
payload = json.dumps({'p_schema': schema}).encode('utf-8')

try:
    req = Request(url, data=payload, headers=headers, method='POST')
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    # Group columns by table
    from collections import defaultdict
    grouped = defaultdict(list)
    for row in data:
        t = f"{row['table_schema']}.{row['table_name']}"
        grouped[t].append(f"{row['column_name']} ({row['data_type']})")

    print(f"Tables and columns in schema '{schema}':")
    for table, cols in grouped.items():
        print(f"- {table}: {', '.join(cols)}")
except HTTPError as e:
    body = e.read().decode('utf-8') if hasattr(e, 'read') else ''
    print(f"HTTPError {e.code}: {body}")
    sys.exit(2)
except URLError as e:
    print(f"URLError: {e}")
    sys.exit(3)
