"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Card } from "@/components/ui";
import {
  ApiError,
  MAX_SEATS_PER_ORDER,
  api,
  formatDate,
  formatPrice,
  seatLabel,
  type EventSummary,
  type Order,
  type Seat,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const POLL_MS = 3000; // how often to refresh the seat map so others' picks show up

type Message = { tone: "error" | "success" | "info"; text: React.ReactNode };

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
  const [pickedIds, setPickedIds] = useState<number[]>([]);
  const [hold, setHold] = useState<Order | null>(null);
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

  // If the user already holds seats here (e.g. after a page reload), pick that back up
  useEffect(() => {
    if (!user) return;
    api<Order[]>("/orders/me")
      .then((orders) => {
        const active = orders.find((o) => o.event.id === eventId && o.status === "held");
        if (active) setHold(active);
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

  // Seats someone else grabbed since they were picked (seen on the next poll) drop out
  const picked = seats.filter((s) => pickedIds.includes(s.id) && s.status === "available");
  const pickedTotal = picked.reduce((sum, s) => sum + s.price_cents, 0);

  function toggle(seat: Seat) {
    setMessage(null);
    setHold(null);
    if (pickedIds.includes(seat.id)) {
      setPickedIds(pickedIds.filter((id) => id !== seat.id));
    } else if (picked.length >= MAX_SEATS_PER_ORDER) {
      setMessage({ tone: "info", text: `You can pick up to ${MAX_SEATS_PER_ORDER} seats at once.` });
    } else {
      setPickedIds([...pickedIds, seat.id]);
    }
  }

  async function holdSeats() {
    if (picked.length === 0) return;
    if (!user) {
      router.push(`/login?next=/events/${eventId}`);
      return;
    }
    setBusy(true);
    setMessage(null);
    setHold(null);
    try {
      const order = await api<Order>(`/events/${eventId}/orders`, {
        method: "POST",
        json: { seat_ids: picked.map((s) => s.id) },
      });
      setHold(order);
      setPickedIds([]);
    } catch (err) {
      const text =
        err instanceof ApiError && err.status === 409
          ? `Too slow! ${err.message} Your other picks are still selected.`
          : (err as Error).message;
      setMessage({ tone: "error", text });
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function confirm() {
    if (!liveHold) return;
    setBusy(true);
    try {
      const order = await api<Order>(`/orders/${liveHold.id}/confirm`, { method: "POST" });
      setHold(null);
      setMessage({
        tone: "success",
        text: (
          <>
            Booked! {order.seats.map(seatLabel).join(", ")} for {formatPrice(order.total_cents)}.
            A confirmation email is on its way.{" "}
            <Link href="/bookings" className="font-medium underline">
              See my bookings
            </Link>
          </>
        ),
      });
    } catch (err) {
      setHold(null);
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
      await api(`/orders/${liveHold.id}/cancel`, { method: "POST" });
    } catch {
      // already expired or cancelled: either way the hold is gone
    }
    setHold(null);
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
        <Alert tone="info">Your hold ran out, so those seats went back on sale. Pick again to retry.</Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
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
                    picked={picked.some((p) => p.id === seat.id)}
                    disabled={busy || liveHold !== null}
                    onToggle={() => toggle(seat)}
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
                <p className="text-sm text-muted">
                  {liveHold.seats.length === 1 ? "Seat" : `${liveHold.seats.length} seats`} held for you
                </p>
                <SeatChips labels={liveHold.seats.map(seatLabel)} />
                <p className="mt-2 text-lg font-semibold">{formatPrice(liveHold.total_cents)}</p>
              </div>
              <p className="rounded-md bg-seat-held/15 px-3 py-2 text-sm">
                Confirm within{" "}
                <span className="font-mono font-semibold">
                  {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}
                </span>{" "}
                or they go back on sale.
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
          ) : picked.length > 0 ? (
            <>
              <div>
                <p className="text-sm text-muted">
                  {picked.length} of up to {MAX_SEATS_PER_ORDER} seats picked
                </p>
                <SeatChips labels={picked.map(seatLabel)} />
                <p className="mt-2 text-lg font-semibold">{formatPrice(pickedTotal)}</p>
              </div>
              <Button onClick={holdSeats} disabled={busy} className="w-full">
                {user
                  ? `Hold ${picked.length === 1 ? "this seat" : `these ${picked.length} seats`}`
                  : "Log in to book"}
              </Button>
              <button
                onClick={() => setPickedIds([])}
                className="w-full text-center text-sm text-muted hover:text-foreground"
              >
                Clear selection
              </button>
            </>
          ) : (
            <div className="text-sm text-muted">
              <p className="font-medium text-foreground">
                {event.available_seats} of {event.total_seats} seats left
              </p>
              <p className="mt-1">
                Click green seats to pick them (up to {MAX_SEATS_PER_ORDER}), then hold them all at
                once.
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function SeatChips({ labels }: { labels: string[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {labels.map((label) => (
        <span key={label} className="rounded-md bg-background px-2 py-1 font-mono text-sm font-semibold">
          {label}
        </span>
      ))}
    </div>
  );
}

function SeatButton({
  seat,
  picked,
  disabled,
  onToggle,
}: {
  seat: Seat;
  picked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const free = seat.status === "available";
  const color = seat.mine
    ? "bg-accent text-accent-foreground border-accent"
    : picked
      ? "bg-seat-free border-seat-free text-white ring-2 ring-seat-free ring-offset-2 ring-offset-surface"
      : free
        ? "border-seat-free text-seat-free hover:bg-seat-free hover:text-white"
        : seat.status === "held"
          ? "bg-seat-held/70 border-seat-held text-white"
          : "bg-seat-booked border-seat-booked text-transparent";
  const state = seat.mine ? "yours" : picked ? "picked" : seat.status;
  return (
    <button
      onClick={onToggle}
      disabled={!free || disabled}
      title={`${seatLabel(seat)} · ${formatPrice(seat.price_cents)} · ${state}`}
      aria-label={`Seat ${seatLabel(seat)}, ${state}`}
      aria-pressed={picked}
      className={`size-7 rounded-t-lg rounded-b-sm border-2 font-mono text-[10px] transition disabled:cursor-not-allowed ${color}`}
    >
      {seat.number}
    </button>
  );
}

function Legend() {
  const items = [
    ["border-seat-free", "Available"],
    ["bg-seat-free border-seat-free", "Picked"],
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
