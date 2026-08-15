import React, { useState } from "react";
import { api } from "../api/client.js";
import { Button, Card, Field, inputClass } from "../components/ui.jsx";

export function Projects({ onCreated }) {
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.post("/projects", { key, name, description });
      onCreated(project);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen items-center justify-center p-6">
      <Card title="Create the first project workspace" className="w-[420px]">
        <form onSubmit={submit} className="space-y-3">
          <Field label="Project key">
            <input className={inputClass} value={key} onChange={(e) => setKey(e.target.value)} placeholder="ORDERS" required />
          </Field>
          <Field label="Project name">
            <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="Order Approval System" required />
          </Field>
          <Field label="Description">
            <textarea className={`${inputClass} min-h-16`} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          {error && <p className="text-[12px] text-red-400">{error.message}</p>}
          <Button variant="primary" disabled={busy || !key || !name}>Create project</Button>
        </form>
      </Card>
    </div>
  );
}
