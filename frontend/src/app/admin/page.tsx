"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Campaign, type Org, type Submission } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AdminPage() {
  const { user, refresh } = useAuth();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [pending, setPending] = useState<Campaign[]>([]);
  const [queue, setQueue] = useState<Submission[]>([]);
  const [hosts, setHosts] = useState<
    Array<{ id: number; host: string; category: string; enabled: boolean }>
  >([]);
  const [newHost, setNewHost] = useState("");
  const [newCategory, setNewCategory] = useState("admin_added");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [memo, setMemo] = useState("");

  const load = useCallback(async () => {
    if (!user || user.role !== "admin") return;
    setErr(null);
    try {
      const [o, c, q, a] = await Promise.all([
        api.orgs(),
        api.campaigns("pending_review"),
        api.reviewQueue(),
        api.allowlist(),
      ]);
      setOrgs(o);
      setPending(c);
      setQueue(q);
      setHosts(a);
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
        <Link href="/sign-in">Sign in</Link> as <strong>admin</strong> (Admin으로 로그인하세요).
      </div>
    );
  }
  if (user.role !== "admin") {
    return (
      <div className="panel">
        Signed in as <strong>{user.role}</strong>.{" "}
        <Link href="/sign-in">Switch account</Link> to Admin (Admin 계정으로 전환하세요).
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h2>Admin 운영 콘솔</h2>
            <p className="muted">
              KYB 승인 → 캠페인 사전승인 (OSINT / CV) → 제출 수동 큐. Founder ops UI (KO/EN). CV는
              synthetic_allowed=false 기본, 민감·합성 사유 코드 사용.
            </p>
          </div>
          <Link href="/admin/analytics" className="btn secondary" style={{ textDecoration: "none" }}>
            분석 / Analytics
          </Link>
        </div>
        {msg && <p className="success">{msg}</p>}
        {err && <p className="error">{err}</p>}
      </div>

      <div className="grid two">
        <div className="panel">
          <h3>1. Org KYB</h3>
          <table>
            <thead>
              <tr>
                <th>Org</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orgs.map((o) => (
                <tr key={o.id}>
                  <td>
                    {o.name}
                    <div className="muted mono">{o.intended_use?.slice(0, 80)}</div>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        o.kyb_status === "approved"
                          ? "ok"
                          : o.kyb_status === "rejected"
                            ? "bad"
                            : "warn"
                      }`}
                    >
                      {o.kyb_status}
                    </span>
                  </td>
                  <td>
                    {o.kyb_status === "pending" && (
                      <div className="row">
                        <button
                          type="button"
                          onClick={async () => {
                            await api.decideKyb(o.id, true, "파일럿 KYB 승인");
                            setMsg(`Org #${o.id} KYB approved`);
                            await load();
                            await refresh();
                          }}
                        >
                          승인
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={async () => {
                            await api.decideKyb(o.id, false, "자료 부족");
                            setMsg(`Org #${o.id} KYB rejected`);
                            await load();
                          }}
                        >
                          거절
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h3>2. 캠페인 사전승인</h3>
          {pending.length === 0 && <p className="muted">대기 캠페인 없음</p>}
          {pending.map((c) => (
            <div key={c.id} style={{ marginBottom: "0.75rem" }}>
              <strong>
                #{c.id} {c.title}
              </strong>{" "}
              <span className="badge">{c.data_type}</span>
              <div className="muted">
                pool={c.reward_pool} remaining={c.reward_remaining} unit={c.unit_reward} ·
                synthetic={String(c.synthetic_allowed)}
              </div>
              <div className="row" style={{ marginTop: "0.4rem" }}>
                <button
                  type="button"
                  onClick={async () => {
                    await api.decideCampaign(c.id, true, "정책 통과 — publish");
                    setMsg(`Campaign #${c.id} published (active)`);
                    await load();
                  }}
                >
                  승인/게시
                </button>
                <button
                  type="button"
                  className="danger"
                  onClick={async () => {
                    await api.decideCampaign(c.id, false, "요구사항 불충분");
                    setMsg(`Campaign #${c.id} rejected`);
                    await load();
                  }}
                >
                  거절
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>3. 제출 리뷰 큐 (needs_review)</h3>
        <label>내부 메모 (KO)</label>
        <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="검수 메모…" />
        {queue.length === 0 && <p className="muted">큐 비어 있음</p>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Campaign</th>
              <th>Source / Labels</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {queue.map((s) => (
              <tr key={s.id}>
                <td className="mono">{s.id}</td>
                <td>{s.campaign_id}</td>
                <td>
                  <div className="mono">{s.source_url || s.storage_key || "(no media)"}</div>
                  <div className="muted mono">{JSON.stringify(s.labels_json)}</div>
                  {(s.metadata_json as { template?: string })?.template === "cv_media" && (
                    <span className="badge">cv_media</span>
                  )}
                </td>
                <td>
                  <div className="row">
                    <button
                      type="button"
                      onClick={async () => {
                        await api.review(s.id, {
                          accept: true,
                          reason_code: "quality_ok",
                          quality_mult: 1.0,
                          internal_memo_ko: memo || "수락",
                        });
                        setMsg(`Submission #${s.id} accepted → credit granted`);
                        await load();
                        await refresh();
                      }}
                    >
                      수락
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={async () => {
                        const isCv =
                          (s.metadata_json as { template?: string })?.template === "cv_media";
                        await api.review(s.id, {
                          accept: false,
                          reason_code: isCv ? "synthetic_suspected" : "label_quality",
                          internal_memo_ko:
                            memo || (isCv ? "합성/민감 의심 거절" : "라벨 품질 부족"),
                        });
                        setMsg(`Submission #${s.id} rejected`);
                        await load();
                      }}
                    >
                      거절
                    </button>
                    {(s.metadata_json as { template?: string })?.template === "cv_media" && (
                      <button
                        type="button"
                        className="danger"
                        onClick={async () => {
                          await api.review(s.id, {
                            accept: false,
                            reason_code: "sensitive_person",
                            internal_memo_ko: memo || "인물·시설 민감 — 거절",
                          });
                          setMsg(`Submission #${s.id} rejected (sensitive)`);
                          await load();
                        }}
                      >
                        민감거절
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Allowlist v0 (호스트 목록 / 추가 / 비활성)</h3>
        <p className="muted">
          Phase-0 EN 공개 보도·공식 호스트. 비활성(disable)하면 제출 시 allowlist 거절. 소셜 덤프·분쟁지
          현장 출처는 넣지 마세요.
        </p>
        <table>
          <thead>
            <tr>
              <th>Host</th>
              <th>Category</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {hosts.map((h) => (
              <tr key={h.id}>
                <td className="mono">{h.host}</td>
                <td>
                  <span className="badge">{h.category}</span>
                </td>
                <td>
                  <span className={`badge ${h.enabled ? "ok" : "bad"}`}>
                    {h.enabled ? "enabled" : "disabled"}
                  </span>
                </td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    onClick={async () => {
                      await api.setAllowlistEnabled(h.id, !h.enabled);
                      setMsg(
                        h.enabled
                          ? `Disabled ${h.host}`
                          : `Enabled ${h.host}`
                      );
                      await load();
                    }}
                  >
                    {h.enabled ? "비활성" : "활성"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <input
            style={{ marginBottom: 0, maxWidth: 280 }}
            value={newHost}
            onChange={(e) => setNewHost(e.target.value)}
            placeholder="add host e.g. reuters.com"
          />
          <select
            style={{ marginBottom: 0, width: "auto" }}
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
          >
            <option value="admin_added">admin_added</option>
            <option value="us_wire_national">us_wire_national</option>
            <option value="us_defense_outlet">us_defense_outlet</option>
            <option value="us_gov_military">us_gov_military</option>
            <option value="asia_en_outlet">asia_en_outlet</option>
            <option value="en_international">en_international</option>
            <option value="public_eo_archive">public_eo_archive</option>
          </select>
          <button
            type="button"
            className="secondary"
            onClick={async () => {
              await api.addAllowlist(newHost, newCategory);
              setNewHost("");
              setMsg("Host added / re-enabled");
              await load();
            }}
          >
            호스트 추가
          </button>
        </div>
      </div>
    </div>
  );
}
