import os
import json
import re
import bcrypt
import streamlit as st
import pandas as pd
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Float, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Загружаем переменные окружения
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Настройка базы данных
DB_URL = os.getenv("DATABASE_URL", "postgresql://fitadvisor:fitadvisor@localhost:5432/fitadvisor_db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

from sqlalchemy import text

def ensure_diet_column_exists(engine):
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user_plans' AND column_name = 'diet_recommendations';
            """)
        )
        if not result.fetchone():
            conn.execute(text("ALTER TABLE user_plans ADD COLUMN diet_recommendations TEXT;"))
            conn.commit()
            print("Колонка  добавлена")

# Вызов проверки
ensure_diet_column_exists(engine)


# Проверяем, есть ли колонка diet_recommendations, и добавляем при необходимости
def ensure_diet_column_exists(engine):
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user_plans' AND column_name = 'diet_recommendations';
            """)
        )
        if not result.fetchone():
            print("Добавляю колонку 'diet_recommendations' в таблицу user_plans...")
            conn.execute(text("ALTER TABLE user_plans ADD COLUMN diet_recommendations TEXT;"))
            conn.commit()
            print("Колонка добавлена.")

ensure_diet_column_exists(engine)

# Модели
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    last_plan = Column(Text, nullable=True)

    plans = relationship("UserPlan", back_populates="user", cascade="all, delete-orphan")
    progress = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")


class UserPlan(Base):
    __tablename__ = "user_plans"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    plan_json = Column(Text, nullable=False)
    diet_recommendations = Column(Text, nullable=True)
    user = relationship("User", back_populates="plans")


class UserProgress(Base):
    __tablename__ = "user_progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    weight_kg = Column(Float)
    goal = Column(String(50))
    activity_level = Column(String(50))
    user = relationship("User", back_populates="progress")


# Создаем таблицы
Base.metadata.create_all(bind=engine)

