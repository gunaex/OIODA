import { useEffect, useState } from "react";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Badge, Loading, Empty, formatDateTime } from "../components/ui";
import RichText from "../components/richtext";

export default function ArtifactPage({ type }) {
  const { project } = useProjectCtx();
  const [artifacts, setArtifacts] = useState(null);
  const [revisions, setRevisions] = useState([]);
  const [selected, setSelected] = useState(null); // revision id
  const [doc, setDoc] = useState(null);

  useEffect(() => {
    if (!project) return;
    documentApi.listArtifacts(project.id).then(async (rows) => {
      const mine = (rows || []).filter((a) => a.type === type);
      setArtifacts(mine);
      // Artifacts come with their revisions (see /artifacts/{id}); if not,
      // fetch the full artifact for the latest revision.
      let revs = [];
      for (const a of mine) {
        const detail = await documentApi.getArtifact(a.id).catch(() => null);
        revs = revs.concat((detail?.revisions || []).map((r) => ({ ...r, artifactId: a.id })));
      }
      revs.sort((a, b) => (b.revision_number || 0) - (a.revision_number || 0));
      setRevisions(revs);
      if (revs.length) setSelected(revs[0].id);
    }).catch(() => setArtifacts([]));
  }, [project?.id, type]);

  useEffect(() => {
    if (!selected) return;
    setDoc(null);
    documentApi.getRevisionDocument(selected).then(setDoc).catch(() => setDoc({ sections: [] }));
  }, [selected]);

  if (!project) return <Loading />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">{type === "UR" ? "UR — True Cloud Migration" : "DR — True Cloud Migration"}</h1>
        <p className="text-sm text-gray-500">Document authority: Document Again · Excel is the working document.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Revisions" subtitle="Historical truth is preserved." />
          <ul className="divide-y divide-gray-50">
            {revisions.map((r) => (
              <li key={r.id}>
                <button
                  onClick={() => setSelected(r.id)}
                  className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm ${
                    selected === r.id ? "bg-gray-50" : "hover:bg-gray-50"
                  }`}
                >
                  <span className="font-medium text-gray-700">v{r.revision_number}</span>
                  <StatusBadge status={r.status} />
                </button>
              </li>
            ))}
            {revisions.length === 0 && <li className="px-4 py-3 text-sm text-gray-500">No revisions</li>}
          </ul>
        </Card>

        <div className="lg:col-span-2">
          <Card>
            <CardHeader
              title={doc?.title || `${type} document`}
              subtitle={doc ? `${type} · v${doc.revision_number} · ${doc.status}` : undefined}
              right={
                doc && (
                  <div className="flex gap-2">
                    <a
                      href={documentApi.exportRevision(doc.revision_id, "xlsx")}
                      className="rounded-lg border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Excel
                    </a>
                  </div>
                )
              }
            />
            <div className="px-5 py-4">
              {!doc ? <Loading /> : <RichText blocks={doc.sections} />}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
