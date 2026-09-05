#!/usr/bin/env python3
"""Container healthcheck: exits 0 only when /health returns status ok."""
import json
import os
import sys
import urllib.request

port = os.environ.get("PORT", "8080")
url = "http://127.0.0.1:%s/health" % port
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if body.get("status") == "ok":
        print("healthy: %s" % body.get("mode", "unknown"))
        sys.exit(0)
    print("unhealthy: %s" % body, file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print("unhealthy: %s" % exc, file=sys.stderr)
    sys.exit(1)
