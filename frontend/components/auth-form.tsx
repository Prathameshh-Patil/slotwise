"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Card, Field } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const router = useRouter();
  // Where to go afterwards, e.g. back to the seat the user was picking.
  // Only same-site paths, so a crafted link can't send people to another site.
  const next = useSearchParams().get("next");
  const target = next?.startsWith("/") && !next.startsWith("//") ? next : "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isLogin = mode === "login";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (isLogin ? login : register)(email, password);
      router.push(target);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const other = isLogin ? "/register" : "/login";
  return (
    <Card className="mx-auto max-w-sm p-6">
      <h1 className="text-xl font-semibold">{isLogin ? "Log in" : "Create an account"}</h1>
      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          label="Password"
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          required
          minLength={isLogin ? undefined : 8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Please wait…" : isLogin ? "Log in" : "Sign up"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        {isLogin ? "New here? " : "Already have an account? "}
        <Link
          href={next ? `${other}?next=${encodeURIComponent(next)}` : other}
          className="font-medium text-accent"
        >
          {isLogin ? "Create an account" : "Log in"}
        </Link>
      </p>
    </Card>
  );
}
