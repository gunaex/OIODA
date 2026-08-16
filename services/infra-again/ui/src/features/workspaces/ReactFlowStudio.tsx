import { useState, useCallback } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap, addEdge,
  Connection, Node, Edge, MarkerType, BackgroundVariant,
  applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { CanonicalDesign } from '../../lib/drawioEngine';

interface Props { canonical: CanonicalDesign | null; onSave: (c: CanonicalDesign) => void; }

const CAT_COLORS: Record<string,string> = {
  USER:'var(--info)', SECURITY:'var(--danger)', NETWORK:'#a371f7',
  GATEWAY:'var(--accent)', APPLICATION:'var(--accent)', DATABASE:'#e3b341',
  STORAGE:'var(--info)', QUEUE:'var(--warning)', CACHE:'var(--warning)',
};

function ServiceNode({ data, selected }: any) {
  return (
    <div style={{padding:'6px 12px',borderRadius:6,fontSize:11,fontWeight:500,
      background:selected?'var(--bg-active)':'var(--bg-surface)',
      border:`1.5px solid ${selected ? (CAT_COLORS[data.category]||'var(--border-default)') : 'var(--border-default)'}`,
      color:'var(--text-primary)',cursor:'pointer',minWidth:80,textAlign:'center'}}>
      <div style={{fontSize:9,color:CAT_COLORS[data.category]||'var(--text-muted)',textTransform:'uppercase',letterSpacing:'0.05em',marginBottom:2}}>{data.category}</div>
      {data.label}
    </div>
  );
}
const nodeTypes = { default: ServiceNode };

export default function ReactFlowStudio({ canonical, onSave }: Props) {
  const initNodes: Node[] = (canonical?.nodes||[]).map(n=>({id:n.nodeId,type:'default',position:{x:300+Math.random()*100,y:100+Math.random()*300},data:{label:n.name,category:n.category,provider:n.provider}}));
  const initEdges: Edge[] = (canonical?.edges||[]).map(e=>({id:e.edgeId,source:e.sourceNodeId,target:e.targetNodeId,label:e.label||'',animated:true,markerEnd:{type:MarkerType.ArrowClosed,color:'var(--text-muted)'},style:{stroke:'var(--border-default)',strokeWidth:1.5}}));
  const [nodes,setNodes]=useState<Node[]>(initNodes);
  const [edges,setEdges]=useState<Edge[]>(initEdges);
  const onNodesChange=useCallback((chs:NodeChange[])=>setNodes(nds=>applyNodeChanges(chs,nds)),[]);
  const onEdgesChange=useCallback((chs:EdgeChange[])=>setEdges(eds=>applyEdgeChanges(chs,eds)),[]);
  const onConnect=useCallback((p:Connection)=>setEdges(eds=>addEdge({...p,markerEnd:{type:MarkerType.ArrowClosed,color:'var(--text-muted)'},style:{stroke:'var(--border-default)',strokeWidth:1.5}},eds)),[]);

  return (
    <div style={{height:'100%',background:'var(--bg-root)'}}>
      <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} nodeTypes={nodeTypes} fitView>
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border-subtle)"/>
        <Controls style={{background:'var(--bg-surface)',border:'1px solid var(--border-default)',borderRadius:6}}/>
        <MiniMap style={{background:'var(--bg-surface)',border:'1px solid var(--border-default)',borderRadius:6}} nodeColor={n=>CAT_COLORS[(n.data as any)?.category]||'var(--text-muted)'}/>
      </ReactFlow>
    </div>
  );
}
