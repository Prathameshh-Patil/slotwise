"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { OrderCard } from "@/components/order-card";
import { RequireUser } from "@/components/require-user";
import { Alert } from "@/components/ui";
import { api, type Order } from "@/lib/api";

export default function BookingsPage() {
  return <RequireUser loginReturnTo="/bookings">{() => <OrderList />}</RequireUser>;
}

function OrderList() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Order[]>("/orders/me")
      .then(setOrders)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function act(order: Order, action: "confirm" | "cancel") {
    setError(null);
    try {
      await api(`/orders/${order.id}/${action}`, { method: "POST" });
    } catch (e) {
      setError((e as Error).message);
    }
    load();
  }

  const upcoming = orders?.filter((o) => o.status === "held" || o.status === "confirmed") ?? [];
  const past = orders?.filter((o) => o.status === "cancelled" || o.status === "expired") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My bookings</h1>
        <p className="mt-1 text-muted">Every order you&apos;ve made, with its full history.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      {orders === null && !error && <p className="text-muted">Loading…</p>}
      {orders?.length === 0 && (
        <Alert tone="info">
          No bookings yet.{" "}
          <Link href="/" className="font-medium text-accent">
            Find an event
          </Link>
        </Alert>
      )}
      {upcoming.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium tracking-wide text-muted uppercase">Active</h2>
          {upcoming.map((o) => (
            <OrderCard
              key={o.id}
              order={o}
              onConfirm={() => act(o, "confirm")}
              onCancel={() => act(o, "cancel")}
            />
          ))}
        </section>
      )}
      {past.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium tracking-wide text-muted uppercase">Cancelled and expired</h2>
          {past.map((o) => (
            <OrderCard key={o.id} order={o} />
          ))}
        </section>
      )}
    </div>
  );
}
