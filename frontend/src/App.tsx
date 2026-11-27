import { useCallback, useEffect, useState } from "react";
import {
  getFlagged,
  getReview,
  runReview,
  sendFeedback,
  type Review,
  type Transaction,
} from "./api";
import "./App.css";

const THRESHOLDS = [0.5, 0.8, 0.95];

const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });

const percent = (p: number) => `${Math.round(p * 100)}%`;

// Sparkov prefixes every merchant name with "fraud_", normal ones included.
const merchantName = (m: string) => m.replace(/^fraud_/, "");

const categoryName = (c: string) => {
  const [kind, channel] = c.split("_");
  const label = kind.charAt(0).toUpperCase() + kind.slice(1);
  if (channel === "net") return `${label}, online`;
  if (channel === "pos") return `${label}, in store`;
  return c.replace("_", " and ").replace(/^./, (x) => x.toUpperCase());
};

function splitTime(s: string) {
  const d = new Date(s.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return { date: s, time: "" };
  return {
    date: d.toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" }),
    time: d.toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit", hour12: false }),
  };
}

const level = (p: number) => (p >= 0.9 ? "high" : p >= 0.7 ? "mid" : "low");

function ScoreMeter({ value }: { value: number }) {
  return (
    <div className="meter" data-level={level(value)}>
      <span className="meter__track" aria-hidden="true">
        <span className="meter__fill" style={{ width: `${value * 100}%` }} />
      </span>
      <span className="meter__value">{percent(value)}</span>
    </div>
  );
}

const ACTION_LABEL: Record<string, string> = {
  alert: "Alert",
  review: "Needs review",
  approve: "Approve",
};

function DecisionChip({ review }: { review?: Review }) {
  if (!review) return <span className="chip chip--none">Not reviewed</span>;
  return (
    <span className={`chip chip--${review.action}`}>
      {ACTION_LABEL[review.action] ?? review.action}
    </span>
  );
}

export default function App() {
  const [threshold, setThreshold] = useState(0.8);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Review>>({});

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    getFlagged(threshold)
      .then((data) => {
        if (cancelled) return;
        setRows(data);
        setStatus("ready");
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [threshold]);

  const saveDecision = useCallback((r: Review) => {
    setDecisions((d) => ({ ...d, [r.trans_num]: r }));
  }, []);

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <h1>Review queue</h1>
          <p className="masthead__sub">
            {status === "ready"
              ? `${rows.length} transactions scored at ${percent(threshold)} fraud likelihood or higher`
              : "Loading scored transactions"}
          </p>
        </div>
        <fieldset className="threshold">
          <legend>Minimum fraud score</legend>
          {THRESHOLDS.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={t === threshold}
              onClick={() => setThreshold(t)}
            >
              {percent(t)}
            </button>
          ))}
        </fieldset>
      </header>

      <main className="workspace">
        <section className="queue" aria-label="Flagged transactions">
          {status === "loading" && <p className="note">Loading the queue.</p>}
          {status === "error" && <p className="note note--error">{error}</p>}
          {status === "ready" && rows.length === 0 && (
            <p className="note">No transactions meet this score. Lower the minimum score to see more.</p>
          )}
          {status === "ready" && rows.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Merchant</th>
                  <th scope="col" className="num">Amount</th>
                  <th scope="col">Fraud score</th>
                  <th scope="col">Decision</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const { date, time } = splitTime(r.time);
                  const isSelected = selected?.trans_num === r.trans_num;
                  return (
                    <tr
                      key={r.trans_num}
                      tabIndex={0}
                      aria-selected={isSelected}
                      className={isSelected ? "is-selected" : undefined}
                      onClick={() => setSelected(r)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelected(r);
                        }
                      }}
                    >
                      <td>
                        <span className="stack">
                          <span>{date}</span>
                          <span className="muted">{time}</span>
                        </span>
                      </td>
                      <td>
                        <span className="stack">
                          <span>{merchantName(r.merchant)}</span>
                          <span className="muted">{categoryName(r.category)}</span>
                        </span>
                      </td>
                      <td className="num">{money(r.amt)}</td>
                      <td>
                        <ScoreMeter value={r.fraud_probability} />
                      </td>
                      <td>
                        <DecisionChip review={decisions[r.trans_num]} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        <aside className="panel" aria-label="Transaction review">
          {selected ? (
            <ReviewPanel
              key={selected.trans_num}
              txn={selected}
              review={decisions[selected.trans_num]}
              onReview={saveDecision}
            />
          ) : (
            <div className="panel__empty">
              <h2>Pick a transaction</h2>
              <p>Select a row to see its details and ask the agent to review it.</p>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

function ReviewPanel({
  txn,
  review,
  onReview,
}: {
  txn: Transaction;
  review?: Review;
  onReview: (r: Review) => void;
}) {
  const [checking, setChecking] = useState(!review);
  const [running, setRunning] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (review) return;
    let cancelled = false;
    getReview(txn.trans_num)
      .then((r) => {
        if (!cancelled && r) onReview(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [txn.trans_num, review, onReview]);

  async function handleRun() {
    setRunning(true);
    setError("");
    try {
      onReview(await runReview(txn.trans_num));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The review failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleFeedback(isFraud: boolean) {
    setSending(true);
    setError("");
    try {
      onReview(await sendFeedback(txn.trans_num, isFraud));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The feedback did not save.");
    } finally {
      setSending(false);
    }
  }

  const { date, time } = splitTime(txn.time);
  const label = review?.reviewer_label;

  return (
    <div className="detail">
      <div className="detail__head">
        <p className="detail__merchant">{merchantName(txn.merchant)}</p>
        <p className="detail__amount">{money(txn.amt)}</p>
      </div>

      <dl className="facts">
        <div>
          <dt>Date</dt>
          <dd>{date}</dd>
        </div>
        <div>
          <dt>Time</dt>
          <dd>{time}</dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{categoryName(txn.category)}</dd>
        </div>
        <div>
          <dt>Card</dt>
          <dd>Ending {String(txn.cc_num).slice(-4)}</dd>
        </div>
        <div className="facts__wide">
          <dt>Model fraud score</dt>
          <dd>
            <ScoreMeter value={txn.fraud_probability} />
          </dd>
        </div>
      </dl>

      <section className="verdict-area" aria-live="polite">
        {checking && <p className="note">Checking for a saved review.</p>}

        {!checking && running && (
          <p className="note note--working">
            The agent is checking this card's history, duplicate charges, and merchant use. This takes a few seconds.
          </p>
        )}

        {!checking && !running && review && (
          <div className={`verdict verdict--${review.action}`}>
            <p className="verdict__action">{ACTION_LABEL[review.action] ?? review.action}</p>
            <p className="verdict__risk">{review.risk.charAt(0).toUpperCase() + review.risk.slice(1)} risk</p>
            <p className="verdict__reason">{review.reason}</p>
          </div>
        )}

        {!checking && !running && !review && (
          <p className="note">This transaction has no agent review yet.</p>
        )}

        {error && <p className="note note--error">{error}</p>}

        {!checking && (
          <button type="button" className="primary" onClick={handleRun} disabled={running}>
            {running ? "Reviewing" : review ? "Run review again" : "Run review"}
          </button>
        )}
      </section>

      {review && !running && (
        <section className="feedback">
          <h2>Was this charge fraud?</h2>
          <p className="muted">Your answer is saved as a label for retraining the model.</p>
          <div className="feedback__buttons">
            <button
              type="button"
              aria-pressed={label === 1}
              disabled={sending}
              onClick={() => handleFeedback(true)}
            >
              Fraud
            </button>
            <button
              type="button"
              aria-pressed={label === 0}
              disabled={sending}
              onClick={() => handleFeedback(false)}
            >
              Not fraud
            </button>
          </div>
          {label != null && (
            <p className="muted">Saved as {label === 1 ? "fraud" : "not fraud"}.</p>
          )}
        </section>
      )}
    </div>
  );
}