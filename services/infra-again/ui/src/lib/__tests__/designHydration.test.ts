// M4-D.4 — design hydration tests.
//
// Regression coverage for DESIGN_FLOW_RELOAD_DEFECT: GET /api/v1/designs/{id}
// returns {design: {..., flow: {provider, nodes, edges, ...}}}, and the
// canonical architecture / provider live at design.flow, not the top level.
// resolveDesignHydration is the pure function ArchitectureWorkspace now
// calls instead of inlining this decision — tested here independent of
// React/fetch so the "just show the generic template" regression can't
// silently come back.
import { describe, it, expect } from 'vitest';
import { resolveDesignHydration } from '../drawioEngine';

function node(nodeId: string, category: string, provider: string) {
  return {
    nodeId, name: nodeId, category, provider, nativeService: '', platform: 'NATIVE_VM',
    properties: {}, securityZone: 'private', dataClassification: 'internal',
    owner: '', source: 'AI_GENERATED', verificationState: 'UNVERIFIED',
  };
}

function edge(edgeId: string, from: string, to: string) {
  return {
    edgeId, sourceNodeId: from, targetNodeId: to, type: 'request', protocol: 'HTTPS',
    direction: 'unidirectional', dataType: '', securityClassification: 'none', label: 'HTTPS',
  };
}

describe('resolveDesignHydration', () => {
  it('A: AWS_DESIGN_HYDRATION — persisted AWS architecture loads correctly', () => {
    const apiResponse = {
      design: {
        designId: 'DESIGN-AAA111', status: 'DRAFT', metadata: { name: 'Patient Portal' },
        flow: {
          provider: 'AWS', platform: 'KUBERNETES', title: 'Patient Portal',
          nodes: [node('N1', 'APPLICATION', 'AWS'), node('N2', 'DATABASE', 'AWS'), node('N3', 'NETWORK', 'AWS')],
          edges: [edge('E1', 'N1', 'N2'), edge('E2', 'N3', 'N1')],
          groups: [], views: {}, diagramEngine: 'drawio',
        },
      },
    };
    const result = resolveDesignHydration('DESIGN-AAA111', apiResponse);
    expect(result.ok).toBe(true);
    expect(result.canonical!.provider).toBe('AWS');
    expect(result.canonical!.nodes).toHaveLength(3);
    expect(result.canonical!.edges).toHaveLength(2);
  });

  it('B: ONPREM_DESIGN_HYDRATION — persisted ON_PREM architecture loads correctly', () => {
    const apiResponse = {
      design: {
        designId: 'DESIGN-BBB222', status: 'DRAFT', metadata: {},
        flow: { provider: 'ON_PREM', nodes: [node('N1', 'APPLICATION', 'ON_PREM')], edges: [] },
      },
    };
    const result = resolveDesignHydration('DESIGN-BBB222', apiResponse);
    expect(result.ok).toBe(true);
    // ON_PREM here must be the persisted flow's real provider, not a fallback
    // default — proven by giving it a single-node fixture that has nothing
    // else pointing at ON_PREM.
    expect(result.canonical!.provider).toBe('ON_PREM');
    expect(result.canonical!.nodes).toHaveLength(1);
  });

  it('C: MALFORMED_DESIGN_NO_FAKE_FALLBACK — persisted flow with no valid nodes array is not replaced by a fake architecture', () => {
    const apiResponse = {
      design: { designId: 'DESIGN-CCC333', status: 'DRAFT', metadata: {}, flow: { provider: 'AWS', nodes: 'not-an-array' } },
    };
    const result = resolveDesignHydration('DESIGN-CCC333', apiResponse);
    expect(result.ok).toBe(false);
    expect(result.canonical).toBeUndefined();
    expect(result.error).toContain('MALFORMED_PERSISTED_DESIGN');
  });

  it('D: UNRESOLVED_PROVIDER_BLOCK — persisted flow with valid nodes but no provider blocks instead of defaulting to ON_PREM', () => {
    const apiResponse = {
      design: { designId: 'DESIGN-DDD444', status: 'DRAFT', metadata: {}, flow: { nodes: [node('N1', 'APPLICATION', 'AWS')], edges: [] } },
    };
    const result = resolveDesignHydration('DESIGN-DDD444', apiResponse);
    expect(result.ok).toBe(false);
    expect(result.canonical).toBeUndefined();
    expect(result.error).toContain('DESIGN_PROVIDER_UNRESOLVED');
  });

  it('E: DESIGN_ID_RELOAD_STABLE — hydration never mints a different design id', () => {
    const apiResponse = {
      design: { designId: 'DESIGN-EEE555', status: 'DRAFT', metadata: {}, flow: { provider: 'AWS', nodes: [node('N1', 'APPLICATION', 'AWS')], edges: [] } },
    };
    const result = resolveDesignHydration('DESIGN-EEE555', apiResponse);
    expect(result.canonical!.designId).toBe('DESIGN-EEE555');

    // A response for a DIFFERENT design must never be silently accepted.
    const mismatched = resolveDesignHydration('DESIGN-EEE555', {
      design: { designId: 'DESIGN-OTHER', status: 'DRAFT', metadata: {}, flow: { provider: 'AWS', nodes: [] } },
    });
    expect(mismatched.ok).toBe(false);
    expect(mismatched.error).toContain('DESIGN_ID_MISMATCH');
  });

  it('F: NODE_COUNT_PRESERVED — hydrated node/edge count equals persisted count (15/17 fixture)', () => {
    const nodes = Array.from({ length: 15 }, (_, i) => node(`N${i}`, 'APPLICATION', 'AWS'));
    const edges = Array.from({ length: 17 }, (_, i) => edge(`E${i}`, `N${i % 15}`, `N${(i + 1) % 15}`));
    const apiResponse = { design: { designId: 'DESIGN-FFF666', status: 'DRAFT', metadata: {}, flow: { provider: 'AWS', nodes, edges } } };
    const result = resolveDesignHydration('DESIGN-FFF666', apiResponse);
    expect(result.canonical!.nodes).toHaveLength(15);
    expect(result.canonical!.edges).toHaveLength(17);
  });

  it('G+H: INSPECTOR_PROVIDER_MATCH / REFINE_PROVIDER_MATCH — resolved provider is the single source both would read', () => {
    const apiResponse = {
      design: { designId: 'DESIGN-GGG777', status: 'DRAFT', metadata: {}, flow: { provider: 'AWS', nodes: [node('N1', 'APPLICATION', 'AWS')], edges: [] } },
    };
    const result = resolveDesignHydration('DESIGN-GGG777', apiResponse);
    const inspectorProvider = result.canonical!.provider; // what ArchitectureWorkspace's toolbar badge reads
    const refineRequestProvider = result.canonical!.provider; // what runRefine() sends as body.provider
    expect(inspectorProvider).toBe('AWS');
    expect(refineRequestProvider).toBe('AWS');
    expect(inspectorProvider).toBe(refineRequestProvider);
  });

  it('genuinely fresh design (no flow key at all) still gets a starter template under the same id', () => {
    const apiResponse = { design: { designId: 'DESIGN-FRESH1', status: 'DRAFT', metadata: { name: 'New' } } };
    const result = resolveDesignHydration('DESIGN-FRESH1', apiResponse);
    expect(result.ok).toBe(true);
    expect(result.isFreshDesign).toBe(true);
    expect(result.canonical!.designId).toBe('DESIGN-FRESH1');
    expect(result.canonical!.nodes.length).toBeGreaterThan(0);
  });
});
