
const API = "http://127.0.0.1:8000";

export type Transaction = {
  trans_num: string;
  cc_num: number;
  merchant: string;
  category: string;
  amt: number;
  time: string;
  fraud_probability: number;
};

export type Review = {
  trans_num: string;
  action: string;
  risk: string;
  reason: string;
  reviewer_label: number | null;
  created_at: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, init);
  } catch {
    throw new Error("Can't reach the backend. Start it with uvicorn and try again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with status ${res.status}.`);
  }
  return res.json();
}

const id = (transNum: string) => encodeURIComponent(transNum);

export function getFlagged(threshold: number, limit = 50) {
  return request<Transaction[]>(`/transactions/flagged?threshold=${threshold}&limit=${limit}`);
}

export async function getReview(transNum: string): Promise<Review | null> {
  try {
    return await request<Review>(`/transactions/${id(transNum)}/review`);
  } catch (e) {
    if (e instanceof Error && e.message === "no review yet") return null;
    throw e;
  }
}

export function runReview(transNum: string) {
  return request<Review>(`/transactions/${id(transNum)}/review`, { method: "POST" });
}

export function sendFeedback(transNum: string, isFraud: boolean) {
  return request<Review>(`/transactions/${id(transNum)}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_fraud: isFraud }),
  });
}