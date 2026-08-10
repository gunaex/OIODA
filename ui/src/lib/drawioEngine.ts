
/* Draw.io Engine Adapter for INFRA-AGAIN Architecture Studio.
   B2.1: Canonical ↔ draw.io XML round-trip with semantic reconciliation.
   Handles: load, save, export, classification, multi-view diagram generation. */

// ── Types ──

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

export interface ArchitectureProposal {
  summary: string;
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  groups: any[];
  nativeServiceRecommendations: { nodeId: string; recommendation: string }[];
  dataFlow: string[];
  operationFlow: string[];
  securityFlow: string[];
  assumptions: string[];
  risks: string[];
  questions: string[];
}

export type ObjectClassification = 'KNOWN_NODE' | 'KNOWN_EDGE' | 'NEW_VISUAL_NODE'
  | 'NEW_VISUAL_EDGE' | 'REMOVED_NODE' | 'REMOVED_EDGE'
  | 'UNMAPPED_COMPONENT' | 'INVALID_COMPONENT';

export interface ClassifiedObject {
  id: string;
  classification: ObjectClassification;
  xmlCellId: string;
  reason: string;
  meta: ArchitectureNode | ArchitectureEdge | null;
}

// ── Node category → draw.io style ──

const CAT_STYLES: Record<string, { shape: string; fill: string; stroke: string; fontColor: string }> = {
  USER:       { shape: 'ellipse;whiteSpace=wrap;html=1;', fill: '#dae8fc', stroke: '#6c8ebf', fontColor: '#000000' },
  SECURITY:   { shape: 'hexagon;whiteSpace=wrap;html=1;', fill: '#f8cecc', stroke: '#b85450', fontColor: '#000000' },
  NETWORK:    { shape: 'rhombus;whiteSpace=wrap;html=1;', fill: '#e1d5e7', stroke: '#9673a6', fontColor: '#000000' },
  GATEWAY:    { shape: 'process;whiteSpace=wrap;html=1;', fill: '#d5e8d4', stroke: '#82b366', fontColor: '#000000' },
  APPLICATION:{ shape: 'rounded=1;whiteSpace=wrap;html=1;', fill: '#dae8fc', stroke: '#6c8ebf', fontColor: '#000000' },
  DATABASE:   { shape: 'cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;', fill: '#f5f5f5', stroke: '#666666', fontColor: '#000000' },
  STORAGE:    { shape: 'note;whiteSpace=wrap;html=1;', fill: '#fff2cc', stroke: '#d6b656', fontColor: '#000000' },
  QUEUE:      { shape: 'parallelogram;whiteSpace=wrap;html=1;', fill: '#ffe6cc', stroke: '#d79b00', fontColor: '#000000' },
  CACHE:      { shape: 'shape=cylinder3;whiteSpace=wrap;html=1;', fill: '#f8cecc', stroke: '#b85450', fontColor: '#000000' },
};

function nodeStyle(cat: string): string {
  const s = CAT_STYLES[cat] || CAT_STYLES.APPLICATION;
  return `${s.shape}fillColor=${s.fill};strokeColor=${s.stroke};fontColor=${s.fontColor};`;
}

function edgeStyle(edge: ArchitectureEdge): string {
  const stroke = edge.type === 'data' ? '#d79b00' : edge.type === 'auth' ? '#b85450' : '#6c8ebf';
  return `edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeColor=${stroke};strokeWidth=2;`;
}

// ── Encode/decode metadata in cell value ──
// Uses HTML comment to hide metadata from draw.io render while preserving it in XML

function encodeNodeValue(n: ArchitectureNode): string {
  return n.name + '<!-- ' + JSON.stringify({
    nodeId: n.nodeId, category: n.category, provider: n.provider,
    nativeService: n.nativeService, platform: n.platform,
    securityZone: n.securityZone, dataClassification: n.dataClassification,
    owner: n.owner, source: n.source, verificationState: n.verificationState,
  }) + ' -->';
}

