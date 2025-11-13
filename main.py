import os
from datetime import datetime, date
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import db, create_document, get_documents

app = FastAPI(title="Finance Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Schemas (Requests/Responses)
# -----------------------------
class AccountIn(BaseModel):
    name: str = Field(...)
    type: Literal["cash", "bank", "ewallet"]
    initial_balance: float = Field(0, ge=0)
    color: Optional[str] = "#6366F1"

class CategoryIn(BaseModel):
    name: str
    type: Literal["income", "expense"]
    color: Optional[str] = "#22C55E"

class TransactionIn(BaseModel):
    date: date
    amount: float = Field(..., gt=0)
    type: Literal["income", "expense"]
    category_id: str
    account_id: str
    note: Optional[str] = None

class BudgetIn(BaseModel):
    category_id: str
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    amount: float = Field(..., ge=0)

# -----------------------------
# Helpers
# -----------------------------

def serialize(doc: Dict[str, Any]):
    if not doc:
        return doc
    d = dict(doc)
    _id = d.get("_id")
    if _id is not None:
        d["id"] = str(_id)
        del d["_id"]
    # Convert datetime/date to isoformat strings for JSON
    for k, v in list(d.items()):
        if isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    return d


def month_range(month: str):
    # month format YYYY-MM
    start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    # Get next month
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return start, next_month


# -----------------------------
# Base routes
# -----------------------------
@app.get("/")
def root():
    return {"message": "Finance Management System API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                response["collections"] = db.list_collection_names()
                response["connection_status"] = "Connected"
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# -----------------------------
# Accounts
# -----------------------------
@app.get("/api/accounts")
def list_accounts():
    accounts = get_documents("account")
    return [serialize(a) for a in accounts]


@app.post("/api/accounts")
def create_account(payload: AccountIn):
    account_id = create_document("account", payload)
    return {"id": account_id}


# -----------------------------
# Categories
# -----------------------------
@app.get("/api/categories")
def list_categories():
    categories = get_documents("category")
    return [serialize(c) for c in categories]


@app.post("/api/categories")
def create_category(payload: CategoryIn):
    category_id = create_document("category", payload)
    return {"id": category_id}


# -----------------------------
# Transactions
# -----------------------------
@app.get("/api/transactions")
def list_transactions(month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$")):
    txs = get_documents("transaction")
    items = [serialize(t) for t in txs]
    if month:
        start, next_month = month_range(month)
        def in_month(d: str):
            # d is isoformat string
            dd = datetime.fromisoformat(d).date()
            return start <= dd < next_month
        items = [t for t in items if in_month(t["date"])]
    # sort desc by date created_at
    items.sort(key=lambda x: (x.get("date"), x.get("created_at")), reverse=True)
    return items


@app.post("/api/transactions")
def create_transaction(payload: TransactionIn):
    # Basic foreign key existence checks
    from bson import ObjectId
    if not db["account"].find_one({"_id": ObjectId(payload.account_id)}):
        raise HTTPException(status_code=400, detail="Account not found")
    if not db["category"].find_one({"_id": ObjectId(payload.category_id)}):
        raise HTTPException(status_code=400, detail="Category not found")
    tx_id = create_document("transaction", payload)
    return {"id": tx_id}


# -----------------------------
# Budgets
# -----------------------------
@app.get("/api/budgets")
def list_budgets(month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$")):
    budgets = get_documents("budget")
    items = [serialize(b) for b in budgets]
    if month:
        items = [b for b in items if b.get("month") == month]
    return items


@app.post("/api/budgets")
def create_budget(payload: BudgetIn):
    # Ensure category exists and is expense type for budgeting
    from bson import ObjectId
    cat = db["category"].find_one({"_id": ObjectId(payload.category_id)})
    if not cat:
        raise HTTPException(status_code=400, detail="Category not found")
    if cat.get("type") != "expense":
        raise HTTPException(status_code=400, detail="Budget only allowed for expense categories")
    b_id = create_document("budget", payload)
    return {"id": b_id}


# -----------------------------
# Summary and Reports
# -----------------------------
@app.get("/api/summary")
def summary(month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$")):
    accounts = [serialize(a) for a in get_documents("account")]
    categories = [serialize(c) for c in get_documents("category")]
    txs = [serialize(t) for t in get_documents("transaction")]

    if month:
        start, next_month = month_range(month)
        def in_month(d: str):
            dd = datetime.fromisoformat(d).date()
            return start <= dd < next_month
        txs = [t for t in txs if in_month(t["date"])]

    total_income = sum(t["amount"] for t in txs if t["type"] == "income")
    total_expense = sum(t["amount"] for t in txs if t["type"] == "expense")

    # Balance per account = initial + income - expense from all txs (regardless of month for overall balance)
    all_txs = [serialize(t) for t in get_documents("transaction")]
    account_balances = {}
    for acc in accounts:
        acc_id = acc["id"]
        balance = float(acc.get("initial_balance", 0))
        for t in all_txs:
            if t["account_id"] == acc_id:
                if t["type"] == "income":
                    balance += float(t["amount"])
                else:
                    balance -= float(t["amount"])
        account_balances[acc_id] = {
            "name": acc["name"],
            "color": acc.get("color", "#6366F1"),
            "balance": round(balance, 2)
        }

    overall_balance = round(sum(v["balance"] for v in account_balances.values()), 2)

    # Budget status for month
    budgets = [serialize(b) for b in get_documents("budget")]
    budget_status = []
    if month:
        for b in budgets:
            if b["month"] != month:
                continue
            spent = sum(
                t["amount"] for t in txs if t["category_id"] == b["category_id"] and t["type"] == "expense"
            )
            budget_status.append({
                "budget_id": b["id"],
                "category_id": b["category_id"],
                "month": month,
                "amount": b["amount"],
                "spent": round(spent, 2),
                "remaining": round(b["amount"] - spent, 2)
            })

    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "overall_balance": overall_balance,
        "accounts": account_balances,
        "categories": categories,
        "transactions": txs[:50],  # limit to recent 50 for dashboard
        "budgets": budget_status,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
