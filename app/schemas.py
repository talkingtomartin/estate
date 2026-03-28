from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PropertyCreate(BaseModel):
    name: str
    address: Optional[str] = None


class TransactionCreate(BaseModel):
    type: str           # "income" or "expense"
    description: str
    amount: float
    date: date
    category: Optional[str] = None
    is_recurring: bool = False
    notes: Optional[str] = None
