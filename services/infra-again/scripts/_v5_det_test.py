"""V5 Acceptance: Full deterministic event stream test."""
from infra_again.flow import FlowSimulator, create_demo_flow

flow = create_demo_flow()
e1 = FlowSimulator(flow, 'HAPPY_PATH', seed=42).simulate()
e2 = FlowSimulator(flow, 'HAPPY_PATH', seed=42).simulate()
d1 = [ev.to_dict() for ev in e1]
d2 = [ev.to_dict() for ev in e2]
assert d1 == d2, 'MISMATCH: same seed gave different events'
for ev in e1:
    assert 'evt-' in ev.event_id and '-42-' in ev.event_id, f'Bad event_id: {ev.event_id}'
print(f'OK: {len(e1)} events, fully deterministic, 0 ignored fields')
