"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AdminAnalytics } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function pct(rate: number | null): string {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

function BarRow({ label, count, max }: { label: string; count: number; max: number }) {
  const width = max > 0 ? Math.max(2, Math.round((count / max) * 100)) : 0;
  return (
    <tr>
      <td className="mono">{label}</td>
      <td className="mono">{count}</td>
      <td style={{ width: "55%" }}>
        <div
          className="bar-track"
          title={`${count}`}
          aria-label={`${label}: ${count}`}
        >
          <div className="bar-fill" style={{ width: `${width}%` }} />
        </div>
      </td>
    </tr>
  );
}

export default function AdminAnalyticsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!user || user.role !== "admin") return;
    setLoading(true);
    setErr(null);
    try {
      setData(await api.adminAnalytics());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
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
        <Link href="/sign-in">Switch account</Link> to Admin.
      </div>
    );
  }

  const campMax = Math.max(1, ...(data?.campaigns_by_status.map((r) => r.count) ?? [0]));
  const subMax = Math.max(1, ...(data?.submissions_by_status.map((r) => r.count) ?? [0]));
  const reasonMax = Math.max(1, ...(data?.reject_reasons.map((r) => r.count) ?? [0]));

  return (
    <div className="stack">
      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h2>분석 / Analytics</h2>
            <p className="muted">
              Phase-0 운영 요약 — 캠페인 퍼널 · 제출 결과 · 크레딧. BI 도구 아님.
            </p>
          </div>
          <div className="row">
            <Link href="/admin" className="btn secondary" style={{ textDecoration: "none" }}>
              ← 운영 콘솔
            </Link>
            <button type="button" className="secondary" onClick={() => void load()} disabled={loading}>
              {loading ? "불러오는 중…" : "새로고침"}
            </button>
          </div>
        </div>
        {err && <p className="error">{err}</p>}
      </div>

      {!data && !err && <div className="panel muted">불러오는 중…</div>}

      {data && (
        <>
          <div className="grid two">
            <div className="panel">
              <h3>캠페인 상태 ({data.campaigns_total})</h3>
              {data.campaigns_by_status.length === 0 ? (
                <p className="muted">데이터 없음</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Count</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.campaigns_by_status.map((r) => (
                      <BarRow key={r.key} label={r.key} count={r.count} max={campMax} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="panel">
              <h3>제출 verification_status ({data.submissions_total})</h3>
              {data.submissions_by_status.length === 0 ? (
                <p className="muted">데이터 없음</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Count</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.submissions_by_status.map((r) => (
                      <BarRow key={r.key} label={r.key} count={r.count} max={subMax} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className="grid two">
            <div className="panel">
              <h3>수락 / 거절률</h3>
              <table>
                <tbody>
                  <tr>
                    <td>수락 (accepted)</td>
                    <td className="mono">{data.funnel.accepted}</td>
                  </tr>
                  <tr>
                    <td>거절 (rejected)</td>
                    <td className="mono">{data.funnel.rejected}</td>
                  </tr>
                  <tr>
                    <td>수동 큐 (needs_review)</td>
                    <td className="mono">{data.funnel.needs_review}</td>
                  </tr>
                  <tr>
                    <td>검증 대기 (submitted/in_review)</td>
                    <td className="mono">{data.funnel.pending_verify}</td>
                  </tr>
                  <tr>
                    <td>결정 완료 (decided)</td>
                    <td className="mono">{data.funnel.decided}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>수락률</strong>
                    </td>
                    <td className="mono">
                      <span className="badge ok">{pct(data.funnel.accept_rate)}</span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <strong>거절률</strong>
                    </td>
                    <td className="mono">
                      <span className="badge bad">{pct(data.funnel.reject_rate)}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="muted" style={{ marginTop: "0.75rem" }}>
                수락/거절률 = accepted|rejected ÷ decided (needs_review 제외).
              </p>
            </div>

            <div className="panel">
              <h3>크레딧 요약</h3>
              <table>
                <tbody>
                  <tr>
                    <td>지급 크레딧 (reward 합계)</td>
                    <td className="mono">{data.credits.rewards_granted_total.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td>reward 건수</td>
                    <td className="mono">{data.credits.reward_entries}</td>
                  </tr>
                  <tr>
                    <td>풀 적립 (pool_fund 합계)</td>
                    <td className="mono">{data.credits.pool_funded_total.toFixed(2)}</td>
                  </tr>
                  <tr>
                    <td>기여자 잔액 합계</td>
                    <td className="mono">{data.credits.contributor_balances_total.toFixed(2)}</td>
                  </tr>
                </tbody>
              </table>
              <h3 style={{ marginTop: "1rem" }}>Org KYB</h3>
              <table>
                <thead>
                  <tr>
                    <th>kyb_status</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {data.orgs_by_kyb.map((r) => (
                    <tr key={r.key}>
                      <td className="mono">{r.key}</td>
                      <td className="mono">{r.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {data.reject_reasons.length > 0 && (
            <div className="panel">
              <h3>거절 사유 (reject_reason)</h3>
              <table>
                <thead>
                  <tr>
                    <th>Reason</th>
                    <th>Count</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.reject_reasons.map((r) => (
                    <BarRow key={r.key} label={r.key} count={r.count} max={reasonMax} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="panel">
            <h3>캠페인별 집계</h3>
            {data.per_campaign.length === 0 ? (
              <p className="muted">캠페인 없음</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Subs</th>
                    <th>OK</th>
                    <th>Rej</th>
                    <th>Queue</th>
                    <th>Pool left</th>
                    <th>Credits</th>
                  </tr>
                </thead>
                <tbody>
                  {data.per_campaign.map((c) => (
                    <tr key={c.campaign_id}>
                      <td className="mono">{c.campaign_id}</td>
                      <td>{c.title}</td>
                      <td>
                        <span className="badge">{c.data_type}</span>
                      </td>
                      <td className="mono">{c.status}</td>
                      <td className="mono">{c.submissions_total}</td>
                      <td className="mono">{c.accepted}</td>
                      <td className="mono">{c.rejected}</td>
                      <td className="mono">{c.needs_review}</td>
                      <td className="mono">{c.reward_remaining.toFixed(1)}</td>
                      <td className="mono">{c.credits_granted.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
