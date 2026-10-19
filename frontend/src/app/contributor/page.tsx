"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Campaign, type Ledger, type Submission } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const EVENT_TYPES = ["military_exercise", "equipment_display", "official_briefing"];
const EQUIPMENT = ["aircraft", "naval", "ground", "unknown"];

function allowlistFailureMessage(s: Submission): string | null {
  if (s.verification_status !== "rejected" || s.reject_reason !== "allowlist_reject") {
    return null;
  }
  const detail = s.metadata_json?.allowlist_failure as
    | { host?: string; message?: string }
    | undefined;
  if (detail?.message) return detail.message;
  const host = detail?.host || "(unknown)";
  return `Allowlist failure: source host "${host}" is not an allowed public EN news/official host (or was disabled). Online-only OSINT — no conflict-zone field collection.`;
}

export default function ContributorPage() {
  const { user, refresh } = useAuth();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [ledger, setLedger] = useState<Ledger[]>([]);
  const [hosts, setHosts] = useState<
    Array<{ id: number; host: string; category: string; enabled: boolean }>
  >([]);
  const [campaignId, setCampaignId] = useState<number | "">("");
  const [sourceUrl, setSourceUrl] = useState("https://www.reuters.com/example-osint-story");
  const [eventType, setEventType] = useState(EVENT_TYPES[0]);
  const [location, setLocation] = useState("Washington, DC (public)");
  const [eventTime, setEventTime] = useState("2026-03-01");
  const [equipment, setEquipment] = useState(EQUIPMENT[0]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [allowlistErr, setAllowlistErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user || user.role !== "contributor") return;
    setErr(null);
    try {
      const cams = await api.campaigns();
      setCampaigns(cams);
      if (cams[0] && campaignId === "") setCampaignId(cams[0].id);
      setSubs(await api.submissions());
      setLedger(await api.ledger());
      setHosts(await api.allowlist(true));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [user, campaignId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) {
    return (
      <div className="panel">
        <Link href="/sign-in">Sign in</Link> as <strong>contributor</strong>.
      </div>
    );
  }
  if (user.role !== "contributor") {
    return (
      <div className="panel">
        Signed in as <strong>{user.role}</strong>.{" "}
        <Link href="/sign-in">Switch account</Link> to contributor.
      </div>
    );
  }

  const selected = campaigns.find((c) => c.id === campaignId);

  return (
    <div className="stack">
      <div className="panel">
        <h2>Contributor — EN OSINT submissions</h2>
        <p>
          Credits: <strong className="mono">{user.credit_balance}</strong> · redeem_reserve:{" "}
          <span className="mono">{user.redeem_reserve}</span> (Phase-1 token path TBD) · reputation:{" "}
          {user.reputation_score}
        </p>
        <p className="muted">
          Online-only. Source URL must use an <strong>allowlisted</strong> public EN news/official
          host. Do not submit conflict-zone field collection.
        </p>
        {msg && <p className="success">{msg}</p>}
        {err && <p className="error">{err}</p>}
        {allowlistErr && (
          <div className="panel" style={{ borderColor: "#7f1d1d", marginTop: "0.75rem" }}>
            <strong className="error">Allowlist rejection</strong>
            <p className="error" style={{ marginBottom: 0 }}>
              {allowlistErr}
            </p>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Allowed source hosts (v0)</h3>
        <p className="muted">
          {hosts.length} enabled hosts. Submissions from other domains are rejected automatically.
        </p>
        <div className="mono muted" style={{ maxHeight: 140, overflow: "auto", fontSize: "0.8rem" }}>
          {hosts.map((h) => (
            <div key={h.id}>
              {h.host} <span className="badge">{h.category}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>Active campaigns</h3>
        {campaigns.length === 0 && (
          <p className="muted">No active campaigns yet. Wait for Admin to publish.</p>
        )}
        <ul>
          {campaigns.map((c) => (
            <li key={c.id}>
              <strong>
                #{c.id} {c.title}
              </strong>{" "}
              — reward {c.unit_reward} credits
              <div className="muted">
                {(c.requirements_json as { label_guide_en?: string }).label_guide_en}
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h3>Submit one OSINT label</h3>
        <label>Campaign</label>
        <select
          value={campaignId}
          onChange={(e) => setCampaignId(Number(e.target.value))}
          disabled={campaigns.length === 0}
        >
          {campaigns.map((c) => (
            <option key={c.id} value={c.id}>
              #{c.id} {c.title}
            </option>
          ))}
        </select>
        <label>Source URL (must be allowlisted host)</label>
        <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
        <div className="grid two">
          <div>
            <label>Event type</label>
            <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
              {EVENT_TYPES.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Equipment type</label>
            <select value={equipment} onChange={(e) => setEquipment(e.target.value)}>
              {EQUIPMENT.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
        </div>
        <label>Location (public city/region only)</label>
        <input value={location} onChange={(e) => setLocation(e.target.value)} />
        <label>Event time</label>
        <input value={eventTime} onChange={(e) => setEventTime(e.target.value)} />
        <button
          type="button"
          disabled={!selected}
          onClick={async () => {
            if (!selected) return;
            setAllowlistErr(null);
            setErr(null);
            try {
              const s = await api.createSubmission({
                campaign_id: selected.id,
                source_url: sourceUrl,
                labels: {
                  event_type: eventType,
                  location_public: location,
                  event_time: eventTime,
                  equipment_type: equipment,
                },
                claimed_capture_time: eventTime,
                license_claim: "public_reporting_fair_use_claim",
              });
              const al = allowlistFailureMessage(s);
              if (al) {
                setAllowlistErr(al);
                setMsg(`Submission #${s.id} rejected (allowlist)`);
              } else {
                setMsg(`Submission #${s.id} → ${s.verification_status}`);
              }
              await load();
              await refresh();
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            }
          }}
        >
          Submit
        </button>
      </div>

      <div className="grid two">
        <div className="panel">
          <h3>My submissions</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Detail</th>
                <th>Reward</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => {
                const al = allowlistFailureMessage(s);
                return (
                  <tr key={s.id}>
                    <td>{s.id}</td>
                    <td>
                      <span
                        className={`badge ${
                          s.verification_status === "accepted"
                            ? "ok"
                            : s.verification_status === "rejected"
                              ? "bad"
                              : "warn"
                        }`}
                      >
                        {s.verification_status}
                      </span>
                      {s.reject_reason && (
                        <div className="mono muted">{s.reject_reason}</div>
                      )}
                    </td>
                    <td className="muted" style={{ maxWidth: 280 }}>
                      {al || "—"}
                    </td>
                    <td className="mono">{s.final_reward ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h3>Credit ledger</h3>
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Amount</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((l) => (
                <tr key={l.id}>
                  <td>{l.type}</td>
                  <td className="mono">{l.amount}</td>
                  <td className="mono">{l.balance_after ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
