"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isClerkConfigured } from "@/components/providers";

const ClerkSignInPanel = dynamic(
  () => import("@/components/ClerkSignInPanel").then((m) => m.ClerkSignInPanel),
  { ssr: false }
);

export default function SignInPage() {
  const clerk = isClerkConfigured();
  const { signInDev, signedIn, user, authMode } = useAuth();
  const router = useRouter();
  const [personas, setPersonas] = useState<User[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (clerk) return;
    void (async () => {
      try {
        await api.seed();
        setPersonas(await api.personas());
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [clerk]);

  useEffect(() => {
    if (signedIn && user) {
      const dest =
        user.role === "admin" ? "/admin" : user.role === "buyer" ? "/buyer" : "/contributor";
      router.replace(dest);
    }
  }, [signedIn, user, router]);

  if (clerk) {
    return <ClerkSignInPanel />;
  }

  return (
    <div className="stack">
      <div className="panel">
        <h2>Sign in (local session)</h2>
        <p className="muted">
          No Clerk keys detected (<code>AUTH_MODE={authMode}</code>). Choose a seeded persona — this
          issues a Bearer JWT (not the old Act-as header). Add Clerk keys in <code>.env</code> for
          the production IdP.
        </p>
        {err && <div className="error">{err}</div>}
        <div className="stack" style={{ marginTop: "1rem" }}>
          {personas.map((p) => (
            <button
              key={p.id}
              type="button"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                setErr(null);
                void signInDev(p.email)
                  .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
                  .finally(() => setBusy(false));
              }}
              style={{ textAlign: "left" }}
            >
              <strong>{p.role}</strong> — {p.display_name}
              <div className="muted">{p.email}</div>
            </button>
          ))}
          {personas.length === 0 && !err && <p className="muted">Loading personas…</p>}
        </div>
      </div>
    </div>
  );
}
