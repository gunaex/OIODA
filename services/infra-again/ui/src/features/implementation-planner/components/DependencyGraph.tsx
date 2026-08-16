import React from 'react';
import type { Dependency, WorkPackage } from '../model/implementationTypes';

interface Props {
  dependencies: Dependency[];
  workPackages: WorkPackage[];
  criticalPath: string[];
}

const TYPE_COLORS: Record<string, string> = {
  SECURITY: '#8b5cf6',
  APPLICATION: '#3b82f6',
  DATABASE: '#22c55e',
  STORAGE: '#f59e0b',
  INTEGRATION: '#06b6d4',
  TESTING: '#ec4899',
  DEPLOYMENT: '#ef4444',
  DOCUMENTATION: '#6b7280',
};

export default function DependencyGraph({ dependencies, workPackages, criticalPath }: Props) {
  const pkgMap = new Map(workPackages.map(w => [w.packageId, w]));
  const nodeSet = new Set<string>();
  dependencies.forEach(d => { nodeSet.add(d.fromPackage); nodeSet.add(d.toPackage); });

  const nodes = Array.from(nodeSet).map(id => ({
    id,
    label: (pkgMap.get(id)?.title || id).replace(' ', '\n'),
    type: pkgMap.get(id)?.packageType || 'APPLICATION',
    isCritical: criticalPath.includes(id),
  }));

  // Simple topological layout: arrange nodes in layers
  const layers = computeLayers(dependencies, nodes.map(n => n.id));
  const nodePos = new Map<string, { x: number; y: number }>();
  const layerHeight = 70;
  const nodeSpacing = 160;
  layers.forEach((layer, li) => {
    layer.forEach((nid, ni) => {
      // Critical path nodes come first
      nodePos.set(nid, { x: 50 + ni * nodeSpacing + 80, y: 30 + li * layerHeight + 25 });
    });
  });

  const canvasW = Math.max(600, (Math.max(...layers.map(l => l.length), 1)) * nodeSpacing + 160);
  const canvasH = Math.max(200, layers.length * layerHeight + 80);

  return (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>🔗 Dependency Graph</h3>
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, background: '#fafbfc', overflow: 'auto' }}>
        <svg width={canvasW} height={canvasH} style={{ display: 'block' }}>
          {/* Edges */}
          {dependencies.map(d => {
            const from = nodePos.get(d.fromPackage);
            const to = nodePos.get(d.toPackage);
            if (!from || !to) return null;
            const isCritical = criticalPath.includes(d.fromPackage) && criticalPath.includes(d.toPackage);
            const midX = (from.x + to.x) / 2;
            const midY = (from.y + to.y) / 2;
            return (
              <g key={d.depId}>
                <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                  stroke={isCritical ? '#ef4444' : '#d1d5db'}
                  strokeWidth={isCritical ? 2 : 1}
                  markerEnd={isCritical ? 'url(#arrowCritical)' : 'url(#arrow)'}
                />
                <text x={midX} y={midY - 4} fontSize={9} fill="#9ca3af" textAnchor="middle">
                  {d.description.slice(0, 20)}
                </text>
              </g>
            );
          })}

          {/* Arrow markers */}
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX={10} refY={5} markerWidth={6} markerHeight={6} orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 Z" fill="#d1d5db" />
            </marker>
            <marker id="arrowCritical" viewBox="0 0 10 10" refX={10} refY={5} markerWidth={6} markerHeight={6} orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 Z" fill="#ef4444" />
            </marker>
          </defs>

          {/* Nodes */}
          {nodes.map(n => {
            const pos = nodePos.get(n.id)!;
            const color = TYPE_COLORS[n.type] || '#6b7280';
            const labels = n.label.split('\n');
            return (
              <g key={n.id}>
                <rect x={pos.x - 60} y={pos.y - 18} width={120} height={36}
                  rx={8} fill={color + '15'} stroke={n.isCritical ? '#ef4444' : color}
                  strokeWidth={n.isCritical ? 2 : 1}
                />
                {labels.map((l, i) => (
                  <text key={i} x={pos.x} y={pos.y + (i - (labels.length - 1) / 2) * 13}
                    fontSize={10} fill="#111827" textAnchor="middle" fontWeight={600}>
                    {l}
                  </text>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>
        🔴 Red = critical path | {dependencies.length} dependencies
      </div>
    </div>
  );
}

/** Topological layer assignment (simplified). */
function computeLayers(deps: Dependency[], nodeIds: string[]): string[][] {
  const inDegree = new Map(nodeIds.map(id => [id, 0]));
  const adj = new Map(nodeIds.map(id => [id, [] as string[]]));
  deps.forEach(d => {
    adj.get(d.fromPackage)?.push(d.toPackage);
    inDegree.set(d.toPackage, (inDegree.get(d.toPackage) || 0) + 1);
  });

  const layers: string[][] = [];
  let queue = nodeIds.filter(id => (inDegree.get(id) || 0) === 0);
  while (queue.length > 0) {
    layers.push([...queue]);
    const next: string[] = [];
    queue.forEach(n => {
      (adj.get(n) || []).forEach(m => {
        inDegree.set(m, (inDegree.get(m) || 0) - 1);
        if (inDegree.get(m) === 0) next.push(m);
      });
    });
    queue = next;
  }
  return layers;
}
