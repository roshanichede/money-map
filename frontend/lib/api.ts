export type Txn = {
  id: number;
  date: string;
  description: string;
  merchant: string;
  merchant_key: string;
  type: string;
  amount_pence: number;
  balance_pence: number | null;
  category: string;
  category_source: "rule" | "learned" | "manual";
  account: string;
};

export type MonthRow = {
  month: string;
  income_pence: number;
  spend_pence: number;
  net_pence: number;
  transaction_count: number;
  first_date: string;
  last_date: string;
};

export type Overview = { months: MonthRow[]; transaction_count: number; categorised_rate: number };

export type CategoryRow = { category: string; spend_pence: number; count: number };
export type MerchantRow = { merchant: string; category: string; spend_pence: number; count: number };

export type Driver = {
  merchant: string;
  delta_pence: number;
  this_count: number;
  prev_count: number;
  this_pence: number;
  prev_pence: number;
};
export type Change = {
  category: string;
  this_pence: number;
  prev_pence: number;
  delta_pence: number;
  this_count: number;
  prev_count: number;
  drivers: Driver[];
};
export type Comparison = {
  month: string;
  previous: string;
  this: { spend_pence: number; income_pence: number };
  prev: { spend_pence: number; income_pence: number };
  changes: Change[];
};

export type Summary = {
  month: string;
  income_pence: number;
  spend_pence: number;
  net_pence: number;
  transaction_count: number;
  categories: CategoryRow[];
  merchants: MerchantRow[];
  categorised_rate: number;
  comparison: Comparison | null;
};

export type Recurring = {
  merchant: string;
  merchant_key: string;
  category: string;
  frequency: string;
  typical_amount_pence: number;
  amount_varies: boolean;
  last_date: string;
  next_expected: string;
  occurrences: number;
  active: boolean;
  monthly_cost_pence: number;
};

export type UploadResult = {
  filename: string;
  ok: boolean;
  error?: string;
  format?: string;
  rows_read?: number;
  rows_added?: number;
  duplicates_skipped?: number;
  reconciled?: "ok" | "mismatch" | "not_checked";
  reconciliation_note?: string;
};

export type ImportRow = {
  id: number;
  filename: string;
  format: string;
  uploaded_at: string;
  rows_read: number;
  rows_added: number;
  duplicates_skipped: number;
  reconciled: "ok" | "mismatch" | "not_checked";
  reconciliation_note: string;
};

export type ChatReply = {
  answer: string;
  source: "claude" | "rules";
  guardrail: string;
  intent: string;
  evidence: Txn[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  overview: () => request<Overview>("/api/overview"),
  summary: (month: string) => request<Summary>(`/api/summary/${month}`),
  recurring: () => request<{ items: Recurring[]; active_monthly_total_pence: number }>("/api/recurring"),
  categories: () => request<string[]>("/api/categories"),
  imports: () => request<ImportRow[]>("/api/uploads"),
  transactions: (params: { month?: string; category?: string; q?: string }) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]);
    return request<Txn[]>(`/api/transactions?${qs}`);
  },
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<{ results: UploadResult[] }>("/api/upload", { method: "POST", body: form });
  },
  demo: () => request<{ results: UploadResult[] }>("/api/demo", { method: "POST" }),
  setCategory: (id: number, category: string, applyToMerchant = true) =>
    request<{ updated: number; merchant: string; category: string }>(`/api/transactions/${id}`, {
      method: "PATCH",
      ...json({ category, apply_to_merchant: applyToMerchant }),
    }),
  ask: (question: string) => request<ChatReply>("/api/chat", { method: "POST", ...json({ question }) }),
  deleteAll: () => request<{ deleted: { transactions: number } }>("/api/data", { method: "DELETE" }),
};
