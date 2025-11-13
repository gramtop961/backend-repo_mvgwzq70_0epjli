"""
Database Schemas for Finance Management System

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date

class Account(BaseModel):
    name: str = Field(..., description="Account name, e.g., BCA, Cash, Ovo")
    type: Literal["cash", "bank", "ewallet"] = Field(..., description="Type of account")
    initial_balance: float = Field(0.0, ge=0, description="Starting balance")
    color: Optional[str] = Field("#6366F1", description="Hex color for UI tag")

class Category(BaseModel):
    name: str = Field(..., description="Category name, e.g., Makan, Gaji")
    type: Literal["income", "expense"] = Field(..., description="Income or Expense")
    color: Optional[str] = Field("#22C55E", description="Hex color for UI tag")

class Transaction(BaseModel):
    date: date = Field(..., description="Transaction date")
    amount: float = Field(..., gt=0, description="Positive amount")
    type: Literal["income", "expense"] = Field(..., description="Income or Expense")
    category_id: str = Field(..., description="Related category id")
    account_id: str = Field(..., description="Related account id")
    note: Optional[str] = Field(None, description="Optional note")

class Budget(BaseModel):
    category_id: str = Field(..., description="Category for the budget")
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")
    amount: float = Field(..., ge=0, description="Budget amount for the month")
