const API = "http://127.0.0.1:8000";

export type Transaction = {
  trans_num: string;
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
};

export async function getFlagged(): Promise<Transaction[]> {
  const res = await fetch(`${API}/transactions/flagged?limit=20`);
  return res.json();
}

export async function runReview(id: string): Promise<Review> {
  const res = await fetch(`${API}/transactions/${id}/review`, { method: "POST" });
  return res.json();
}