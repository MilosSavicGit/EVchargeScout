"""Simulated mirrors so the rotation logic is testable without hammering anyone."""
import time, sys
sys.path.insert(0,'.')
import overpass_pool as P

P.COOLDOWN_BUSY, P.COOLDOWN_BROKEN, P.FAILURE_DECAY = 2, 6, 3   # shrink the clock

class Fake(P.OverpassPool):
    """behaviour: dict host -> list of outcomes, consumed in order."""
    def __init__(self, urls, behaviour):
        super().__init__(urls, "test", verbose=True)
        self.behaviour = behaviour
        self.calls = []
    def _attempt(self, mirror, body):
        host = self._host(mirror)
        self.calls.append(host)
        seq = self.behaviour.get(host, [])
        out = seq.pop(0) if seq else "ok"
        if out == "ok":     return {"elements": [host]}, None
        if out == "busy":   return None, ("busy", "HTTP 429", None)
        if out == "broken": return None, ("broken", "HTTP 500", None)

URLS = ["https://a.example/api/interpreter",
        "https://b.example/api/interpreter",
        "https://c.example/api/interpreter"]

fails = []
def check(label, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'}  {label}{(' — ' + extra) if extra else ''}")
    if not cond: fails.append(label)

print("--- a busy mirror is skipped immediately, not retried ---")
p = Fake(URLS, {"a.example": ["busy"]})
t0 = time.time(); r = p.query("q"); el = time.time() - t0
check("fell through to b on the first try", r["elements"] == ["b.example"])
check("did not retry a", p.calls == ["a.example", "b.example"], f"calls={p.calls}")
check("no waiting involved", el < 0.5, f"{el:.2f}s")

print("\n--- a broken mirror is not tried again for the next country ---")
p = Fake(URLS, {"a.example": ["broken"]})
p.query("q1")
before = list(p.calls)
p.query("q2")                       # second country, same pool
new = p.calls[len(before):]
check("a skipped on the second query", "a.example" not in new, f"calls={new}")

print("\n--- cooldown expires, failure decays, mirror returns to rotation ---")
p = Fake(URLS, {"a.example": ["busy"]})
p.query("q1")
time.sleep(P.FAILURE_DECAY * 1.5)          # past cooldown AND past the decay window
p.calls.clear()
for i in range(3): p.query(f"q{i}")
check("a is used again once its failure has decayed",
      "a.example" in p.calls, f"calls={p.calls}")

print("\n--- healthy mirrors share the load ---")
p = Fake(URLS, {})
for i in range(6): p.query(f"q{i}")
used = set(p.calls)
check("work spread over every mirror", used == {"a.example","b.example","c.example"},
      f"calls={p.calls}")

print("\n--- all busy at once: waits, then succeeds ---")
p = Fake(URLS, {"a.example": ["busy"], "b.example": ["busy"], "c.example": ["busy"]})
t0 = time.time(); r = p.query("q"); el = time.time() - t0
check("recovered after the cooldown", r is not None, f"{el:.1f}s")
check("actually waited rather than spinning", el >= P.COOLDOWN_BUSY * 0.8, f"{el:.1f}s")

print("\n--- everything permanently down: raises, does not hang ---")
p = Fake(URLS, {h: ["broken"]*40 for h in ["a.example","b.example","c.example"]})
P.MAX_CYCLES = 2
t0 = time.time()
try:
    p.query("q"); check("should have raised", False)
except RuntimeError as e:
    check("raised RuntimeError", True, str(e)[:60])
check("gave up in reasonable time", time.time()-t0 < 60, f"{time.time()-t0:.1f}s")

print("\n--- a mirror still inside its cooldown is never touched ---")
p = Fake(URLS, {"a.example": ["broken"]})
p.query("q1")                      # a breaks, cooldown starts
p.calls.clear()
for i in range(4): p.query(f"q{i}")
check("broken mirror untouched while cooling",
      "a.example" not in p.calls, f"calls={p.calls}")
check("the healthy two carried the work",
      set(p.calls) == {"b.example","c.example"}, f"calls={p.calls}")

print("\n--- a busy mirror is preferred over a broken one ---")
p = Fake(URLS, {"a.example": ["broken"]*9, "b.example": ["busy"]})
p.query("q1")
time.sleep(P.COOLDOWN_BUSY * 1.6)   # b free again, a still broken-cooling
p.calls.clear()
p.query("q2")
check("busy-then-recovered beats still-broken",
      "a.example" not in p.calls, f"calls={p.calls}")

print("\n" + ("ALL PASS" if not fails else "FAILURES: " + ", ".join(fails)))
print("pool state:", p.report())
