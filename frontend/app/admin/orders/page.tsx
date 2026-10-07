"use client";

import { useCallback, useEffect, useState } from "react";

import { OrderCard } from "@/components/order-card";
import { RequireUser } from "@/components/require-user";
import { Alert, Card } from "@/components/ui";
import { api, formatPrice, type BookingStatus, type EventSummary, type Order } from "@/lib/api";

const STATUSES: BookingStatus[] = ["held", "confirmed", "cancelled", "expired"];

export default function AdminOrdersPage() {
  return (
    <RequireUser adminOnly loginReturnTo="/admin/orders">
      {() => <AllOrders />}
    </RequireUser>
  );
}

function AllOrders() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [eventId, setEventId] = useState("");
  const [status, setStatus] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (eventId) params.set("event_id", eventId);
    if (status) params.set("status", status);
    if (email.trim()) params.set("email", email.trim());
    api<Order[]>(`/admin/orders?${params}`)
      .then(setOrders)
      .catch((e: Error) => setError(e.message));
  }, [eventId, status, email]);

  // Reload when a filter changes (debounced a little so typing an email isn't a request per key)
  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    api<EventSummary[]>("/events").then(setEvents, () => {});
  }, []);

  async function cancel(order: Order) {
    setError(null);
    try {
      await api(`/orders/${order.id}/cancel`, { method: "POST" });
    } catch (e) {
      setError((e as Error).message);
    }
    load();
  }

  const list = orders ?? [];
  const confirmed = list.filter((o) => o.status === "confirmed");
  const stats = [
    ["Orders", String(list.length)],
    ["Seats sold", String(confirmed.reduce((n, o) => n + o.seats.length, 0))],
    ["Revenue", formatPrice(confirmed.reduce((n, o) => n + o.total_cents, 0))],
    ["Active holds", String(list.filter((o) => o.status === "held").length)],
  ];
  const selectClass =
    "rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">All bookings</h1>
        <p className="mt-1 text-muted">
          Every order from every user, newest first, with the full history of each one.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <select value={eventId} onChange={(e) => setEventId(e.target.value)} className={selectClass}>
          <option value="">All events</option>
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.title}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectClass}>
          <option value="">Any status</option>
          {STATUSES.map((s) => (
            <option key={s} value={s} className="capitalize">
              {s}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Filter by email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={`${selectClass} min-w-48 flex-1`}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(([label, value]) => (
          <Card key={label} className="p-4">
            <p className="text-xs tracking-wide text-muted uppercase">{label}</p>
            <p className="mt-1 text-xl font-semibold">{value}</p>
          </Card>
        ))}
      </div>
      <p className="-mt-3 text-xs text-muted">Figures cover the orders shown (up to 200).</p>

      {error && <Alert>{error}</Alert>}
      {orders === null && !error && <p className="text-muted">Loading…</p>}
      {orders?.length === 0 && <Alert tone="info">No orders match these filters.</Alert>}
      <div className="space-y-3">
        {list.map((o) => (
          <OrderCard key={o.id} order={o} showUser onCancel={() => cancel(o)} />
        ))}
      </div>
    </div>
  );
}
