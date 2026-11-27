import { useEffect, useState } from "react";
import { getFlagged, runReview, type Transaction, type Review } from "./api";

export default function App() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { getFlagged().then(setRows); }, []);

  async function handleReview(id: string) {
    setLoading(true);
    setReview(await runReview(id));
    setLoading(false);
  }

  return (
    <div style={{ padding: 24, fontFamily: "sans-serif" }}>
      <h1>Flagged transactions</h1>
      <table>
        <thead>
          <tr><th>Time</th><th>Merchant</th><th>Category</th><th>Amount</th><th>Score</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.trans_num}>
              <td>{r.time}</td><td>{r.merchant}</td><td>{r.category}</td>
              <td>${r.amt.toFixed(2)}</td><td>{r.fraud_probability}</td>
              <td><button onClick={() => handleReview(r.trans_num)}>Review</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {loading && <p>Agent is reviewing...</p>}
      {review && !loading && (
        <div style={{ marginTop: 24 }}>
          <h2>{review.action.toUpperCase()} ({review.risk})</h2>
          <p>{review.reason}</p>
        </div>
      )}
    </div>
  );
}