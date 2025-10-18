from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.recommender import base_plan
from app.db.models import User, Plan
from app.schemas.plan import PlanOut
from typing import Dict, Any

router = APIRouter()

@router.post("/generate", response_model=PlanOut)
async def generate_plan(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    payload должен содержать минимально: email (или user_id), age, gender, height_cm, weight_kg,
    activity_level, goals (dict), preferences (dict), equipment (list).
    Если пользователя с таким email нет — создаём запись (упрощённо).
    """
    email = payload.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    res = await db.execute( User.__table__.select().where(User.email == email) )
    user_row = res.first()
    if user_row:
        user_id = user_row[0]
    else:
        new_user = User(
            email=email,
            hashed_password="*",  # placeholder: для demo
            age=payload.get('age'),
            gender=payload.get('gender'),
            height_cm=payload.get('height_cm'),
            weight_kg=payload.get('weight_kg'),
            activity_level=payload.get('activity_level'),
            goals=payload.get('goals'),
            preferences=payload.get('preferences')
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        user_id = new_user.id

    plan_content = base_plan(payload)

    plan = Plan(user_id=user_id, content=plan_content, active=True)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return plan
