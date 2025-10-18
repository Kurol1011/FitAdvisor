from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    email: str
    password: str
    age: Optional[int]
    gender: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    activity_level: Optional[str]
    goals: Optional[dict]
    preferences: Optional[dict]

class UserOut(BaseModel):
    id: int
    email: str
    age: Optional[int]
    class Config:
        orm_mode = True