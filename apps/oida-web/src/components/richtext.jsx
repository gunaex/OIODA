// Minimal renderer for Document Again's rich section blocks (Tiptap JSON or
// plain {kind, text} blocks). Read-only: it renders a clean human-readable
// document without the editor.
import React from "react";

function tiptapText(node) {
  if (node == null) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(tiptapText).join("");
  if (typeof node.text === "string" && node.text !== "") return node.text;
  if (node.content) return tiptapText(node.content);
  return "";
}

function tiptapNode(node, key = 0) {
  if (node == null) return null;
  if (typeof node === "string") return <React.Fragment key={key}>{node}</React.Fragment>;
  if (Array.isArray(node)) return <React.Fragment key={key}>{node.map((n, i) => tiptapNode(n, i))}</React.Fragment>;

  const type = node.type || node.kind || "paragraph";
  const text = tiptapText(node);

  switch (type) {
    case "heading":
    case "h1":
      return <h1 key={key} className="mb-2 mt-5 text-xl font-bold">{text}</h1>;
    case "h2":
      return <h2 key={key} className="mb-2 mt-4 text-lg font-semibold">{text}</h2>;
    case "h3":
      return <h3 key={key} className="mb-1 mt-3 text-base font-semibold">{text}</h3>;
    case "bulletList":
    case "bulleted_list":
    case "bullet_list":
      return (
        <ul key={key} className="mb-2 list-disc space-y-1 pl-5">
          {(node.content || []).map((item, i) => (
            <li key={i}>{tiptapText(item)}</li>
          ))}
        </ul>
      );
    case "orderedList":
    case "ordered_list":
      return (
        <ol key={key} className="mb-2 list-decimal space-y-1 pl-5">
          {(node.content || []).map((item, i) => (
            <li key={i}>{tiptapText(item)}</li>
          ))}
        </ol>
      );
    case "table":
      return renderTable(node, key);
    case "blockquote":
      return <blockquote key={key} className="mb-2 border-l-4 border-gray-200 pl-3 italic text-gray-600">{text}</blockquote>;
    case "paragraph":
    default:
      if (!text.trim()) return <div key={key} className="h-3" />;
      return <p key={key} className="mb-2 leading-relaxed text-gray-700">{text}</p>;
  }
}

function renderTable(node, key) {
  const rows = (node.content || []).filter((r) => r.type === "tableRow" || r.type === "table_row");
  if (!rows.length) return <p key={key} className="mb-2 text-gray-500">(table)</p>;
  return (
    <table key={key} className="mb-3 w-full border-collapse border border-gray-200 text-sm">
      <tbody>
        {rows.map((row, ri) => {
          const cells = (row.content || []).filter((c) =>
            ["tableCell", "tableHeader", "table_cell", "table_header"].includes(c.type)
          );
          return (
            <tr key={ri} className={ri === 0 ? "bg-gray-50 font-semibold" : ""}>
              {cells.map((cell, ci) => (
                <td key={ci} className="border border-gray-200 px-2 py-1">{tiptapText(cell)}</td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function RichText({ blocks }) {
  if (!blocks || !blocks.length) return <p className="text-gray-500">Empty document.</p>;
  return (
    <div className="text-sm">
      {blocks.map((block, i) => {
        if (typeof block === "string") return <p key={i} className="mb-2">{block}</p>;
        if (block.kind === "heading") {
          return <h3 key={i} className="mb-2 mt-4 text-base font-semibold text-gray-900">{block.text || block.heading}</h3>;
        }
        // blocks may carry Tiptap JSON directly (block.doc / block.content)
        const doc = block.doc || block.content || block;
        return <div key={i}>{tiptapNode(doc, i)}</div>;
      })}
    </div>
  );
}
