from pathlib import Path
import pandas as pd
import joblib

ROOT = Path(__file__).resolve().parent.parent
model = joblib.load(ROOT / "models" / "rf_portable.joblib")
columns = joblib.load(ROOT / "models" / "rf_portable_columns.joblib")
stats = joblib.load(ROOT / "models" / "card_stats.joblib")

history = pd.read_csv(ROOT / "data" / "fraudTrain.csv")
history["trans_date_trans_time"] = pd.to_datetime(history["trans_date_trans_time"])
history["hour"] = history["trans_date_trans_time"].dt.hour

def score_transaction(txn):
    t = pd.to_datetime(txn["trans_date_trans_time"])
    hour = t.hour
     row = {
        "amt": txn["amt"],
        "hour": hour,
        "dayofweek": t.dayofweek,
        "is_night": int(hour in [22, 23, 0, 1, 2, 3]),
        "amt_vs_card": txn["amt"] / stats["card_avg"].get(txn["cc_num"], stats["overall_avg"]),
        "card_night_share": stats["card_night"].get(txn["cc_num"], stats["overall_night"]),
        txn["category"]: 1,
    }
    X = pd.DataFrame([row]).reindex(columns=columns, fill_value=0).astype(float)
    return {"fraud_probability": round(float(model.predict_proba(X)[0, 1]), 3)}

def get_card_history(cc_num):
    df = history[history["cc_num"] == cc_num]
    if len(df) == 0:
            return {"count": 0, "message": "card has no history"}
    count = len(df)
    avg_amount = float(round(df["amt"].mean(), 2))
    top_categories = df["category"].value_counts().head(3).index.tolist()
    night_share = float(round(df["hour"].isin([22, 23, 0, 1, 2, 3]).mean(), 2))
    return {"average amount": avg_amount, "top 3 categories": top_categories, "night_share": night_share, "count": count}
        
def check_duplicates(cc_num, t, amt):
    t = pd.to_datetime(t)
    df = history[(history["cc_num"] == cc_num) & (history["amt"] == amt)]
    gap = (df["trans_date_trans_time"] - t).abs()
    dupes = df[(gap <= pd.Timedelta(hours=24)) & (df["trans_date_trans_time"] != t)]
    return {
        "duplicate_count": len(dupes),
        "duplicate_times": dupes["trans_date_trans_time"].astype(str).tolist(),
    }

def check_merchant(cc_num, merchant, t):
    t = pd.to_datetime(t)
    df =  history[(history["cc_num"] == cc_num) & (history["merchant"] == merchant & history["trans_date_trans_time"] < t)]
    return {
        "past_visits": len(df),
        "seen_before": len(df) > 0,
    }

def get_transaction_facts(txn):
    t = pd.to_datetime(txn["trans_date_trans_time"])
    amt = float(txn["amt"])
    hour = t.hour
    night_hours = [22, 23, 0, 1, 2, 3]

    past = history[(history["cc_num"] == txn["cc_num"]) &
                   (history["trans_date_trans_time"] < t)]

    facts = {
        "amount": round(amt, 2),
        "hour": hour,
        "is_night": hour in night_hours,
        "category": txn["category"],
        "past_charge_count": len(past),
    }

    if len(past) == 0:
        facts["note"] = "no past charges on this card"
        return facts

    avg = past["amt"].mean()
    last_time = past["trans_date_trans_time"].max()

    facts.update({
        "card_avg_amount": round(float(avg), 2),
        "amount_vs_card_avg": round(amt / avg, 2),
        "card_max_past_amount": round(float(past["amt"].max()), 2),
        "exceeds_card_max": bool(amt > past["amt"].max()),
        "card_night_share": round(float(past["hour"].isin(night_hours).mean()), 2),
        "card_category_share": round(float((past["category"] == txn["category"]).mean()), 2),
        "hours_since_last_charge": round((t - last_time).total_seconds() / 3600, 2),
        "charges_past_24h": int((past["trans_date_trans_time"] >= t - pd.Timedelta(hours=24)).sum()),
    })
    return facts

def get_txn(trans_num):
    return history[history["trans_num"] == trans_num].iloc[0]

def score_all():
    t = history["trans_date_trans_time"]
    hour = t.dt.hour

    X = pd.DataFrame({
        "amt": history["amt"],
        "hour": hour,
        "dayofweek": t.dt.dayofweek,
        "is_night": hour.isin([22, 23, 0, 1, 2, 3]).astype(int),
        "amt_vs_card": history["amt"] / history["cc_num"].map(stats["card_avg"]).fillna(stats["overall_avg"]),
        "card_night_share": history["cc_num"].map(stats["card_night"]).fillna(stats["overall_night"]),
    })

    X = pd.concat([X, pd.get_dummies(history["category"])], axis=1)
    X = X.reindex(columns=columns, fill_value=0).astype(float)

    history["fraud_probability"] = model.predict_proba(X)[:, 1].round(3)
    