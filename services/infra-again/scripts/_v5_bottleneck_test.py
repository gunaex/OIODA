"""V5 Acceptance: Bottleneck evidence."""
from infra_again.flow import FlowSimulator, create_demo_flow

flow = create_demo_flow()
sim = FlowSimulator(flow, 'DATABASE_SLOW', seed=42)
sim.simulate()
bots = sim.get_bottlenecks()

assert len(bots) == 1, f'Expected 1 bottleneck, got {len(bots)}'
b = bots[0]
assert b.node_id == 'postgresql', f'Expected postgresql, got {b.node_id}'
assert b.score == 82.0, f'Expected score 82, got {b.score}'
assert b.factors[0]['source'] == 'SIMULATED', f'Expected SIMULATED, got {b.factors[0]["source"]}'
assert 'database' in b.explanation.lower() or '72%' in b.explanation, f'Bad explanation: {b.explanation}'
print(f'OK: bottleneck={b.node_id} score={b.score} source=SIMULATED')
