"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Card } from "@/components/ui";
import {
  ApiError,
  api,
  formatDate,
  formatPrice,
  type Booking,
  type EventSummary,
  type Seat,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const POLL_MS = 3000; // how often to refresh the seat map so others' picks show up

type Message = { tone: "error" | "success" | "info"; text: React.ReactNode };

function seatLabel(seat: { row_label: string; number: number }) {
  return `${seat.row_label}${seat.number}`;
}

function useCountdown(until: string | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!until) return;
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0); // start from the current time, not the last tick
    const timer = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [until]);
  return until ? Math.max(0, Math.floor((new Date(until).getTime() - now) / 1000)) : 0;
}

export function SeatPicker({ eventId }: { eventId: number }) {
  const { user } = useAuth();
  const router = useRouter();
  const [event, setEvent] = useState<EventSummary | null>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [hold, setHold] = useState<Booking | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);
  const [notFound, setNotFound] = useState(false);
  const secondsLeft = useCountdown(hold?.hold_expires_at ?? null);

  const load = useCallback(
    () =>
      Promise.all([
        api<EventSummary>(`/events/${eventId}`),
        api<Seat[]>(`/events/${eventId}/seats`),
      ]).then(
        ([e, s]) => {
          setEvent(e);
          setSeats(s);
        },
        (err) => {
          if (err instanceof ApiError && err.status === 404) setNotFound(true);
        },
      ),
    [eventId],
  );
  const refresh = () => void load();

  // Load the seat map, then keep it fresh while the page is open
  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [load, user]);

  // If the user already holds a seat here (e.g. after a page reload), pick it back up
  useEffect(() => {
    if (!user) return;
    api<Booking[]>("/bookings/me")
      .then((bookings) => {
        const active = bookings.find((b) => b.event.id === eventId && b.status === "held");
        if (active) {
          setHold(active);
          setSelectedId(active.seat.id);
        }
      })
      .catch(() => {});
  }, [user, eventId]);

  // A hold only counts while its countdown runs (and while someone is logged in)
  const liveHold = user && hold && secondsLeft > 0 ? hold : null;
  const holdRanOut = user && hold && secondsLeft === 0;

  const rows = useMemo(() => {
    const byRow = new Map<string, Seat[]>();
    for (const seat of seats) byRow.set(seat.row_label, [...(byRow.get(seat.row_label) ?? []), seat]);
    return [...byRow.entries()];
  }, [seats]);

  // A seat someone else grabbed since it was picked (seen on the next poll) is dropped
  const picked = seats.find((s) => s.id === selectedId);
  const selected =
    picked && !holdRanOut && (picked.status === "available" || liveHold) ? picked : null;

  async function holdSeat() {
    if (!selected) return;
    if (!user) {
      router.push(`/login?next=/events/${eventId}`);
      return;
    }
    setBusy(true);
    setMessage(null);
    setHold(null);
    try {
      setHold(await api<Booking>(`/seats/${selected.id}/hold`, { method: "POST" }));
    } catch (err) {
      const text =
        err instanceof ApiError && err.status === 409
          ? `Too slow! Someone else just took seat ${seatLabel(selected)}. Pick another one.`
          : (err as Error).message;
      setMessage({ tone: "error", text });
      setSelectedId(null);
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function confirm() {
    if (!liveHold) return;
    setBusy(true);
    try {
      const booking = await api<Booking>(`/bookings/${liveHold.id}/confirm`, { method: "POST" });
      setHold(null);
      setSelectedId(null);
      setMessage({
        tone: "success",
        text: (
          <>
            Booked! Seat {seatLabel(booking.seat)} is yours. A confirmation email is on its way.{" "}
            <Link href="/bookings" className="font-medium underline">
              See my bookings
            </Link>
          </>
        ),
      });
    } catch (err) {
      setHold(null);
      setSelectedId(null);
      setMessage({ tone: "error", text: (err as Error).message });
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function release() {
    if (!liveHold) return;
    setBusy(true);
    try {
      await api(`/bookings/${liveHold.id}/cancel`, { method: "POST" });
    } catch {
      // already expired or cancelled: either way the hold is gone
    }
    setHold(null);
    setSelectedId(null);
    setBusy(false);
    refresh();
  }

  if (notFound) return <Alert>This event doesn&apos;t exist.</Alert>;
  if (!event) return <p className="text-muted">Loading event…</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-muted hover:text-foreground">
          ← All events
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{event.title}</h1>
        <p className="text-muted">
          {formatDate(event.starts_at)} · {event.venue}
        </p>
        {event.description && <p className="mt-2 max-w-2xl">{event.description}</p>}
      </div>

      {message && <Alert tone={message.tone}>{message.text}</Alert>}
      {holdRanOut && (
        <Alert tone="info">Your hold ran out, so the seat went back on sale. Pick a seat to try again.</Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <Card className="overflow-x-auto p-5">
          <div className="mx-auto mb-6 w-2/3 rounded-b-xl bg-border py-1.5 text-center text-xs font-medium tracking-widest text-muted uppercase">
            Stage
          </div>
          <div className="mx-auto w-max space-y-1.5">
            {rows.map(([row, rowSeats]) => (
              <div key={row} className="flex items-center gap-1.5">
                <span className="w-5 text-right font-mono text-xs text-muted">{row}</span>
                {rowSeats.map((seat) => (
                  <SeatButton
                    key={seat.id}
                    seat={seat}
                    selected={seat.id === selectedId}
                    disabled={busy || liveHold !== null}
                    onSelect={() => {
                      setMessage(null);
                      setHold(null);
                      setSelectedId(seat.id === selectedId ? null : seat.id);
                    }}
                  />
                ))}
              </div>
            ))}
          </div>
          <Legend />
        </Card>

        <Card className="h-fit space-y-4 p-5">
          {liveHold ? (
            <>
              <div>
                <p className="text-sm text-muted">Seat held for you</p>
                <p className="text-3xl font-semibold">{seatLabel(liveHold.seat)}</p>
                <p className="text-sm">{formatPrice(liveHold.seat.price_cents)}</p>
              </div>
              <p className="rounded-md bg-seat-held/15 px-3 py-2 text-sm">
                Confirm within{" "}
                <span className="font-mono font-semibold">
                  {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}
                </span>{" "}
                or it goes back on sale.
              </p>
              <div className="flex gap-2">
                <Button onClick={confirm} disabled={busy} className="flex-1">
                  Confirm booking
                </Button>
                <Button variant="secondary" onClick={release} disabled={busy}>
                  Release
                </Button>
              </div>
            </>
          ) : selected ? (
            <>
              <div>
                <p className="text-sm text-muted">Selected seat</p>
                <p className="text-3xl font-semibold">{seatLabel(selected)}</p>
                <p className="text-sm">{formatPrice(selected.price_cents)}</p>
              </div>
              <Button onClick={holdSeat} disabled={busy} className="w-full">
                {user ? "Hold this seat" : "Log in to book"}
              </Button>
            </>
          ) : (
            <div className="text-sm text-muted">
              <p className="font-medium text-foreground">
                {event.available_seats} of {event.total_seats} seats left
              </p>
              <p className="mt-1">Pick a green seat on the map to get started.</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function SeatButton({
  seat,
  selected,
  disabled,
  onSelect,
}: {
  seat: Seat;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  const free = seat.status === "available";
  const color = seat.mine
    ? "bg-accent text-accent-foreground border-accent"
    : free
      ? "border-seat-free text-seat-free hover:bg-seat-free hover:text-white"
      : seat.status === "held"
        ? "bg-seat-held/70 border-seat-held text-white"
        : "bg-seat-booked border-seat-booked text-transparent";
  const state = seat.mine ? "yours" : seat.status;
  return (
    <button
      onClick={onSelect}
      disabled={!free || disabled}
      title={`${seatLabel(seat)} · ${formatPrice(seat.price_cents)} · ${state}`}
      aria-label={`Seat ${seatLabel(seat)}, ${state}`}
      aria-pressed={selected}
      className={`size-7 rounded-t-lg rounded-b-sm border-2 font-mono text-[10px] transition disabled:cursor-not-allowed ${color} ${
        selected && !seat.mine ? "bg-seat-free text-white ring-2 ring-seat-free ring-offset-2 ring-offset-surface" : ""
      }`}
    >
      {seat.number}
    </button>
  );
}

function Legend() {
  const items = [
    ["border-seat-free", "Available"],
    ["bg-seat-held/70 border-seat-held", "Held"],
    ["bg-seat-booked border-seat-booked", "Booked"],
    ["bg-accent border-accent", "Yours"],
  ];
  return (
    <div className="mt-6 flex flex-wrap justify-center gap-4 text-xs text-muted">
      {items.map(([cls, label]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className={`size-3.5 rounded-t-md rounded-b-sm border-2 ${cls}`} />
          {label}
        </span>
      ))}
    </div>
  );
}
