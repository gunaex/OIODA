import { Card, CardHeader, Empty } from "../components/ui";

export default function QaEvidence() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Evidence</h1>
        <p className="text-sm text-gray-500">Source: QA Again · evidence is attached per executed test.</p>
      </div>
      <Card>
        <CardHeader title="Evidence items" />
        <Empty title="No evidence yet">
          Evidence is captured when a test is executed. No tests have run for this baseline, so there is honestly nothing here.
        </Empty>
      </Card>
    </div>
  );
}
