"""Live end-to-end smoke test against the running local server."""
import httpx
import sys

BASE = "http://127.0.0.1:8080"
passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✅ {label}")
        passed += 1
    else:
        print(f"  ❌ {label} {detail}")
        failed += 1


# 1. Health
r = httpx.get(f"{BASE}/health")
check("Health 200", r.status_code == 200)
check("Health body", r.json() == {"status": "ok", "version": "1.0.0"})

# 2. Homepage
r = httpx.get(f"{BASE}/")
check("Homepage 200", r.status_code == 200)

# 3. Create a plan
payload = {
    "destination": "Tokyo",
    "start_date": "2026-06-10",
    "end_date": "2026-06-12",
    "budget_amount": 1500,
    "budget_currency": "USD",
    "interests": ["culture", "food"],
    "travel_style": "couple",
    "group_size": 2,
}
r = httpx.post(f"{BASE}/api/plan", json=payload, timeout=30)
check("Create plan 200", r.status_code == 200, r.text[:200])
data = r.json()
plan_id = data.get("id") or data.get("plan_id")
check("Plan has id", bool(plan_id))
check("Plan has days", len(data.get("days", [])) > 0)

# 4. Get plan back
r2 = httpx.get(f"{BASE}/api/plan/{plan_id}")
check("Get plan 200", r2.status_code == 200)
check("Get plan id matches", r2.json().get("id") == plan_id)

# 5. Refine plan
r3 = httpx.post(f"{BASE}/api/plan/{plan_id}/refine", json={"message": "Add more food spots"}, timeout=30)
check("Refine plan 200", r3.status_code == 200)

# 6. Export iCal
r4 = httpx.get(f"{BASE}/api/plan/{plan_id}/export/ics")
check("Export ICS 200", r4.status_code == 200)
check("ICS content-type", "calendar" in r4.headers.get("content-type", ""))

# 7. Validation: zero budget should fail
bad = {**payload, "budget_amount": 0}
r5 = httpx.post(f"{BASE}/api/plan", json=bad)
check("Zero budget rejected (422)", r5.status_code == 422)

# 8. 404 for non-existent plan
r6 = httpx.get(f"{BASE}/api/plan/nonexistent-plan-id-xyz")
check("Non-existent plan 404", r6.status_code == 404)

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
else:
    print("🎉 All end-to-end checks passed!")
