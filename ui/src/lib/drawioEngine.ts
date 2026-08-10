
/* Draw.io Engine Adapter for INFRA-AGAIN Architecture Studio.
   Handles: load, save, export, semantic reconciliation, multi-view (pages). */

export interface ArchitectureNode {
  nodeId: string; name: string; category: string;
  provider: string; nativeService: string; platform: string;
  properties: Record<string,string>;
  securityZone: string; dataClassification: string; owner: string;
  source: string; verificationState: string;
}

export interface ArchitectureEdge {
  edgeId: string; sourceNodeId: string; targetNodeId: string;
  type: string; protocol: string; direction: string;
  dataType: string; securityClassification: string; label: string;
}

export interface CanonicalDesign {
  designId: string; workspaceId: string;
  title: string; description: string;
  provider: string; platform: string; fidelity: string;
  version: string; status: string;
  nodes: ArchitectureNode[]; edges: ArchitectureEdge[]; groups: any[];
  views: { architecture: string[]; dataFlow: string[]; operationFlow: string[]; securityFlow: string[] };
  aiRationale: string; assumptions: string[]; risks: string[];
  diagramEngine: string; diagramDocument: string;
  createdBy: string; updatedBy: string; createdAt: string; updatedAt: string;
}

/** Mermaid syntax for a simple architecture */
export function generateMermaid(nodes: ArchitectureNode[], edges: ArchitectureEdge[], view: string): string {
  const lines: string[] = ['graph TD'];
  const nodeIds = new Set<string>();
  for (const n of nodes) {
    const label = n.name.replace(/[^a-zA-Z0-9 ]/g,'');
    const id = n.nodeId.replace(/-/g,'');
    lines.push(`  ${id}[${label}]`);
    nodeIds.add(id);
  }
  for (const e of edges) {
    const src = e.sourceNodeId.replace(/-/g,'');
    const tgt = e.targetNodeId.replace(/-/g,'');
    if (nodeIds.has(src) && nodeIds.has(tgt)) {
      lines.push(`  ${src} -->|${e.label||''}| ${tgt}`);
    }
  }
  return lines.join('\n');
}

/** Create a canonical example design */
export function createExampleDesign(provider: string = 'AWS'): CanonicalDesign {
  const nodes: ArchitectureNode[] = [
    { nodeId:'NODE-USER-001', name:'Client / User', category:'USER', provider, nativeService:'', platform:'WEB', properties:{}, securityZone:'public', dataClassification:'none', owner:'', source:'POC', verificationState:'UNVERIFIED' },
    { nodeId:'NODE-LB-001', name:'Application Load Balancer', category:'NETWORK', provider, nativeService:provider==='AWS'?'alb':'lb', platform:'NATIVE_VM', properties:{}, securityZone:'dmz', dataClassification:'none', owner:'', source:'POC', verificationState:'UNVERIFIED' },
    { nodeId:'NODE-APP-001', name:'Application Service', category:'APPLICATION', provider, nativeService:provider==='AWS'?'ecs':'app', platform:'KUBERNETES', properties:{runtime:'container'}, securityZone:'private', dataClassification:'internal', owner:'platform-team', source:'POC', verificationState:'UNVERIFIED' },
    { nodeId:'NODE-DB-001', name:'Database', category:'DATABASE', provider, nativeService:provider==='AWS'?'rds':'db', platform:'NATIVE_VM', properties:{engine:'postgresql'}, securityZone:'private', dataClassification:'pii', owner:'data-team', source:'POC', verificationState:'UNVERIFIED' },
    { nodeId:'NODE-STORE-001', name:'Object Storage', category:'STORAGE', provider, nativeService:provider==='AWS'?'s3':'storage', platform:'NATIVE_VM', properties:{}, securityZone:'private', dataClassification:'internal', owner:'', source:'POC', verificationState:'UNVERIFIED' },
  ];
  const edges: ArchitectureEdge[] = [
    { edgeId:'EDGE-001', sourceNodeId:'NODE-USER-001', targetNodeId:'NODE-LB-001', type:'request', protocol:'HTTPS', direction:'unidirectional', dataType:'', securityClassification:'none', label:'HTTPS' },
    { edgeId:'EDGE-002', sourceNodeId:'NODE-LB-001', targetNodeId:'NODE-APP-001', type:'request', protocol:'HTTP', direction:'unidirectional', dataType:'', securityClassification:'none', label:'HTTP' },
    { edgeId:'EDGE-003', sourceNodeId:'NODE-APP-001', targetNodeId:'NODE-DB-001', type:'data', protocol:'TCP', direction:'bidirectional', dataType:'SQL', securityClassification:'pii', label:'SQL' },
    { edgeId:'EDGE-004', sourceNodeId:'NODE-APP-001', targetNodeId:'NODE-STORE-001', type:'data', protocol:'HTTPS', direction:'bidirectional', dataType:'blob', securityClassification:'internal', label:'S3 API' },
  ];
  return {
    designId: '', workspaceId: '', title: `Example ${provider} Architecture`, description: 'POC architecture',
    provider, platform: 'KUBERNETES', fidelity: 'LOCAL_RUNTIME', version: '1', status: 'DRAFT',
    nodes, edges, groups: [],
    views: {
      architecture: nodes.map(n=>n.nodeId),
      dataFlow: ['NODE-APP-001','NODE-DB-001','NODE-STORE-001'],
      operationFlow: ['NODE-USER-001','NODE-LB-001','NODE-APP-001'],
      securityFlow: ['NODE-LB-001','NODE-APP-001'],
    },
    aiRationale: '', assumptions: [], risks: [],
    diagramEngine: 'drawio', diagramDocument: '',
    createdBy: 'poc', updatedBy: 'poc', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
}
