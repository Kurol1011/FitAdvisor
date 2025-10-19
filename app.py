import os
import json
import re
import bcrypt
import streamlit as st
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Загрузка окружения ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Настройка базы данных ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://fitadvisor:fitadvisor@localhost:5432/fitadvisor_db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# --- Модель пользователя ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    last_plan = Column(Text, nullable=True)


Base.metadata.create_all(bind=engine)


# --- Модель ввода данных ---
class UserInput(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float
    activity_level: str
    goal: str
    equipment: Optional[List[str]] = []
    diet_preferences: Optional[List[str]] = []


PROMPT_TEMPLATE = '''
Ты — FitAdvisor, интеллектуальный помощник по персонализированным тренировкам и питанию.
Составь персональный план тренировок и питания на основе следующего профиля пользователя:
{profile}

Верни строго JSON следующей структуры (без лишнего текста):

{{
  "summary": "Краткое описание общего подхода",
  "weekly_schedule": [
    {{"day": "Понедельник", "duration": 45, "focus": "Ноги и ягодицы"}},
    {{"day": "Вторник", "duration": 40, "focus": "Грудь и руки"}}
  ],
  "calories_target": 2200,
  "exercises": [
    {{"name": "Приседания", "sets": 3, "reps": 12, "notes": "Можно выполнять с собственным весом"}},
    {{"name": "Отжимания", "sets": 3, "reps": 10, "notes": "С коленей при необходимости"}}
  ]
}}

Не добавляй комментариев, описаний или текста вне JSON.
'''




# --- Работа с пользователями ---
def create_user(username, password):
    session = SessionLocal()
    if session.query(User).filter_by(username=username).first():
        session.close()
        return False, "Такой пользователь уже существует."
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(username=username, password_hash=hashed)
    session.add(user)
    session.commit()
    session.close()
    return True, "Регистрация успешна!"


def authenticate_user(username, password):
    session = SessionLocal()
    user = session.query(User).filter_by(username=username).first()
    if not user:
        session.close()
        return None
    if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        session.close()
        return user
    session.close()
    return None


def save_plan(user_id, plan_json):
    session = SessionLocal()
    user = session.query(User).get(user_id)
    if user:
        user.last_plan = plan_json
        session.commit()
    session.close()


# --- Интерфейс Streamlit ---
st.set_page_config(page_title="FitAdvisor", layout="centered")
st.title("FitAdvisor — персональный подбор тренировок и питания")

if "user" not in st.session_state:
    st.session_state.user = None

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
                st.success(f"Добро пожаловать, {user.username}!")
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
else:
    st.write(f"Вы вошли как **{st.session_state.user['username']}**")
    if st.button("Выйти"):
        st.session_state.user = None
        st.rerun()

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
            ["нет", "гантели", "штанга", "резиновые ленты", "тренажёрный зал"]
        )
        diet = st.multiselect(
            "Предпочтения в питании",
            ["вегетарианство", "высокое содержание белка", "низкоуглеводная диета", "веганство"]
        )

        submitted = st.form_submit_button("Сгенерировать план")

    if submitted:
        user_input = UserInput(
            age=age,
            sex=sex,
            weight_kg=weight,
            height_cm=height,
            activity_level=activity,
            goal=goal,
            equipment=equipment,
            diet_preferences=diet
        )

        with st.spinner("Генерация персонального плана..."):
            profile_json = json.dumps(user_input.dict(), ensure_ascii=False, indent=2)
            prompt = PROMPT_TEMPLATE.format(profile=profile_json)

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )

                text = response.choices[0].message.content.strip()

                # Извлекаем JSON из текста
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    text = match.group(0)

                # Пробуем разобрать JSON
                try:
                    plan = json.loads(text)
                except Exception:
                    plan = text  # оставляем как строку, если JSON невалиден

                if isinstance(plan, dict):
                    st.success("План успешно сгенерирован!")
                    st.subheader("Краткое описание:")
                    st.write(plan.get("summary", "Описание отсутствует."))

                    st.subheader("План тренировок на неделю:")
                    for day in plan.get("weekly_schedule", []):
                        if isinstance(day, dict):
                            st.markdown(f"**{day.get('day', 'День')}** — {day.get('duration', 'Не указано')} мин")

                    st.subheader("Упражнения:")
                    for ex in plan.get("exercises", []):
                        if isinstance(ex, dict):
                            st.markdown(f"- {ex.get('name', '')} ({ex.get('sets', '?')} x {ex.get('reps', '?')}) — {ex.get('notes', '')}")

                    if "calories_target" in plan:
                        st.subheader(f"Рекомендуемая калорийность: {plan['calories_target']} ккал в день")

                    save_plan(st.session_state.user["id"], json.dumps(plan, ensure_ascii=False))
                else:
                    st.warning("Ответ модели не удалось распознать как JSON. Выводим как текст:")
                    st.text(plan)

            except Exception as e:
                st.error(f"Ошибка при генерации плана: {e}")
