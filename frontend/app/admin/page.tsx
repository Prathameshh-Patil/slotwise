"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { RequireUser } from "@/components/require-user";
import { Alert, Button, Card, Field } from "@/components/ui";
import { api, type EventSummary } from "@/lib/api";

export default function AdminPage() {
  return (
    <RequireUser adminOnly loginReturnTo="/admin">
      {() => <NewEventForm />}
    </RequireUser>
  );
}

function NewEventForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const value = (name: string) => String(form.get(name) ?? "");
    setBusy(true);
    setError(null);
    try {
      const event = await api<EventSummary>("/events", {
        method: "POST",
        json: {
          title: value("title"),
          description: value("description"),
          venue: value("venue"),
          // <input type="datetime-local"> has no time zone; this reads it as local time
          starts_at: new Date(value("starts_at")).toISOString(),
          rows: Number(value("rows")),
          seats_per_row: Number(value("seats_per_row")),
          price_cents: Math.round(Number(value("price")) * 100),
        },
      });
      router.push(`/events/${event.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card className="mx-auto max-w-lg p-6">
      <h1 className="text-xl font-semibold">New event</h1>
      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label="Title" name="title" required maxLength={200} />
        <Field label="Venue" name="venue" required maxLength={200} />
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Description</span>
          <textarea
            name="description"
            rows={3}
            className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </label>
        <Field label="Starts at" name="starts_at" type="datetime-local" required />
        <div className="grid grid-cols-3 gap-3">
          <Field label="Rows (A–Z)" name="rows" type="number" min={1} max={26} defaultValue={6} required />
          <Field label="Seats per row" name="seats_per_row" type="number" min={1} max={50} defaultValue={10} required />
          <Field label="Price (₹)" name="price" type="number" min={0} step="0.01" defaultValue={500} required />
        </div>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Creating…" : "Create event"}
        </Button>
      </form>
    </Card>
  );
}
