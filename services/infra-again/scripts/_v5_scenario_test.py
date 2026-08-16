"""V5 Acceptance: Semantic scenario assertions."""
from infra_again.flow import FlowSimulator, create_demo_flow, reduce_state, FlowNodeState, FlowEdgeState

flow = create_demo_flow()


def test_scenario(sc, checks):
    sim = FlowSimulator(flow, sc, seed=42)
    events = sim.simulate()
    state = reduce_state(flow, events, bottlenecks=sim.get_bottlenecks())
    for check_name, fn in checks:
        ok, msg = fn(state, events, sim)
        if not ok:
            return False, f'{sc}: {check_name} FAILED: {msg}'
    return True, f'{sc}: {len(events)} events OK'


def chk_blocked(node_id):
    return lambda s, e, sim: (
        s.node_states.get(node_id) == FlowNodeState.BLOCKED,
        f'{node_id} not BLOCKED')

def chk_not_reached(*node_ids):
    return lambda s, e, sim: (
        all(s.node_states.get(n) == FlowNodeState.NOT_REACHED for n in node_ids),
        f'Expected NOT_REACHED for {node_ids}')

def chk_degraded(node_id):
    return lambda s, e, sim: (
        s.node_states.get(node_id) == FlowNodeState.DEGRADED,
        f'{node_id} not DEGRADED')

def chk_completed(node_id):
    return lambda s, e, sim: (
        s.node_states.get(node_id) in (FlowNodeState.PASS, FlowNodeState.COMPLETED),
        f'{node_id} not PASS/COMPLETED')

def chk_bottleneck(node_id):
    return lambda s, e, sim: (
        any(b.node_id == node_id and (b.score or 0) > 0 for b in s.bottlenecks),
        f'No bottleneck for {node_id}')

def chk_no_blocked():
    return lambda s, e, sim: (
        not any(v == FlowNodeState.BLOCKED for v in s.node_states.values()),
        'Unexpected BLOCKED')

def chk_waiting():
    return lambda s, e, sim: (
        any(ev.event_type.value == 'APPROVAL_REQUESTED' for ev in e),
        'No WAITING/APPROVAL_REQUESTED in events')


results = []

results.append(test_scenario('HAPPY_PATH', [
    ('no-blocked', chk_no_blocked()),
    ('user-completed', chk_completed('user')),
]))

results.append(test_scenario('AUTH_FAILURE', [
    ('credential-blocked', chk_blocked('credential-gate')),
    ('downstream-not-reached', chk_not_reached(
        'waf', 'firewall', 'api-gateway', 'application-service', 'postgresql', 'approval-gate')),
]))

results.append(test_scenario('FIREWALL_BLOCK', [
    ('firewall-blocked', chk_blocked('firewall')),
    ('api-not-reached', chk_not_reached(
        'api-gateway', 'application-service', 'postgresql', 'approval-gate')),
]))

results.append(test_scenario('DATABASE_SLOW', [
    ('postgresql-degraded', chk_degraded('postgresql')),
    ('bottleneck-exists', chk_bottleneck('postgresql')),
    ('no-blocked', chk_no_blocked()),
]))

results.append(test_scenario('API_TIMEOUT', [
    ('api-failed', lambda s, e, sim: (
        s.node_states.get('api-gateway') == FlowNodeState.FAILED,
        'api-gateway not FAILED')),
    ('downstream-not-reached', chk_not_reached(
        'application-service', 'postgresql', 'approval-gate')),
]))

results.append(test_scenario('APPROVAL_WAIT', [
    ('approval-requested', lambda s, e, sim: (
        any(ev.event_type.value == 'APPROVAL_REQUESTED' for ev in e),
        'No APPROVAL_REQUESTED event')),
    ('approval-granted', lambda s, e, sim: (
        any(ev.event_type.value == 'APPROVAL_GRANTED' for ev in e),
        'No APPROVAL_GRANTED event')),
]))

results.append(test_scenario('RETRY_RECOVERY', [
    ('retry-started', lambda s, e, sim: (
        any(ev.event_type.value == 'RETRY_START' for ev in e),
        'No RETRY_START event')),
    ('node-failed-then-passed', lambda s, e, sim: (
        any(ev.event_type.value == 'NODE_FAIL' for ev in e)
        and any(ev.event_type.value == 'NODE_PASS' and ev.node_id == 'application-service' for ev in e),
        'No fail-then-pass pattern for application-service')),
]))

for ok, msg in results:
    if not ok:
        print(msg)
        raise SystemExit(1)
    print(msg)

print('ALL 7 SCENARIOS: SEMANTIC ASSERTIONS PASSED')
