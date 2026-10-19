"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { user, loading } = useAuth();

  return (
    <div className="stack">
      <div className="panel">
        <h2>Happy path (vertical slice)</h2>
        <ol className="muted">
          <li>
            <strong>Admin</strong> — approve Org KYB
          </li>
          <li>
            <strong>Buyer</strong> — create OSINT campaign draft (auto pending_review + pool fund)
          </li>
          <li>
            <strong>Admin</strong> — approve / publish campaign
          </li>
          <li>
            <strong>Contributor</strong> — submit one EN OSINT label (URL + labels JSON)
          </li>
          <li>
            <strong>Admin</strong> — manual accept in review queue → CreditLedger reward
          </li>
          <li>
            <strong>Buyer</strong> — Dataset v1 JSONL export / download
          </li>
        </ol>
        <p className="muted">
          Contributor & Buyer UI = English. Admin ops labels = Korean where useful. Online-only
          OSINT; no on-chain token; no CV template.
        </p>
        {!loading && user && (
          <p>
            Current role: <span className="badge">{user.role}</span> {user.email}
          </p>
        )}
        <div className="row" style={{ marginTop: "1rem" }}>
          <Link className="btn" href="/admin">
            Go Admin
          </Link>
          <Link className="btn secondary" href="/buyer">
            Go Buyer
          </Link>
          <Link className="btn secondary" href="/contributor">
            Go Contributor
          </Link>
        </div>
      </div>
    </div>
  );
}