function encodeEdgeValue(e: ArchitectureEdge): string {
  return (e.label || '') + '<!-- ' + JSON.stringify({
    edgeId: e.edgeId, type: e.type, protocol: e.protocol,
    direction: e.direction, dataType: e.dataType,
    securityClassification: e.securityClassification,
  }) + ' -->';
}

function decodeMeta(value: string): { label: string; meta: Record<string,string> | null } {
  const commentMatch = value.match(/<!--\s*(\{[\s\S]*?\})\s*-->/);
  if (commentMatch) {
    try {
      return { label: value.replace(/<!--[\s\S]*?-->/, '').trim(), meta: JSON.parse(commentMatch[1]) };
    } catch { /* fall through */ }
  }
  return { label: value, meta: null };
}

// ═══════════════════════════════════════════════════════════════════
// CANONICAL → DRAW.IO XML
// ═══════════════════════════════════════════════════════════════════

export function canonicalToDrawioXml(
  canonical: CanonicalDesign,
  viewName: string = 'architecture'
): string {
  const viewNodeIds = new Set(canonical.views[viewName as keyof typeof canonical.views] || canonical.nodes.map(n => n.nodeId));
  const nodes = canonical.nodes.filter(n => viewNodeIds.has(n.nodeId));
  const edges = canonical.edges.filter(e => viewNodeIds.has(e.sourceNodeId) && viewNodeIds.has(e.targetNodeId));

  const nodeIdToCell: Record<string, number> = {};
  let cellId = 2;
  const cells: string[] = [];

  // Layout: grid-based positioning
  const COLS = 3;
  const CELL_W = 150, CELL_H = 60, GAP_X = 200, GAP_Y = 100;
  const START_X = 40, START_Y = 40;

  nodes.forEach((n, i) => {
    const col = i % COLS;
    const row = Math.floor(i / COLS);
    const x = START_X + col * GAP_X;
    const y = START_Y + row * GAP_Y;
    const style = nodeStyle(n.category);
    const value = encodeNodeValue(n);
    nodeIdToCell[n.nodeId] = cellId;
    cells.push(`        <mxCell id="${cellId}" value="${xmlEscape(value)}" style="${xmlEscape(style)}" vertex="1" parent="1">
          <mxGeometry x="${x}" y="${y}" width="${CELL_W}" height="${CELL_H}" as="geometry"/>
        </mxCell>`);
    cellId++;
  });

  edges.forEach(e => {
    const srcCell = nodeIdToCell[e.sourceNodeId];
    const tgtCell = nodeIdToCell[e.targetNodeId];
    if (!srcCell || !tgtCell) return;
    const style = edgeStyle(e);
    const value = encodeEdgeValue(e);
    cells.push(`        <mxCell id="${cellId}" value="${xmlEscape(value)}" style="${xmlEscape(style)}" edge="1" parent="1" source="${srcCell}" target="${tgtCell}">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>`);
    cellId++;
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="infra-again" modified="${new Date().toISOString()}" agent="INFRA-AGAIN B2.1" version="10.0.0">
  <diagram id="${canonical.designId}-${viewName}" name="${viewName}">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="800" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
${cells.join('\n')}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>`;
}

// ═══════════════════════════════════════════════════════════════════
// DRAW.IO XML → CANONICAL RECONCILIATION
// ═══════════════════════════════════════════════════════════════════

export function drawioXmlToCanonical(
  xml: string,
  existing: CanonicalDesign
): { canonical: CanonicalDesign; classifications: ClassifiedObject[] } {
  const classifications: ClassifiedObject[] = [];
  const existingNodeIds = new Set(existing.nodes.map(n => n.nodeId));
  const existingEdgeIds = new Set(existing.edges.map(e => e.edgeId));

  const newNodes: ArchitectureNode[] = [];
  const newEdges: ArchitectureEdge[] = [];
  const foundNodeIds = new Set<string>();
  const foundEdgeIds = new Set<string>();

  // Parse XML using regex (safe for draw.io's predictable format)
  const cellRegex = /<mxCell\s+[^>]*id="([^"]*)"[^>]*>/g;
  const attrRegex = /(\w+)="([^"]*)"/g;

  let cellMatch: RegExpExecArray | null;
  while ((cellMatch = cellRegex.exec(xml)) !== null) {
    const cellId = cellMatch[1];
    if (cellId === '0' || cellId === '1') continue;

    const tag = cellMatch[0];
    const attrs: Record<string,string> = {};
    let am: RegExpExecArray | null;
    const attrRe = /(\w+)="([^"]*)"/g;
    while ((am = attrRe.exec(tag)) !== null) {
      attrs[am[1]] = am[2];
    }

    const value = attrs.value || '';
    const { label, meta } = decodeMeta(value);

    if (attrs.vertex === '1') {
      // Vertex = node
      if (meta?.nodeId && existingNodeIds.has(meta.nodeId)) {
        // KNOWN_NODE — update position/metadata
        const existingNode = existing.nodes.find(n => n.nodeId === meta.nodeId)!;
        const updated: ArchitectureNode = {
          ...existingNode,
          name: label || existingNode.name,
          category: meta.category || existingNode.category,
          provider: meta.provider || existingNode.provider,
          nativeService: meta.nativeService || existingNode.nativeService,
          platform: meta.platform || existingNode.platform,
          securityZone: meta.securityZone || existingNode.securityZone,
          dataClassification: meta.dataClassification || existingNode.dataClassification,
          owner: meta.owner || existingNode.owner,
          verificationState: meta.verificationState || existingNode.verificationState,
        };
        newNodes.push(updated);
        foundNodeIds.add(meta.nodeId);
        classifications.push({ id: meta.nodeId, classification: 'KNOWN_NODE', xmlCellId: cellId, reason: '', meta: updated });
      } else if (meta?.nodeId) {
        // NEW_VISUAL_NODE with known ID but not in existing set
        const nn: ArchitectureNode = {
          nodeId: meta.nodeId, name: label,
          category: meta.category || 'APPLICATION',
          provider: meta.provider || existing.provider,
          nativeService: meta.nativeService || '',
          platform: meta.platform || existing.platform,
          properties: {},
          securityZone: meta.securityZone || 'private',
          dataClassification: meta.dataClassification || 'internal',
          owner: meta.owner || '',
          source: meta.source || 'drawio',
          verificationState: meta.verificationState || 'UNVERIFIED',
        };
        newNodes.push(nn);
        foundNodeIds.add(meta.nodeId);
        classifications.push({ id: meta.nodeId, classification: 'NEW_VISUAL_NODE', xmlCellId: cellId, reason: 'Not in existing canonical', meta: nn });
      } else {
        // UNMAPPED_COMPONENT — no INFRA-AGAIN metadata
        classifications.push({ id: `unmapped-${cellId}`, classification: 'UNMAPPED_COMPONENT', xmlCellId: cellId, reason: 'No INFRA-AGAIN metadata', meta: null });
      }
    } else if (attrs.edge === '1') {
      // Edge
      if (meta?.edgeId && existingEdgeIds.has(meta.edgeId)) {
        const existingEdge = existing.edges.find(e => e.edgeId === meta.edgeId)!;
        const updated: ArchitectureEdge = {
          ...existingEdge,
          label: label || existingEdge.label,
          type: meta.type || existingEdge.type,
          protocol: meta.protocol || existingEdge.protocol,
          direction: meta.direction || existingEdge.direction,
          dataType: meta.dataType || existingEdge.dataType,
          securityClassification: meta.securityClassification || existingEdge.securityClassification,
        };
        newEdges.push(updated);
        foundEdgeIds.add(meta.edgeId);
        classifications.push({ id: meta.edgeId, classification: 'KNOWN_EDGE', xmlCellId: cellId, reason: '', meta: updated });
      } else if (meta?.edgeId) {
        const ne: ArchitectureEdge = {
          edgeId: meta.edgeId,
          sourceNodeId: attrs.source ? findNodeIdByCell(attrs.source, classifications) : '',
          targetNodeId: attrs.target ? findNodeIdByCell(attrs.target, classifications) : '',
          type: meta.type || 'request',
          protocol: meta.protocol || 'TCP',
          direction: meta.direction || 'unidirectional',
          dataType: meta.dataType || '',
          securityClassification: meta.securityClassification || 'none',
          label: label,
        };
        newEdges.push(ne);
        foundEdgeIds.add(meta.edgeId);
        classifications.push({ id: meta.edgeId, classification: 'NEW_VISUAL_EDGE', xmlCellId: cellId, reason: 'New edge', meta: ne });
      } else {
        classifications.push({ id: `unmapped-${cellId}`, classification: 'UNMAPPED_COMPONENT', xmlCellId: cellId, reason: 'No INFRA-AGAIN metadata on edge', meta: null });
      }
    }
  }

  // Classify REMOVED nodes and edges
  for (const nid of existingNodeIds) {
    if (!foundNodeIds.has(nid)) {
      classifications.push({ id: nid, classification: 'REMOVED_NODE', xmlCellId: '', reason: 'Present in canonical but not in draw.io XML', meta: null });
    }
  }
  for (const eid of existingEdgeIds) {
    if (!foundEdgeIds.has(eid)) {
      classifications.push({ id: eid, classification: 'REMOVED_EDGE', xmlCellId: '', reason: 'Present in canonical but not in draw.io XML', meta: null });
    }
  }

  const canonical: CanonicalDesign = {
    ...existing,
    nodes: newNodes,
    edges: newEdges,
    diagramDocument: xml,
    diagramEngine: 'drawio',
    updatedAt: new Date().toISOString(),
  };

  return { canonical, classifications };
}

function findNodeIdByCell(cellId: string, classifications: ClassifiedObject[]): string {
  const found = classifications.find(c => c.xmlCellId === cellId && c.meta && 'category' in c.meta);
  return found?.id || '';
}

// ═══════════════════════════════════════════════════════════════════
// MULTI-VIEW XML GENERATION
// ═══════════════════════════════════════════════════════════════════

export function generateMultiViewXmls(
  canonical: CanonicalDesign
): Record<string, string> {
  return {
    architecture: canonicalToDrawioXml(canonical, 'architecture'),
    dataFlow: canonicalToDrawioXml(canonical, 'dataFlow'),
    operationFlow: canonicalToDrawioXml(canonical, 'operationFlow'),
    securityFlow: canonicalToDrawioXml(canonical, 'securityFlow'),
  };
}

// ═══════════════════════════════════════════════════════════════════
// ARCHITECTURE PROPOSAL VALIDATION
// ═══════════════════════════════════════════════════════════════════

export function validateArchitectureProposal(proposal: any): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!proposal || typeof proposal !== 'object') { errors.push('Proposal must be an object'); return { valid: false, errors }; }
  if (!proposal.summary) errors.push('Missing: summary');
  if (!Array.isArray(proposal.nodes)) errors.push('Missing: nodes[]');
  if (!Array.isArray(proposal.edges)) errors.push('Missing: edges[]');
  if (!Array.isArray(proposal.groups)) errors.push('Missing: groups[]');
  if (!Array.isArray(proposal.assumptions)) errors.push('Missing: assumptions[]');
  if (!Array.isArray(proposal.risks)) errors.push('Missing: risks[]');
  if (!Array.isArray(proposal.questions)) errors.push('Missing: questions[]');

  // Validate each node has required fields
  if (Array.isArray(proposal.nodes)) {
    proposal.nodes.forEach((n: any, i: number) => {
      if (!n.nodeId) errors.push(`nodes[${i}]: missing nodeId`);
      if (!n.name) errors.push(`nodes[${i}]: missing name`);
      if (!n.category) errors.push(`nodes[${i}]: missing category`);
    });
  }
  if (Array.isArray(proposal.edges)) {
    proposal.edges.forEach((e: any, i: number) => {
      if (!e.edgeId) errors.push(`edges[${i}]: missing edgeId`);
      if (!e.sourceNodeId) errors.push(`edges[${i}]: missing sourceNodeId`);
      if (!e.targetNodeId) errors.push(`edges[${i}]: missing targetNodeId`);
    });
  }

  return { valid: errors.length === 0, errors };
}

// ═══════════════════════════════════════════════════════════════════
// UTILITIES (unchanged from original)
// ═══════════════════════════════════════════════════════════════════

function xmlEscape(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');
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
