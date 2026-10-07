"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Card } from "@/components/ui";
import {
  formatDate,
  formatDateTime,
  formatPrice,
  seatLabel,
  type BookingStatus,
  type Order,
} from "@/lib/api";

export const STATUS_STYLE: Record<BookingStatus, string> = {
  confirmed: "bg-seat-free/15 text-seat-free",
  held: "bg-seat-held/15 text-seat-held",
  cancelled: "bg-border text-muted",
  expired: "bg-border text-muted",
};

const DOT: Record<BookingStatus, string> = {
  held: "bg-seat-held",
  confirmed: "bg-seat-free",
  cancelled: "bg-muted",
  expired: "bg-muted",
};

export function StatusBadge({ status }: { status: BookingStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STATUS_STYLE[status]}`}>
      {status}
    </span>
  );
}

export function OrderCard({
  order,
  showUser = false,
  onConfirm,
  onCancel,
}: {
  order: Order;
  showUser?: boolean;
  onConfirm?: () => void;
  onCancel?: () => void;
}) {
  const active = order.status === "held" || order.status === "confirmed";
  const [loadedAt] = useState(Date.now); // read the clock once, not on every render
  const eventStarted = new Date(order.event.starts_at).getTime() <= loadedAt;
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted">Order #{order.id}</span>
            <StatusBadge status={order.status} />
            {showUser && <span className="text-sm font-medium">{order.user_email}</span>}
          </div>
          <Link href={`/events/${order.event.id}`} className="mt-1 block font-medium hover:text-accent">
            {order.event.title}
          </Link>
          <p className="text-sm text-muted">
            {formatDate(order.event.starts_at)} · {order.event.venue}
          </p>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold">{formatPrice(order.total_cents)}</p>
          <p className="text-xs text-muted">
            {order.seats.length} seat{order.seats.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {order.seats.map((s) => (
          <span
            key={s.id}
            title={formatPrice(s.price_cents)}
            className="rounded-md bg-background px-2 py-1 font-mono text-sm font-semibold"
          >
            {seatLabel(s)}
          </span>
        ))}
      </div>

      <details className="group mt-3">
        <summary className="cursor-pointer text-sm text-muted select-none hover:text-foreground">
          History and details
        </summary>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <ol className="space-y-3 border-l border-border pl-4">
            {order.history.map((h, i) => (
              <li key={i} className="relative">
                <span className={`absolute top-1.5 -left-[21px] size-2.5 rounded-full ${DOT[h.status]}`} />
                <p className="text-sm">
                  <span className="font-medium capitalize">{h.status}</span> · {h.detail}
                </p>
                <p className="text-xs text-muted">
                  {formatDateTime(h.created_at)} · by {h.actor_email ?? "the system"}
                </p>
              </li>
            ))}
          </ol>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <Detail label="Booked by" value={order.user_email} />
            <Detail label="Created" value={formatDateTime(order.created_at)} />
            {order.hold_expires_at && (
              <Detail label="Hold expires" value={formatDateTime(order.hold_expires_at)} />
            )}
            {order.confirmed_at && <Detail label="Confirmed" value={formatDateTime(order.confirmed_at)} />}
            {order.cancelled_at && <Detail label="Cancelled" value={formatDateTime(order.cancelled_at)} />}
            {order.expired_at && <Detail label="Expired" value={formatDateTime(order.expired_at)} />}
            {order.seats.map((s) => (
              <Detail key={s.id} label={`Seat ${seatLabel(s)}`} value={formatPrice(s.price_cents)} />
            ))}
          </dl>
        </div>
      </details>

      {(onConfirm || onCancel) && active && !eventStarted && (
        <div className="mt-3 flex gap-2">
          {order.status === "held" && onConfirm && <Button onClick={onConfirm}>Confirm</Button>}
          {onCancel && (
            <Button variant="danger" onClick={onCancel}>
              {order.status === "held" ? "Release hold" : "Cancel booking"}
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
