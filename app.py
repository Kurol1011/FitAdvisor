import os
import json
import re
import streamlit as st
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
Составь план тренировок и питания на основе следующего профиля пользователя:
{profile}
Верни результат строго в формате JSON со следующими полями:
summary (строка — краткое описание),
weekly_schedule (список словарей — недельное расписание),
calories_target (целое число — целевая калорийность),
exercises (список объектов вида {{name, sets, reps, notes}} — упражнения, подходы, повторения, примечания).
Не добавляй никакого текста вне JSON.
'''

# --- Интерфейс Streamlit ---
st.set_page_config(page_title="FitAdvisor", layout="centered")
st.title("FitAdvisor — персональный подбор тренировок и питания")

st.markdown("Введите свои данные, и система подберёт индивидуальный план тренировок и питания.")

with st.form("user_form"):
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Возраст", min_value=10, max_value=100, value=25)
        weight = st.number_input("Вес (кг)", min_value=30.0, max_value=200.0, value=70.0)
        height = st.number_input("Рост (см)", min_value=100.0, max_value=220.0, value=175.0)
    with col2:
        sex = st.selectbox("Пол", ["мужской", "женский"])
        activity = st.selectbox("Уровень физической активности", ["низкий", "умеренный", "высокий"])
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
    user = UserInput(
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
        profile_json = json.dumps(user.dict(), ensure_ascii=False, indent=2)
        prompt = PROMPT_TEMPLATE.format(profile=profile_json)

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1200
            )

            text = response.choices[0].message.content.strip()

            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                text = match.group(0)

            plan = None
            try:
                plan = json.loads(text)
            except json.JSONDecodeError:
                fixed = text.replace("'", '"')
                fixed = re.sub(r",\s*([\]}])", r"\1", fixed)
                fixed = re.sub(r"[\n\r\t]", " ", fixed)
                try:
                    plan = json.loads(fixed)
                except Exception:
                    pass

            if not plan:
                st.warning("Не удалось корректно распознать JSON. Отображаю как текст:")
                st.text_area("Ответ модели:", text, height=400)
            else:
                st.success("План успешно сгенерирован!")

                st.subheader("Краткое описание:")
                st.write(plan.get("summary", "Описание отсутствует."))

                st.subheader("План тренировок на неделю:")
                for day in plan.get("weekly_schedule", []):
                    st.markdown(f"**{day.get('day', 'День')}** — {day.get('duration', 'Не указано')} мин")

                st.subheader("Упражнения:")
                for ex in plan.get("exercises", []):
                    st.markdown(f"- {ex.get('name', '')} ({ex.get('sets', '?')} x {ex.get('reps', '?')}) — {ex.get('notes', '')}")

                if "calories_target" in plan:
                    st.subheader(f"Рекомендуемая калорийность: {plan['calories_target']} ккал в день")

        except Exception as e:
            st.error(f"Ошибка при генерации плана: {e}")
