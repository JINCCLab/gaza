"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { users, user, setUserId, loading, error, refresh } = useAuth();
  const path = usePathname();

  return (
    <>
      <header className="app-header">
        <div>
          <div className="brand">data_platform</div>
          <div className="muted">Phase-0 OSINT vertical slice (demo auth)</div>
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
        <div className="row">
          <label htmlFor="role" style={{ margin: 0 }}>
            Act as
          </label>
          <select
            id="role"
            value={user?.id ?? ""}
            onChange={(e) => setUserId(Number(e.target.value))}
            style={{ marginBottom: 0, width: "auto", minWidth: 220 }}
            disabled={loading || users.length === 0}
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.role} — {u.display_name}
              </option>
            ))}
          </select>
          <button type="button" className="secondary" onClick={() => void refresh()}>
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
        {children}
      </main>
    </>
  );
}
