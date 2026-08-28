#!/usr/bin/env python3
"""
overpass_pool.py — mirror rotation that treats "busy" differently from "broken".

WHY THIS IS NOT JUST RETRY-WITH-BACKOFF

Overpass mirrors fail in two quite different ways and the right response is
opposite in each case:

  BUSY   429 / 503 / 504, or a body saying rate_limited or timed out.
         The server is fine, it just has no free slot for you. Sitting there
         retrying the same host is the one thing that does not help - and it is
         also the rude option, because you are queueing while another mirror is
         idle. Move on IMMEDIATELY, come back later.

  BROKEN 500, connection refused, DNS failure, garbage response.
         Retrying quickly is pointless too, but for a different reason: this
         one may be down for hours. Put it in a long cooldown so a 56-country
         run does not pay for it 56 times.

The original code retried each mirror twice with 10s and 20s waits before
moving on. On the first real run kumi returned 500 twice, so every country
would have burned 30 seconds on a dead host before trying a live one. Across
56 countries that is 28 minutes of waiting for nothing.

Cooldowns are remembered ACROSS countries for exactly that reason.
"""

import json, random, time
import urllib.parse, urllib.request, urllib.error

BUSY_STATUS   = {429, 503, 504, 502}
BUSY_MARKERS  = ("rate_limited", "too many requests", "timed out",
                 "slot available after", "please check /api/status")

COOLDOWN_BUSY   = 60      # seconds — it has slots, just not now
COOLDOWN_BROKEN = 900     # seconds — assume it is out for a while
MAX_CYCLES      = 4       # full passes over the pool before giving up
FAILURE_DECAY   = 1800    # seconds a failure counts against a mirror

# Failures MUST decay. Without it, one 500 early in a 56-country run demotes
# that mirror for the whole run, and every remaining country lands on whichever
# host happened to answer first. That is worse for us (no redundancy left) and
# ruder to them (one donated server carrying the lot). Ties break on
# least-recently-used, so healthy mirrors take turns instead of one being
# hammered.


class Mirror:
    def __init__(self, url):
        self.url = url
        self.available_at = 0.0
        self.last_used = 0.0
        self.failures = []            # (when, kind) — pruned by FAILURE_DECAY
        self.busy = self.broken = self.ok = 0

    def ready(self, now):  return now >= self.available_at
    def wait(self, now):   return max(0.0, self.available_at - now)

    def penalty(self, now):
        """Recent failures only. A broken counts double a busy."""
        self.failures = [(t, k) for (t, k) in self.failures if now - t < FAILURE_DECAY]
        return sum(2 if k == "broken" else 1 for _, k in self.failures)

    def cool(self, seconds, kind):
        now = time.time()
        self.available_at = now + seconds
        self.failures.append((now, kind))
        if kind == "busy": self.busy += 1
        else:              self.broken += 1

    def __repr__(self):
        return f"{self.url.split('//')[1].split('/')[0]} ok={self.ok} busy={self.busy} broken={self.broken}"


class OverpassPool:
    def __init__(self, urls, ua, http_timeout=360, verbose=True):
        self.mirrors = [Mirror(u) for u in urls]
        self.ua = ua
        self.http_timeout = http_timeout
        self.verbose = verbose

    def _say(self, msg):
        if self.verbose: print(f"      {msg}", flush=True)

    def _host(self, m):
        return m.url.split("//")[1].split("/")[0]

    def _attempt(self, mirror, body):
        """Returns (data, None) on success, or (None, (kind, detail, retry_after))."""
        req = urllib.request.Request(
            mirror.url, data=body,
            headers={"User-Agent": self.ua, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.http_timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            low = raw[:2000].lower()
            if any(mk in low for mk in BUSY_MARKERS):
                return None, ("busy", "server said it is at capacity", None)
            return json.loads(raw), None
        except urllib.error.HTTPError as e:
            detail = f"HTTP {e.code}"
            retry_after = None
            try:
                ra = e.headers.get("Retry-After")
                if ra and ra.isdigit(): retry_after = int(ra)
            except Exception:                                    # noqa: BLE001
                pass
            body_txt = ""
            try: body_txt = e.read(2000).decode("utf-8", "replace").lower()
            except Exception: pass                               # noqa: BLE001
            if e.code in BUSY_STATUS or any(mk in body_txt for mk in BUSY_MARKERS):
                return None, ("busy", detail, retry_after)
            return None, ("broken", detail, retry_after)
        except json.JSONDecodeError:
            return None, ("broken", "response was not JSON", None)
        except Exception as e:                                   # noqa: BLE001
            return None, ("broken", type(e).__name__, None)

    def query(self, q):
        body = urllib.parse.urlencode({"data": q}).encode()
        last = "no attempt made"

        for cycle in range(1, MAX_CYCLES + 1):
            now = time.time()
            # Healthiest-first: fewest recent failures, then least recently used.
            # Fewest RECENT failures first; then least recently used, so equally
            # healthy mirrors share the work rather than one taking all of it.
            ready = sorted((m for m in self.mirrors if m.ready(now)),
                           key=lambda m: (m.penalty(now), m.last_used))
            if not ready:
                # Everything is cooling. Wait for whichever frees up soonest.
                soonest = min(self.mirrors, key=lambda m: m.available_at)
                nap = min(soonest.wait(now) + 1, 120)
                self._say(f"all mirrors cooling - waiting {nap:.0f}s")
                time.sleep(nap)
                continue

            for m in ready:
                m.last_used = time.time()
                data, err = self._attempt(m, body)
                if err is None:
                    m.ok += 1
                    m.available_at = 0.0          # proven good, clear any cooldown
                    return data
                kind, detail, retry_after = err
                cool = retry_after or (COOLDOWN_BUSY if kind == "busy" else COOLDOWN_BROKEN)
                cool *= (1 + 0.25 * random.random())       # jitter, avoid lockstep
                m.cool(cool, kind)
                last = f"{self._host(m)} {kind} ({detail})"
                self._say(f"{last} - skipping it for {cool:.0f}s, next mirror")

            if cycle < MAX_CYCLES:
                nap = min(20 * cycle, 90)
                self._say(f"cycle {cycle} exhausted - pausing {nap}s")
                time.sleep(nap)

        raise RuntimeError(f"all Overpass mirrors unavailable; last was {last}")

    def report(self):
        return " | ".join(repr(m) for m in self.mirrors)
