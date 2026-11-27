from fastapi import FastAPI, HTTPException
from src.tools import get_txn, score_transaction, score_all, history
from src.agent import review_transaction
from backend.schemas import Transaction, Review, Feedback
from backend.db import init_db, save_review, get_review, save_feedback
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()
score_all()

@app.get("/transactions/flagged", response_model = list[Transaction])
def get_flagged(threshold: float= 0.5, limit: int = 50):
    df = history[history["fraud_probability"] >= threshold].sort_values("fraud_probability", ascending=False).head(limit)
    return [
        Transaction(
            trans_num=row["trans_num"],
            cc_num=int(row["cc_num"]),
            merchant=row["merchant"],
            category=row["category"],
            amt=float(row["amt"]),
            time=str(row["trans_date_trans_time"]),
            fraud_probability=float(row["fraud_probability"]),
        )
        for _, row in df.iterrows()
    ]

@app.get("/transactions/{trans_num}", response_model=Transaction)
def get_transaction(trans_num: str):
    try:
        txn = get_txn(trans_num)
    except IndexError:
        raise HTTPException(status_code=404, detail="transaction not found")

    score = score_transaction(txn)

    return Transaction(
        trans_num=trans_num,
        cc_num=int(txn["cc_num"]),
        merchant=txn["merchant"],
        category=txn["category"],
        amt=float(txn["amt"]),
        time=str(txn["trans_date_trans_time"]),
        fraud_probability=score["fraud_probability"],
    )

@app.post("/transactions/{trans_num}/review", response_model=Review)
def run_review(trans_num: str):
    try:
        get_txn(trans_num)
    except IndexError:
        raise HTTPException(status_code=404, detail="transaction not found")

    decision = review_transaction(trans_num)
    save_review(trans_num, decision)
    return Review(**get_review(trans_num))

@app.get("/transactions/{trans_num}/review", response_model=Review)
def read_review(trans_num: str):
    review = get_review(trans_num)
    if review is None:
        raise HTTPException(status_code=404, detail="no review yet")
    return Review(**review)
    

@app.post("/transactions/{trans_num}/feedback", response_model=Review)
def give_feedback(trans_num: str, body: Feedback):
    if get_review(trans_num) is None:
        raise HTTPException(status_code=404, detail="no review yet")
    save_feedback(trans_num, int(body.is_fraud))
    return Review(**get_review(trans_num))

