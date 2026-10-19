const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type User = {
  id: number;
  email: string;
  display_name: string;
  role: string;
  auth_subject: string | null;
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
  storage_key: string | null;
  labels_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  file_hash: string | null;
  quality_score: number | null;
  verification_status: string;
  reject_reason: string | null;
  final_reward: number | null;
  created_at: string;
};

export type MediaUpload = {
  storage_key: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  media_url: string;
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

export type AuthConfig = {
  mode: "clerk" | "dev";
  configured_mode: string;
  clerk_ready: boolean;
  message: string;
  has_clerk_publishable_key: boolean;
};

export type CountByKey = { key: string; count: number };

export type AdminAnalytics = {
  campaigns_total: number;
  campaigns_by_status: CountByKey[];
  submissions_total: number;
  submissions_by_status: CountByKey[];
  funnel: {
    accepted: number;
    rejected: number;
    needs_review: number;
    pending_verify: number;
    decided: number;
    accept_rate: number | null;
    reject_rate: number | null;
  };
  reject_reasons: CountByKey[];
  credits: {
    rewards_granted_total: number;
    reward_entries: number;
    pool_funded_total: number;
    contributor_balances_total: number;
  };
  orgs_by_kyb: CountByKey[];
  per_campaign: Array<{
    campaign_id: number;
    title: string;
    data_type: string;
    status: string;
    submissions_total: number;
    accepted: number;
    rejected: number;
    needs_review: number;
    reward_pool: number;
    reward_remaining: number;
    credits_granted: number;
  }>;
};

type TokenGetter = () => Promise<string | null>;

let tokenGetter: TokenGetter | null = null;

/** Register the session token provider (Clerk getToken or local Bearer storage). */
export function setAccessTokenGetter(getter: TokenGetter | null) {
  tokenGetter = getter;
}

export async function getAccessToken(): Promise<string | null> {
  if (!tokenGetter) return null;
  return tokenGetter();
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const { headers, ...rest } = opts;
  const token = await getAccessToken();
  const isForm = typeof FormData !== "undefined" && rest.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  base: API_BASE,
  authConfig: () => request<AuthConfig>("/api/auth/config"),
  personas: () => request<User[]>("/api/auth/personas"),
  devLogin: (email: string) =>
    request<{ access_token: string; user: User; auth_mode: string }>("/api/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  seed: () =>
    request<{ seeded: boolean; users?: Record<string, { id: number }> }>("/api/seed", {
      method: "POST",
    }),
  me: () => request<User>("/api/me"),
  users: () => request<User[]>("/api/users"),
  orgs: () => request<Org[]>("/api/orgs"),
  decideKyb: (orgId: number, approve: boolean, notes?: string) =>
    request<Org>(`/api/orgs/${orgId}/kyb`, {
      method: "POST",
      body: JSON.stringify({ approve, notes }),
    }),
  campaigns: (status?: string) =>
    request<Campaign[]>(`/api/campaigns${status ? `?status=${status}` : ""}`),
  createCampaign: (body: Record<string, unknown>) =>
    request<Campaign>("/api/campaigns", { method: "POST", body: JSON.stringify(body) }),
  decideCampaign: (id: number, approve: boolean, notes?: string) =>
    request<Campaign>(`/api/campaigns/${id}/decide`, {
      method: "POST",
      body: JSON.stringify({ approve, notes }),
    }),
  submissions: (status?: string) =>
    request<Submission[]>(`/api/submissions${status ? `?status=${status}` : ""}`),
  createSubmission: (body: Record<string, unknown>) =>
    request<Submission>("/api/submissions", { method: "POST", body: JSON.stringify(body) }),
  uploadMedia: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<MediaUpload>("/api/media/upload", { method: "POST", body: fd });
  },
  reviewQueue: () => request<Submission[]>("/api/review-queue"),
  review: (id: number, body: Record<string, unknown>) =>
    request<Submission>(`/api/submissions/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  events: (id: number) =>
    request<Array<{ stage: string; result: string; detail_json: Record<string, unknown> }>>(
      `/api/submissions/${id}/events`
    ),
  exportDataset: (campaignId: number) =>
    request<Dataset>(`/api/campaigns/${campaignId}/export`, { method: "POST" }),
  datasets: () => request<Dataset[]>("/api/datasets"),
  ledger: () => request<Ledger[]>("/api/ledger"),
  allowlist: (enabledOnly = false) =>
    request<Array<{ id: number; host: string; category: string; enabled: boolean }>>(
      `/api/allowlist${enabledOnly ? "?enabled_only=true" : ""}`
    ),
  addAllowlist: (host: string, category = "admin_added") =>
    request<{ id: number; host: string; category: string; enabled: boolean }>("/api/allowlist", {
      method: "POST",
      body: JSON.stringify({ host, category }),
    }),
  setAllowlistEnabled: (id: number, enabled: boolean) =>
    request<{ id: number; host: string; category: string; enabled: boolean }>(
      `/api/allowlist/${id}/${enabled ? "enable" : "disable"}`,
      { method: "POST" }
    ),
  downloadUrl: (datasetId: number) => `${API_BASE}/api/datasets/${datasetId}/download`,
  adminAnalytics: () => request<AdminAnalytics>("/api/admin/analytics"),
};
