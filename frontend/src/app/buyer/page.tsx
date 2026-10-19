"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Campaign, type Dataset, type Org } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type TemplateKind = "osint_label" | "cv_media";

export default function BuyerPage() {
  const { user, refresh, getAccessToken } = useAuth();
  const [org, setOrg] = useState<Org | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [template, setTemplate] = useState<TemplateKind>("osint_label");
  const [title, setTitle] = useState("EN OSINT event labels — pilot");
  const [desc, setDesc] = useState(
    "Label public open-source reporting: event type, public location, time, equipment. Online-only."
  );
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [legalName, setLegalName] = useState("Demo Buyer Org LLC");
  const [registrationId, setRegistrationId] = useState("REG-DEMO-001");
  const [docUrl, setDocUrl] = useState("https://example.com/kyb-certificate-stub.pdf");
  const [kybFile, setKybFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const applyTemplateDefaults = (kind: TemplateKind) => {
    setTemplate(kind);
    if (kind === "cv_media") {
      setTitle("EN CV public-scene annotations — pilot");
      setDesc(
        "Annotate whitelist public scenes (parade, museum, official promo, airshow, open viewing). Bounding boxes + caption. synthetic_allowed=false. No conflict-zone field collection."
      );
    } else {
      setTitle("EN OSINT event labels — pilot");
      setDesc(
        "Label public open-source reporting: event type, public location, time, equipment. Online-only."
      );
    }
  };

  const load = useCallback(async () => {
    if (!user || user.role !== "buyer") return;
    setErr(null);
    try {
      const orgs = await api.orgs();
      const mine = orgs.find((o) => o.id === user.org_id) || null;
      setOrg(mine);
      setCampaigns(await api.campaigns());
      setDatasets(await api.datasets());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) {
    return (
      <div className="panel">
        <Link href="/sign-in">Sign in</Link> as <strong>buyer</strong>.
      </div>
    );
  }
  if (user.role !== "buyer") {
    return (
      <div className="panel">
        Signed in as <strong>{user.role}</strong>. <Link href="/sign-in">Switch account</Link> to
        buyer.
      </div>
    );
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
          <p className="muted">
            Submit the KYB stub packet below, then ask Admin to approve before creating a campaign.
          </p>
        )}
        {msg && <p className="success">{msg}</p>}
        {err && <p className="error">{err}</p>}
      </div>

      {org && org.kyb_status !== "approved" && (
        <div className="panel">
          <h3>KYB document stub</h3>
          <p className="muted">
            Phase-0 stub only — company name, registration id, and a file URL or upload. No real ID
            verification vendor.
          </p>
          {org.kyb_packet_ready && (
            <p className="success">
              Packet ready
              {org.kyb_legal_name ? ` · ${org.kyb_legal_name}` : ""}
              {org.kyb_registration_id ? ` · ${org.kyb_registration_id}` : ""}
            </p>
          )}
          <label>Legal / company name</label>
          <input value={legalName} onChange={(e) => setLegalName(e.target.value)} />
          <label>Registration id</label>
          <input value={registrationId} onChange={(e) => setRegistrationId(e.target.value)} />
          <label>Document URL (optional if you upload a file)</label>
          <input value={docUrl} onChange={(e) => setDocUrl(e.target.value)} placeholder="https://…" />
          <label>Or upload stub file (PDF / PNG / JPEG / TXT)</label>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,application/pdf,image/*,text/plain"
            onChange={(e) => setKybFile(e.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            disabled={uploading}
            onClick={async () => {
              setErr(null);
              setUploading(true);
              try {
                let storage_key: string | undefined;
                let filename: string | undefined;
                let content_type: string | undefined;
                if (kybFile) {
                  const up = await api.uploadKybDocument(org.id, kybFile);
                  storage_key = up.storage_key;
                  filename = up.filename;
                  content_type = up.content_type;
                }
                const updated = await api.submitKybPacket(org.id, {
                  legal_name: legalName,
                  registration_id: registrationId,
                  document_url: docUrl.trim() || undefined,
                  storage_key,
                  filename,
                  content_type,
                });
                setOrg(updated);
                setMsg(
                  updated.kyb_packet_ready
                    ? "KYB stub packet submitted — waiting for Admin review"
                    : "KYB packet saved"
                );
                await load();
              } catch (e) {
                setErr(e instanceof Error ? e.message : String(e));
              } finally {
                setUploading(false);
              }
            }}
          >
            {uploading ? "Submitting…" : "Submit KYB stub packet"}
          </button>
        </div>
      )}

      <div className="panel">
        <h3>Create campaign draft</h3>
        <label>Template (same platform)</label>
        <select
          value={template}
          onChange={(e) => applyTemplateDefaults(e.target.value as TemplateKind)}
        >
          <option value="osint_label">osint_label — structured OSINT labels</option>
          <option value="cv_media">cv_media — public-scene CV annotations</option>
        </select>
        <label>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label>Description</label>
        <textarea rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} />
        <p className="muted">
          Creates draft → funds pool (credits, 15% fee stub) → submits for Admin review.
          {template === "cv_media" && (
            <>
              {" "}
              CV defaults: <code>synthetic_allowed=false</code>, public scene category whitelist.
            </>
          )}
        </p>
        <button
          type="button"
          disabled={org?.kyb_status !== "approved"}
          onClick={async () => {
            try {
              const c = await api.createCampaign({
                title,
                description: desc,
                data_type: template,
                data_class:
                  template === "cv_media" ? "public_scene_cv" : "structured_osint",
                target_region: "en_us_asia",
                synthetic_allowed: false,
                target_quantity: 10,
                unit_reward: template === "cv_media" ? 12 : 10,
                pool_fund_amount: 200,
              });
              setMsg(
                `Campaign #${c.id} (${c.data_type}) created (${c.status}), pool=${c.reward_pool}`
              );
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
              <th>Type</th>
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
                  <span className="badge">{c.data_type}</span>
                  {c.synthetic_allowed ? (
                    <span className="badge warn">synthetic</span>
                  ) : (
                    <span className="badge ok">real-only</span>
                  )}
                </td>
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
                        const d = await api.exportDataset(c.id);
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
                  void (async () => {
                    const token = await getAccessToken();
                    const res = await fetch(api.downloadUrl(d.id), {
                      headers: token ? { Authorization: `Bearer ${token}` } : {},
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
