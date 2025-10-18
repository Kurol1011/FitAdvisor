from sqlalchemy import select
from app.db.models import User
from app.db.session import AsyncSession
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_user(db: AsyncSession, payload):
    hashed = pwd_context.hash(payload.password)
    user = User(email=payload.email, hashed_password=hashed, age=payload.age,
                gender=payload.gender, height_cm=payload.height_cm,
                weight_kg=payload.weight_kg, activity_level=payload.activity_level,
                goals=payload.goals, preferences=payload.preferences)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_user_by_email(db: AsyncSession, email: str):
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()