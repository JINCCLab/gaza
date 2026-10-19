"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Campaign, type Dataset, type Org } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function BuyerPage() {
  const { user, refresh } = useAuth();
  const [org, setOrg] = useState<Org | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [title, setTitle] = useState("EN OSINT event labels — pilot");
  const [desc, setDesc] = useState(
    "Label public open-source reporting: event type, public location, time, equipment. Online-only."
  );
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user || user.role !== "buyer") return;
    setErr(null);
    try {
      const orgs = await api.orgs();
      const mine = orgs.find((o) => o.id === user.org_id) || null;
      setOrg(mine);
      setCampaigns(await api.campaigns(user.id));
      setDatasets(await api.datasets(user.id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) return <p className="muted">Loading…</p>;
  if (user.role !== "buyer") {
    return <div className="panel">Switch role to <strong>buyer</strong> in the header.</div>;
  }

  return (
    <div className="stack">
      <div className="panel">
        <h2>Buyer — Organization & campaigns</h2>
        {org ? (
          <p>
            Org: <strong>{org.name}</strong>{" "}
            <span
              className={`badge ${
                org.kyb_status === "approved"
                  ? "ok"
                  : org.kyb_status === "rejected"
                    ? "bad"
                    : "warn"
              }`}
            >
              KYB {org.kyb_status}
            </span>
          </p>
        ) : (
          <p className="muted">No org linked.</p>
        )}
        {org?.kyb_status !== "approved" && (
          <p className="muted">Ask Admin to approve KYB before creating a campaign.</p>
        )}
        {msg && <p className="success">{msg}</p>}
        {err && <p className="error">{err}</p>}
      </div>

      <div className="panel">
        <h3>Create OSINT campaign draft</h3>
        <label>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label>Description</label>
        <textarea rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} />
        <p className="muted">
          Creates draft → funds pool (credits, 15% fee stub) → submits for Admin review.
        </p>
        <button
          type="button"
          disabled={org?.kyb_status !== "approved"}
          onClick={async () => {
            try {
              const c = await api.createCampaign(user.id, {
                title,
                description: desc,
                data_type: "osint_label",
                data_class: "structured_osint",
                target_region: "en_us_asia",
                synthetic_allowed: false,
                target_quantity: 10,
                unit_reward: 10,
                pool_fund_amount: 200,
              });
              setMsg(`Campaign #${c.id} created (${c.status}), pool=${c.reward_pool}`);
              await load();
              await refresh();
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            }
          }}
        >
          Create & submit for review
        </button>
      </div>

      <div className="panel">
        <h3>Your campaigns</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Status</th>
              <th>Pool / remaining</th>
              <th>Export</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td>{c.title}</td>
                <td>
                  <span className="badge">{c.status}</span>
                </td>
                <td className="mono">
                  {c.reward_pool} / {c.reward_remaining}
                </td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    onClick={async () => {
                      try {
                        const d = await api.exportDataset(user.id, c.id);
                        setMsg(
                          `Dataset v${d.version} exported (${d.item_count} items). Download below.`
                        );
                        await load();
                      } catch (e) {
                        setErr(e instanceof Error ? e.message : String(e));
                      }
                    }}
                  >
                    Export JSONL
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Datasets</h3>
        {datasets.length === 0 && <p className="muted">No exports yet.</p>}
        <ul>
          {datasets.map((d) => (
            <li key={d.id}>
              Campaign {d.campaign_id} · v{d.version} · {d.item_count} items —{" "}
              <a
                href={api.downloadUrl(d.id)}
                onClick={(e) => {
                  e.preventDefault();
                  // FileResponse needs auth header — fetch blob
                  void (async () => {
                    const res = await fetch(api.downloadUrl(d.id), {
                      headers: { "X-User-Id": String(user.id) },
                    });
                    if (!res.ok) {
                      setErr(await res.text());
                      return;
                    }
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `campaign_${d.campaign_id}_v${d.version}.jsonl`;
                    a.click();
                    URL.revokeObjectURL(url);
                  })();
                }}
              >
                Download JSONL
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
