from pydantic import BaseModel

class Transaction(BaseModel):
    trans_num: str
    cc_num: int
    merchant: str
    category: str
    amt: float
    time: str
    fraud_probability: float

class Review(BaseModel):
    trans_num: str
    action: str
    risk: str
    reason: str
    reviewer_label: int | None = None
    created_at: str | None = None

class Feedback(BaseModel):
    is_fraud: bool