"""Seed a demo intake session with 15 BOM requirements."""
import requests

BASE = "http://127.0.0.1:8000/api"
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@conductoragain.local", "password": "ChangeMe123!"})
h = {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}

content = """1. User login with email/password and OAuth2 SSO support
2. Create and edit Production BOM with version history and draft mode
3. Circular reference detection - prevent self-reference on save with DFS algorithm
4. BOM comparison tool - diff two versions side by side with visual highlighting
5. Export BOM to Excel with cost roll-up and multi-level indentation
6. Multi-level approval workflow with sign-off routing by BOM value threshold
7. Real-time inventory integration with ERP system via REST API
8. Audit trail for all BOM changes with user attribution and timestamps
9. Role-based access control: viewers, editors, approvers, administrators
10. Performance optimization: sub-second search across 50K+ BOM items with indexing
11. Data migration from legacy system - import 100K+ historical BOM records
12. Dashboard analytics with cost trends, material usage, and bottleneck detection
13. Email notifications for approval requests, rejections, and BOM activations
14. Mobile-responsive UI for on-tablet BOM review on factory floor
15. Backup and disaster recovery - daily automated encrypted backups"""

r2 = requests.post(f"{BASE}/bom-system/intake/parse", headers=h, json={
    "content": content, "source_type": "text", "source_name": "Production BOM Requirements",
})
d = r2.json()
print(f"Session: {d['session_id'][:8]}...")
print(f"Functions: {d['function_count']}")
print(f"Total effort: {d['total_effort_person_days']} person-days")
print(f"Risk: {d['risk_forecast']['level'].upper()} (score: {d['risk_forecast']['overall_score']})")
print(f"Buffer: {d['risk_forecast']['schedule_buffer_days']} days")
print(f"Similar pairs: {len(d['similarities'])}")
print(f"Complexity: {d['complexity_distribution']}")
print(f"Risk items: {len(d['risk_forecast']['items'])}")
for item in d['risk_forecast']['items']:
    print(f"  - {item['category']}: {item['level']} ({item['severity']})")
print("\nFunction -> Module mapping:")
for f in d['functions'][:5]:
    print(f"  {f['code']} [{f['complexity']['level']}] {f['effort']['person_days']}d -> {f['target_module']} | {f['title'][:60]}")
print("  ...")
