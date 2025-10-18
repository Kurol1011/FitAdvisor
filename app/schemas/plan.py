from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class PlanOut(BaseModel):
    id: int
    user_id: int
    content: Dict[str, Any]
    active: bool

    class Config:
        orm_mode = True
