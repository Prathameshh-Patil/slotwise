"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Alert } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/api";

// Renders its children only for a logged-in user (and only admins if adminOnly)
export function RequireUser({
  adminOnly = false,
  loginReturnTo,
  children,
}: {
  adminOnly?: boolean;
  loginReturnTo: string;
  children: (user: User) => React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(loginReturnTo)}`);
  }, [loading, user, router, loginReturnTo]);

  if (loading || !user) return <p className="text-muted">Loading…</p>;
  if (adminOnly && !user.is_admin) return <Alert>Only admins can see this page.</Alert>;
  return <>{children(user)}</>;
}
