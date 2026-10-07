"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense } from "react";

import { useAuth } from "@/lib/auth";

type NavLinkProps = { href: string; children: React.ReactNode };

function NavLinkView({ href, children, active }: NavLinkProps & { active: boolean }) {
  return (
    <Link
      href={href}
      className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-background font-medium" : "text-muted hover:text-foreground"}`}
    >
      {children}
    </Link>
  );
}

function ActiveNavLink(props: NavLinkProps) {
  return <NavLinkView {...props} active={usePathname() === props.href} />;
}

// The current path is only known at request time on dynamic routes like
// /events/[id], so it is read inside Suspense; until then the link renders plain.
function NavLink(props: NavLinkProps) {
  return (
    <Suspense fallback={<NavLinkView {...props} active={false} />}>
      <ActiveNavLink {...props} />
    </Suspense>
  );
}

export function Header() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-3">
        <Link href="/" className="mr-4 text-lg font-semibold tracking-tight">
          Slot<span className="text-accent">wise</span>
        </Link>
        <nav className="flex flex-1 items-center gap-1">
          <NavLink href="/">Events</NavLink>
          {user && <NavLink href="/bookings">My bookings</NavLink>}
          {user?.is_admin && <NavLink href="/admin">New event</NavLink>}
        </nav>
        {loading ? null : user ? (
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-muted sm:inline">{user.email}</span>
            <button
              onClick={() => {
                logout();
                router.push("/");
              }}
              className="rounded-md border border-border px-3 py-1.5 hover:bg-background"
            >
              Log out
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm">
            <Link href="/login" className="rounded-md px-3 py-1.5 hover:bg-background">
              Log in
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-accent px-3 py-1.5 font-medium text-accent-foreground"
            >
              Sign up
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
