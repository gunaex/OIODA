
import { useState, useCallback } from 'react';
export interface Toast { id: number; msg: string; type: 'ok'|'err'|'info'; }
let _id=0;
export function useToast() {
  const [toasts,setToasts]=useState<Toast[]>([]);
  const add=useCallback((msg:string,type:'ok'|'err'|'info'='info')=>{
    const t={id:++_id,msg,type}; setToasts(p=>[...p.slice(-4),t]);
    setTimeout(()=>setToasts(p=>p.filter(x=>x.id!==t.id)),3500);
  },[]);
  return {toasts,add};
}
export function ToastContainer({toasts}:{toasts:Toast[]}) {
  const colors:Record<string,string>={ok:'var(--verified)',err:'var(--blocked)',info:'var(--info)'};
  return <div style={{position:'fixed',bottom:20,right:20,zIndex:100,display:'flex',flexDirection:'column',gap:6}}>
    {toasts.map(t=><div key={t.id} style={{background:'var(--bg-elevated)',border:'1px solid var(--border)',borderRadius:6,padding:'8px 16px',fontSize:12,color:colors[t.type]||'var(--text-primary)',maxWidth:400,wordBreak:'break-word',boxShadow:'0 4px 12px rgba(0,0,0,0.4)'}}>{t.msg}</div>)}
  </div>;
}
