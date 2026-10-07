"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, Card } from "@/components/ui";
import { api, formatDate, type EventSummary } from "@/lib/api";

export default function EventsPage() {
  const [events, setEvents] = useState<EventSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<EventSummary[]>("/events")
      .then(setEvents)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upcoming events</h1>
        <p className="mt-1 text-muted">Pick an event, choose your seat, and it&apos;s yours.</p>
      </div>

      {error && <Alert>{error}</Alert>}
      {events === null && !error && <p className="text-muted">Loading events…</p>}
      {events?.length === 0 && <Alert tone="info">No upcoming events yet.</Alert>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {events?.map((event) => {
          const soldOut = event.available_seats === 0;
          return (
            <Link key={event.id} href={`/events/${event.id}`} className="group">
              <Card className="flex h-full flex-col p-5 transition group-hover:border-accent">
                <p className="text-xs font-medium tracking-wide text-accent uppercase">
                  {formatDate(event.starts_at)}
                </p>
                <h2 className="mt-2 text-lg font-semibold">{event.title}</h2>
                <p className="text-sm text-muted">{event.venue}</p>
                <p className="mt-3 line-clamp-2 flex-1 text-sm">{event.description}</p>
                <p className={`mt-4 text-sm font-medium ${soldOut ? "text-danger" : ""}`}>
                  {soldOut
                    ? "Sold out"
                    : `${event.available_seats} of ${event.total_seats} seats left`}
                </p>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
