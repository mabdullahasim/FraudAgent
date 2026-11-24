import json
from dotenv import load_dotenv
import anthropic
from pathlib import Path
from src.tools import (get_txn, score_transaction, get_transaction_facts, check_duplicates, check_merchant)


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
client = anthropic.Anthropic()

MODEL = "claude-haiku-5-5"
MAX_ROUNDS = 10

SYSTEM_PROMPT = """You are a fraud analyst. You review one flagged card transaction and decide whether it fits the card's normal habits.

TOOLS
Use the tools to gather evidence about the card's history before you decide. Call only the tools you need. Do not repeat a call with the same inputs. Stop calling tools once the evidence supports a decision.

WHAT TO CHECK
Compare the flagged charge against the card's baseline:
1. Amount: compare to the card's average and largest past charge.
2. Merchant: a merchant the card has never used, or a category the card rarely or never uses.
3. Timing: a charge at night on a card that rarely spends at night.
4. Velocity: hours since the card's last charge, and the number of charges in the past 24 hours.
5. Duplicates: the same amount charged to the card within 24 hours.

MODEL SCORE
The model's fraud probability is one signal. A high score supports suspicion, but the card's own history decides. Do not alert on the score alone.

HOW TO WEIGH EVIDENCE
- One unusual signal alone is weak evidence. Do not alert on one signal.
- Two or more unusual signals that point the same way are strong evidence.
- Evidence that conflicts (some signals unusual, others strongly normal) calls for review.
- Missing or failed tool data counts as uncertainty. Lean toward review, not approve.
- A card with no past charges has no baseline. Judge the charge on its own numbers and lean toward review.
- Judge the charge by numbers from the tools. Do not assume facts the tools did not return.

DECISION MAP
- approve / low: the charge fits the card's habits. No more than one minor deviation.
- review / medium: conflicting signals, one strong signal, or incomplete data.
- alert / high: two or more strong signals agree, such as a large amount at night in a category the card has never used.

OUTPUT
Return JSON only. No text before or after. No code fences. Use exactly these three keys:
{"action": "approve|review|alert", "risk": "low|medium|high", "reason": "..."}

The reason is two or three sentences. Cite specific numbers from the tools, such as the amount against the card's average, the card's night share, or the hours since the last charge. Name the signals that drove the decision.

Example:
{"action": "alert", "risk": "high", "reason": "The $940 charge is 21 times the card's $45 average and exceeds its largest past charge of $310. It came at 23:00 on a card with 4% night activity, in a category the card has never used."}
"""

TOOLS = [
    {
        "name": "score_transaction",
        "description": "Get the ML model's fraud probability (0 to 1) for a transaction.",
        "input_schema": {
            "type": "object",
            "properties": {"trans_num": {"type": "string"}},
            "required": ["trans_num"],
        },
    },
    {
        "name": "get_transaction_facts",
        "description": "Get numbers comparing this transaction with the card's past charges: amount vs average, night activity, category share, time since last charge, charges in past 24 hours.",
        "input_schema": {
            "type": "object",
            "properties": {"trans_num": {"type": "string"}},
            "required": ["trans_num"],
        },
    },
    {
        "name": "check_duplicates",
        "description": "Find charges on the same card with the same amount within 24 hours.",
        "input_schema": {
            "type": "object",
            "properties": {"trans_num": {"type": "string"}},
            "required": ["trans_num"],
        },
    },
    {
        "name": "check_merchant",
        "description": "Check whether the card used this merchant before this transaction, and how many times.",
        "input_schema": {
            "type": "object",
            "properties": {"trans_num": {"type": "string"}},
            "required": ["trans_num"],
        },
    },
]


def run_tool(name, tool_input):
    try:
        txn = get_txn(tool_input["trans_num"])
    except (KeyError, IndexError):
        return json.dumps({"error": "transaction not found"})

    if name == "score_transaction":
        result = score_transaction(txn)
    elif name == "get_transaction_facts":
        result = get_transaction_facts(txn)
    elif name == "check_duplicates":
        result = check_duplicates(txn["cc_num"], txn["trans_date_trans_time"], txn["amt"])
    elif name == "check_merchant":
        result = check_merchant(txn["cc_num"], txn["merchant"], txn["trans_date_trans_time"])
    else:
        result = {"error": f"unknown tool {name}"}

    return json.dumps(result, default=str)


def review_transaction(trans_num):
    messages = [{"role": "user", "content": f"Review transaction {trans_num}."}]

    for _ in range(MAX_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": run_tool(block.name, block.input),
                    })
            messages.append({"role": "user", "content": results})
            continue

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"action": "review", "risk": "medium",
                    "reason": f"agent returned unreadable output: {text[:200]}"}

    return {"action": "review", "risk": "medium",
            "reason": "agent did not reach a decision"}