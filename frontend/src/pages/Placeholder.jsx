import React from "react";
import { Card } from "../components/ui.jsx";

export function Placeholder({ title, note }) {
  return (
    <Card title={title}>
      <p className="text-[13px] text-slate-400">{note || "Specialized engine ships post-P0. The domain layer and semantic IDs already reserve this ground."}</p>
      <div className="mt-6 rounded border border-dashed border-line p-10 text-center text-[12px] text-slate-600">
        engine placeholder — structured model is authoritative, the canvas is a view
      </div>
    </Card>
  );
}
