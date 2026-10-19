"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type OntologyDetail, type OntologySummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AdminOntologyPage() {
  const { user } = useAuth();
  const [list, setList] = useState<OntologySummary[]>([]);
  const [detail, setDetail] = useState<OntologyDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user || (user.role !== "admin" && user.role !== "buyer")) return;
    setErr(null);
    try {
      const rows = await api.ontologies();
      setList(rows);
      const first = rows.find((r) => r.ontology_id === "osint_label") || rows[0];
      if (first) {
        setDetail(await api.ontology(first.ontology_id, first.schema_version));
      }
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
        <Link href="/sign-in">Sign in</Link> as admin or buyer.
      </div>
    );
  }
  if (user.role !== "admin" && user.role !== "buyer") {
    return (
      <div className="panel">
        Ontology view is for Admin / Buyer. <Link href="/sign-in">Switch</Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h2>온톨로지 / Ontology v0</h2>
            <p className="muted">
              Phase-0 seed JSON (읽기 전용). 캠페인은 ontology_id + schema_version을 고정합니다.
              편집은 시드 파일로 — 런타임 에디터 없음.
            </p>
          </div>
          <Link
            href={user.role === "admin" ? "/admin" : "/buyer"}
            className="btn secondary"
            style={{ textDecoration: "none" }}
          >
            ← 뒤로
          </Link>
        </div>
        {err && <p className="error">{err}</p>}
      </div>

      <div className="grid two">
        <div className="panel">
          <h3>등록된 버전</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Version</th>
                <th>Type</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={`${r.ontology_id}@${r.schema_version}`}>
                  <td className="mono">{r.ontology_id}</td>
                  <td className="mono">{r.schema_version}</td>
                  <td>
                    <span className="badge">{r.data_type}</span>
                    {r.is_default && <span className="badge ok">default</span>}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      onClick={async () => {
                        setDetail(await api.ontology(r.ontology_id, r.schema_version));
                      }}
                    >
                      보기
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h3>상세</h3>
          {!detail && <p className="muted">선택하세요</p>}
          {detail && (
            <>
              <p>
                <strong>
                  {detail.title}
                </strong>{" "}
                <span className="mono">
                  {detail.ontology_id}@{detail.schema_version}
                </span>
              </p>
              <p className="muted">{detail.description}</p>
              <p className="muted">
                Required labels:{" "}
                <span className="mono">{detail.required_label_fields.join(", ")}</span>
              </p>
              <pre
                className="mono"
                style={{
                  whiteSpace: "pre-wrap",
                  fontSize: "0.8rem",
                  background: "var(--bg)",
                  padding: "0.75rem",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  maxHeight: 360,
                  overflow: "auto",
                }}
              >
                {JSON.stringify(
                  {
                    safety: detail.safety,
                    fields: detail.fields,
                  },
                  null,
                  2
                )}
              </pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
