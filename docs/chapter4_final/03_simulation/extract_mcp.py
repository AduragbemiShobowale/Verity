"""Extracts the JSON rows from a saved Supabase MCP execute_sql result file.
Usage: python3 extract_mcp.py <mcp result file> <output.json>"""
import json, re, sys
outer = json.loads(open(sys.argv[1]).read())['result']
s = re.search(r'>\n(\[\{.*\}\])\n<', outer, re.S).group(1)
val = list(json.loads(s)[0].values())[0]
json.dump(val, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)
print(sys.argv[2], len(val))
