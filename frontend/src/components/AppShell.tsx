"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { isClerkConfigured } from "@/components/providers";

const ClerkChrome = dynamic(
  () => import("@/components/ClerkChrome").then((m) => m.ClerkChrome),
  { ssr: false }
);

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, error, refresh, signOut, authMode, signedIn } = useAuth();
  const path = usePathname();
  const clerk = isClerkConfigured();

  return (
    <>
      <header className="app-header">
        <div>
          <div className="brand">data_platform</div>
          <div className="muted">
            Phase-0 OSINT · auth: {authMode === "unknown" ? "…" : authMode}
            {clerk ? " (Clerk)" : " (local session)"}
          </div>
        </div>
        <nav>
          <Link href="/" className={path === "/" ? "active" : ""}>
            Home
          </Link>
          <Link href="/admin" className={path.startsWith("/admin") ? "active" : ""}>
            Admin (KO)
          </Link>
          <Link href="/buyer" className={path.startsWith("/buyer") ? "active" : ""}>
            Buyer
          </Link>
          <Link href="/contributor" className={path.startsWith("/contributor") ? "active" : ""}>
            Contributor
          </Link>
        </nav>
        <div className="row session-bar">
          {clerk ? (
            <ClerkChrome user={user} />
          ) : signedIn && user ? (
            <>
              <span className="muted">
                <span className="badge">{user.role}</span> {user.display_name}
              </span>
              <Link href="/sign-in" className="btn secondary" style={{ textDecoration: "none" }}>
                Switch account
              </Link>
              <button type="button" className="secondary" onClick={() => void signOut()}>
                Sign out
              </button>
            </>
          ) : (
            <Link href="/sign-in" className="btn" style={{ textDecoration: "none" }}>
              Sign in
            </Link>
          )}
          <button
            type="button"
            className="secondary"
            onClick={() => void refresh()}
            disabled={loading}
          >
            Refresh
          </button>
        </div>
      </header>
      <main>
        {error && (
          <div className="panel error">
            API error: {error}. Start backend on :8000 then Refresh.
          </div>
        )}
        {!loading && !signedIn && path !== "/sign-in" && (
          <div className="panel" style={{ marginBottom: "1rem" }}>
            <strong>Signed out.</strong>{" "}
            <Link href="/sign-in">Sign in</Link> to run KYB → campaign → submit → review → export.
          </div>
        )}
        {children}
      </main>
    </>
  );
}
