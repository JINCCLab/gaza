const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type User = {
  id: number;
  email: string;
  display_name: string;
  role: string;
  org_id: number | null;
  credit_balance: number;
  redeem_reserve: number;
  reputation_score: number;
  kyc_status: string;
  terms_accepted: boolean;
  status: string;
};

export type Org = {
  id: number;
  name: string;
  owner_user_id: number;
  kyb_status: string;
  intended_use: string | null;
  kyb_notes: string | null;
  status: string;
  created_at: string;
};

export type Campaign = {
  id: number;
  organization_id: number;
  title: string;
  description: string;
  data_type: string;
  data_class: string;
  target_region: string;
  requirements_json: Record<string, unknown>;
  synthetic_allowed: boolean;
  target_quantity: number;
  unit_reward: number;
  reward_pool: number;
  reward_remaining: number;
  quality_threshold: number;
  status: string;
  admin_notes: string | null;
  created_at: string;
};

export type Submission = {
  id: number;
  campaign_id: number;
  contributor_id: number;
  source_url: string;
  labels_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  file_hash: string | null;
  quality_score: number | null;
  verification_status: string;
  reject_reason: string | null;
  final_reward: number | null;
  created_at: string;
};

export type Dataset = {
  id: number;
  campaign_id: number;
  organization_id: number;
  version: number;
  item_count: number;
  export_storage_key: string | null;
  manifest_json: Record<string, unknown>;
  created_at: string;
  download_url: string | null;
};

export type Ledger = {
  id: number;
  user_id: number | null;
  organization_id: number | null;
  campaign_id: number | null;
  submission_id: number | null;
  type: string;
  amount: number;
  balance_after: number | null;
  note: string | null;
  created_at: string;
};

async function request<T>(
  path: string,
  opts: RequestInit & { userId?: number } = {}
): Promise<T> {
  const { userId, headers, ...rest } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(userId != null ? { "X-User-Id": String(userId) } : {}),
      ...(headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  base: API_BASE,
  seed: () => request<{ seeded: boolean; users?: Record<string, { id: number }> }>("/api/seed", { method: "POST" }),
  users: () => request<User[]>("/api/users"),
  me: (userId: number) => request<User>("/api/me", { userId }),
  orgs: () => request<Org[]>("/api/orgs"),
  decideKyb: (userId: number, orgId: number, approve: boolean, notes?: string) =>
    request<Org>(`/api/orgs/${orgId}/kyb`, {
      method: "POST",
      userId,
      body: JSON.stringify({ approve, notes }),
    }),
  campaigns: (userId: number, status?: string) =>
    request<Campaign[]>(`/api/campaigns${status ? `?status=${status}` : ""}`, { userId }),
  createCampaign: (userId: number, body: Record<string, unknown>) =>
    request<Campaign>("/api/campaigns", { method: "POST", userId, body: JSON.stringify(body) }),
  decideCampaign: (userId: number, id: number, approve: boolean, notes?: string) =>
    request<Campaign>(`/api/campaigns/${id}/decide`, {
      method: "POST",
      userId,
      body: JSON.stringify({ approve, notes }),
    }),
  submissions: (userId: number, status?: string) =>
    request<Submission[]>(`/api/submissions${status ? `?status=${status}` : ""}`, { userId }),
  createSubmission: (userId: number, body: Record<string, unknown>) =>
    request<Submission>("/api/submissions", { method: "POST", userId, body: JSON.stringify(body) }),
  reviewQueue: (userId: number) => request<Submission[]>("/api/review-queue", { userId }),
  review: (userId: number, id: number, body: Record<string, unknown>) =>
    request<Submission>(`/api/submissions/${id}/review`, {
      method: "POST",
      userId,
      body: JSON.stringify(body),
    }),
  events: (userId: number, id: number) =>
    request<Array<{ stage: string; result: string; detail_json: Record<string, unknown> }>>(
      `/api/submissions/${id}/events`,
      { userId }
    ),
  exportDataset: (userId: number, campaignId: number) =>
    request<Dataset>(`/api/campaigns/${campaignId}/export`, { method: "POST", userId }),
  datasets: (userId: number) => request<Dataset[]>("/api/datasets", { userId }),
  ledger: (userId: number) => request<Ledger[]>("/api/ledger", { userId }),
  allowlist: (userId?: number, enabledOnly = false) =>
    request<Array<{ id: number; host: string; category: string; enabled: boolean }>>(
      `/api/allowlist${enabledOnly ? "?enabled_only=true" : ""}`,
      userId != null ? { userId } : {}
    ),
  addAllowlist: (userId: number, host: string, category = "admin_added") =>
    request<{ id: number; host: string; category: string; enabled: boolean }>("/api/allowlist", {
      method: "POST",
      userId,
      body: JSON.stringify({ host, category }),
    }),
  setAllowlistEnabled: (userId: number, id: number, enabled: boolean) =>
    request<{ id: number; host: string; category: string; enabled: boolean }>(
      `/api/allowlist/${id}/${enabled ? "enable" : "disable"}`,
      { method: "POST", userId }
    ),
  downloadUrl: (datasetId: number) => `${API_BASE}/api/datasets/${datasetId}/download`,
};
