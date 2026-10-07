"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { RequireUser } from "@/components/require-user";
import { Alert, Button, Card } from "@/components/ui";
import { api, formatDate, formatPrice, type Booking, type BookingStatus } from "@/lib/api";

const BADGE: Record<BookingStatus, string> = {
  confirmed: "bg-seat-free/15 text-seat-free",
  held: "bg-seat-held/15 text-seat-held",
  cancelled: "bg-border text-muted",
  expired: "bg-border text-muted",
};

export default function BookingsPage() {
  return <RequireUser loginReturnTo="/bookings">{() => <BookingList />}</RequireUser>;
}

function BookingList() {
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Booking[]>("/bookings/me")
      .then(setBookings)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function act(booking: Booking, action: "confirm" | "cancel") {
    setError(null);
    try {
      await api(`/bookings/${booking.id}/${action}`, { method: "POST" });
    } catch (e) {
      setError((e as Error).message);
    }
    load();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">My bookings</h1>
      {error && <Alert>{error}</Alert>}
      {bookings === null && !error && <p className="text-muted">Loading…</p>}
      {bookings?.length === 0 && (
        <Alert tone="info">
          No bookings yet.{" "}
          <Link href="/" className="font-medium text-accent">
            Find an event
          </Link>
        </Alert>
      )}
      <div className="space-y-3">
        {bookings?.map((b) => (
          <Card key={b.id} className="flex flex-wrap items-center gap-4 p-4">
            <div className="flex size-12 items-center justify-center rounded-lg bg-background font-mono font-semibold">
              {b.seat.row_label}
              {b.seat.number}
            </div>
            <div className="min-w-0 flex-1">
              <Link href={`/events/${b.event.id}`} className="font-medium hover:text-accent">
                {b.event.title}
              </Link>
              <p className="text-sm text-muted">
                {formatDate(b.event.starts_at)} · {b.event.venue} · {formatPrice(b.seat.price_cents)}
              </p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${BADGE[b.status]}`}>
              {b.status}
            </span>
            {b.status === "held" && <Button onClick={() => act(b, "confirm")}>Confirm</Button>}
            {(b.status === "held" || b.status === "confirmed") && (
              <Button variant="danger" onClick={() => act(b, "cancel")}>
                Cancel
              </Button>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
