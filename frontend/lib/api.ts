// Everything the front end knows about the API: its address, its types, and one
// fetch helper that adds the login token and turns error responses into exceptions.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type User = { id: number; email: string; is_admin: boolean };

export type EventSummary = {
  id: number;
  title: string;
  description: string;
  venue: string;
  starts_at: string;
  total_seats: number;
  available_seats: number;
};

export type SeatStatus = "available" | "held" | "booked";

export type Seat = {
  id: number;
  row_label: string;
  number: number;
  price_cents: number;
  status: SeatStatus;
  mine: boolean;
};

export type BookingStatus = "held" | "confirmed" | "cancelled" | "expired";

export type Booking = {
  id: number;
  status: BookingStatus;
  hold_expires_at: string | null;
  created_at: string;
  confirmed_at: string | null;
  seat: { id: number; row_label: string; number: number; price_cents: number };
  event: { id: number; title: string; venue: string; starts_at: string };
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const TOKEN_KEY = "slotwise_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage blocked (private mode): the user just stays logged out on reload
  }
}

// FastAPI sends {"detail": "text"}, or a list of field errors for invalid input
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${d.loc?.at(-1) ?? "input"}: ${d.msg}`)
      .join("; ");
  }
  return `Request failed (${status})`;
}

export async function api<T>(
  path: string,
  options: { method?: string; json?: unknown; form?: Record<string, string> } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form) {
    body = new URLSearchParams(options.form);
  }
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { method: options.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the API running?");
  }
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(data, response.status));
  return data as T;
}

export function formatPrice(cents: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(cents / 100);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}
