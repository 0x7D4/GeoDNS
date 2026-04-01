import urllib.request, json
cases = [
    ("google.com", "MX"),
    ("google.com", "TXT"),
    ("definitely-nxdomain-xyz123.com", "A"),
    ("google.com", "AAAA")
]

for d, rt in cases:
    req = urllib.request.Request('http://localhost:8053/resolve', data=json.dumps({'domain': d, 'record_type': rt}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    res = urllib.request.urlopen(req)
    out = json.loads(res.read().decode('utf-8'))
    print(f"--- {d} {rt} ---")
    print(f"Status: {out['status']}")
    print(f"Answers: {out['answers']}")
    print(f"TTL: {out['ttl']}")
    print(f"Time (ms): {out['query_time_ms']}")
    print(f"NS: {out['nameserver_used']}")