# Модель данных пользователя
class UserInput(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float
    activity_level: str
    goal: str
    equipment: Optional[List[str]] = []
    diet_preferences: Optional[List[str]] = []


# Промпт для GPT
PROMPT_TEMPLATE = '''
Ты — FitAdvisor, интеллектуальный помощник по персонализированным тренировкам и питанию.
Составь персональный план тренировок и питания на основе следующего профиля пользователя:
{profile}

Руководствуйся целью пользователя (похудение, набор массы, поддержание формы) и его диетическими предпочтениями.
Если пользователь указал предпочтения или ограничения — учти их при составлении рациона.

Верни строго JSON следующей структуры (без лишнего текста):

{{
  "summary": "Краткое описание общего подхода",
  "weekly_schedule": [
    {{"day": "Понедельник", "duration": 45, "focus": "Ноги и ягодицы"}}
  ],
  "calories_target": 2200,
  "exercises": [
    {{"name": "Приседания", "sets": 3, "reps": 12, "notes": "Можно выполнять с собственным весом"}}
  ],
  "diet_plan": [
    {{"meal": "Завтрак", "example": "Овсянка с ягодами и орехами"}},
    {{"meal": "Перекус", "example": "Йогурт и горсть орехов"}},
    {{"meal": "Обед", "example": "Куриная грудка, киноа, овощи"}},
    {{"meal": "Ужин", "example": "Запечённая рыба, салат"}},
    {{"meal": "Перед сном", "example": "Творог или протеиновый коктейль"}}
  ]
}}
'''

# Работа с пользователями
def create_user(username, password):
    session = SessionLocal()
    try:
        if session.query(User).filter_by(username=username).first():
            return False, "Такой пользователь уже существует."
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(username=username, password_hash=hashed)
        session.add(user)
        session.commit()
        return True, "Регистрация успешна."
    finally:
        session.close()


def authenticate_user(username, password):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return None
        if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return user
        return None
    finally:
        session.close()


def save_plan_and_progress(user_id, plan_json, user_input: UserInput, diet_text: str = None):
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if user:
            user.last_plan = plan_json
            session.add(UserPlan(
                user_id=user_id,
                plan_json=plan_json,
                diet_recommendations=diet_text
            ))
            session.add(UserProgress(
                user_id=user_id,
                weight_kg=user_input.weight_kg,
                goal=user_input.goal,
                activity_level=user_input.activity_level
            ))
            session.commit()
    finally:
        session.close()


def get_user_history(user_id, limit: int = 10):
    session = SessionLocal()
    try:
        return session.query(UserPlan).filter_by(user_id=user_id).order_by(UserPlan.created_at.desc()).limit(limit).all()
    finally:
        session.close()


def get_user_progress(user_id):
    session = SessionLocal()
    try:
        return session.query(UserProgress).filter_by(user_id=user_id).order_by(UserProgress.created_at.asc()).all()
    finally:
        session.close()


# Генерация простых советов по питанию
def generate_diet_recommendations(goal, diet_preferences):
    base = []
    if goal == "похудение":
        base.append("Сократите калорийность на 10–20% от поддерживающего уровня.")
        base.append("Добавьте больше клетчатки: овощи, зелень, цельнозерновые продукты.")
    elif goal == "набор массы":
        base.append("Увеличьте калорийность на 10–15% от нормы.")
        base.append("Сосредоточьтесь на белках: мясо, рыба, яйца, бобовые.")
    else:
        base.append("Поддерживайте сбалансированное питание и пейте достаточно воды.")

    if "вегетарианство" in diet_preferences:
        base.append("Используйте растительные источники белка: тофу, фасоль, нут, чечевицу.")
    if "веганство" in diet_preferences:
        base.append("Добавьте витамин B12 и больше орехов, семян и бобовых.")
    if "высокое содержание белка" in diet_preferences:
        base.append("Добавляйте белок в каждый приём пищи (20–35 г).")
    if "низкоуглеводная диета" in diet_preferences:
        base.append("Ограничьте сахар и быстрые углеводы, увеличьте количество овощей и белка.")
    return base


# Интерфейс Streamlit
st.set_page_config(page_title="FitAdvisor", layout="centered")
st.title("FitAdvisor — персональный подбор тренировок и питания")

if "user" not in st.session_state:
    st.session_state.user = None

# Авторизация
if not st.session_state.user:
    tab_login, tab_register = st.tabs(["Вход", "Регистрация"])

    with tab_login:
        st.subheader("Вход")
        login_name = st.text_input("Имя пользователя")
        login_pass = st.text_input("Пароль", type="password")
        if st.button("Войти"):
            user = authenticate_user(login_name, login_pass)
            if user:
                st.session_state.user = {"id": user.id, "username": user.username}
                st.success(f"Добро пожаловать, {user.username}.")
                st.rerun()
            else:
                st.error("Неверное имя пользователя или пароль.")

    with tab_register:
        st.subheader("Регистрация")
        reg_name = st.text_input("Имя пользователя", key="reg_name")
        reg_pass = st.text_input("Пароль", type="password", key="reg_pass")
        if st.button("Создать аккаунт"):
            success, msg = create_user(reg_name, reg_pass)
            if success:
                st.success(msg)
            else:
                st.error(msg)

# Основная часть приложения
else:
    st.write(f"Вы вошли как **{st.session_state.user['username']}**")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Выйти"):
            st.session_state.user = None
            st.rerun()
    with col_b:
        show_history = st.button("Посмотреть историю")

    if show_history:
        st.subheader("История планов и прогресса")

        history = get_user_history(st.session_state.user["id"], limit=20)
        if history:
            for p in history:
                st.markdown(f"### {p.created_at.strftime('%d.%m.%Y %H:%M')}")
                st.markdown("План тренировок сохранен.")
                try:
                    plan_obj = json.loads(p.plan_json)
                    summary = plan_obj.get("summary", "")
                    if summary:
                        st.markdown(f"Описание: {summary}")
                    if "calories_target" in plan_obj:
                        st.markdown(f"Калорийность: {plan_obj['calories_target']} ккал/день")
                    if "diet_plan" in plan_obj:
                        st.markdown("Пример рациона:")
                        for meal in plan_obj["diet_plan"]:
                            st.markdown(f"- {meal.get('meal','')}: {meal.get('example','')}")
                except Exception:
                    st.markdown("Не удалось обработать сохраненный план.")

                if p.diet_recommendations:
                    st.markdown("Сохраненные советы по питанию:")
                    st.text(p.diet_recommendations)
                st.markdown("---")
        else:
            st.info("Пока нет сохраненных планов.")

        progress_data = get_user_progress(st.session_state.user["id"])
        if progress_data:
            df = pd.DataFrame([{
                "Дата": p.created_at,
                "Вес (кг)": p.weight_kg,
                "Цель": p.goal,
                "Активность": p.activity_level
            } for p in progress_data])
            st.subheader("Прогресс по весу")
            st.dataframe(df.sort_values("Дата", ascending=False).reset_index(drop=True))
            st.line_chart(df.set_index("Дата")[["Вес (кг)"]])
        else:
            st.info("Пока нет данных о прогрессе.")
        st.stop()

    st.subheader("Создание персонального плана")

    with st.form("user_form"):
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Возраст", min_value=10, max_value=100, value=25)
            weight = st.number_input("Вес (кг)", min_value=30.0, max_value=200.0, value=70.0)
            height = st.number_input("Рост (см)", min_value=100.0, max_value=220.0, value=175.0)
        with col2:
            sex = st.selectbox("Пол", ["мужской", "женский"])
            activity = st.selectbox("Уровень активности", ["низкий", "умеренный", "высокий"])
            goal = st.selectbox("Цель", ["похудение", "набор массы", "поддержание формы"])

        equipment = st.multiselect(
            "Доступное оборудование",
            ["нет", "гантели", "штанга", "резиновые ленты", "тренажерный зал"]
        )
        diet = st.multiselect(
            "Предпочтения в питании",
            ["вегетарианство", "высокое содержание белка", "низкоуглеводная диета", "веганство"]
        )

        submitted = st.form_submit_button("Сгенерировать план")

    if submitted:
        user_input = UserInput(
            age=age, sex=sex, weight_kg=weight, height_cm=height,
            activity_level=activity, goal=goal, equipment=equipment, diet_preferences=diet
        )

        with st.spinner("Генерация персонального плана..."):
            profile_json = json.dumps(user_input.dict(), ensure_ascii=False, indent=2)
            prompt = PROMPT_TEMPLATE.format(profile=profile_json)

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1200
                )

                text = response.choices[0].message.content.strip()
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    text = match.group(0)
                plan = json.loads(text)

                st.subheader("Описание")
                st.write(plan.get("summary", "Описание отсутствует."))

                st.subheader("План тренировок")
                for day in plan.get("weekly_schedule", []):
                    st.markdown(f"{day.get('day', 'День')} — {day.get('duration', '?')} мин ({day.get('focus', '')})")

                st.subheader("Упражнения")
                for ex in plan.get("exercises", []):
                    st.markdown(f"- {ex.get('name', '')} ({ex.get('sets', '?')}x{ex.get('reps', '?')}) — {ex.get('notes', '')}")

                if "calories_target" in plan:
                    st.subheader(f"Рекомендуемая калорийность: {plan['calories_target']} ккал/день")

                if "diet_plan" in plan and isinstance(plan["diet_plan"], list):
                    st.subheader("Пример рациона на день")
                    for meal in plan["diet_plan"]:
                        st.markdown(f"{meal.get('meal', '')}: {meal.get('example', '')}")

                st.subheader("Советы по питанию")
                diet_recs = generate_diet_recommendations(goal, diet)
                for rec in diet_recs:
                    st.markdown(f"- {rec}")

                save_plan_and_progress(
                    st.session_state.user["id"],
                    json.dumps(plan, ensure_ascii=False),
                    user_input,
                    diet_text="\n".join(diet_recs)
                )

            except Exception as e:
                st.error(f"Ошибка при генерации плана: {e}")
