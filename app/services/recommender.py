from typing import Dict, List
import math
from datetime import date

# ранее были calc_tdee и macro_split — расширим и добавим base_plan

def calc_tdee(weight_kg, height_cm, age, gender, activity_level):
    if gender == 'male':
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    activity_map = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very_active': 1.9,
    }
    return round(bmr * activity_map.get(activity_level, 1.2), 1)

def macro_split(tdee, weight_kg, goal):
    if goal == 'lose_weight':
        calories = max(1200, tdee - 500)
        protein_per_kg = 1.8
    elif goal == 'gain_weight':
        calories = tdee + 300
        protein_per_kg = 2.0
    else:
        calories = tdee
        protein_per_kg = 1.6

    protein_g = round(protein_per_kg * weight_kg, 1)
    fat_g = round((0.25 * calories) / 9, 1)
    carbs_g = round((calories - protein_g * 4 - fat_g * 9) / 4, 1)
    return {'calories': int(calories), 'protein_g': protein_g, 'fat_g': fat_g, 'carb_g': carbs_g}

# небольшой локальный каталог упражнений (можно заменить RAG)
EXERCISES = [
    {"id":"squat", "name":"Приседания", "equipment":["none","barbell","dumbbell"], "muscle":"legs"},
    {"id":"pushup", "name":"Отжимания", "equipment":["none"], "muscle":"chest"},
    {"id":"deadlift", "name":"Становая тяга", "equipment":["barbell","dumbbell"], "muscle":"back"},
    {"id":"row", "name":"Тяга гантели в наклоне", "equipment":["dumbbell"], "muscle":"back"},
    {"id":"plank", "name":"Планка", "equipment":["none"], "muscle":"core"},
    {"id":"lunge", "name":"Выпады", "equipment":["none","dumbbell"], "muscle":"legs"},
    {"id":"overhead_press", "name":"Жим над головой", "equipment":["barbell","dumbbell"], "muscle":"shoulders"},
    {"id":"biceps_curl", "name":"Сгибание на бицепс", "equipment":["dumbbell"], "muscle":"arms"},
]

def choose_exercises(equipment: List[str], goal: str, level: str):
    # простая фильтрация: если equipment пусто -> берем bodyweight-friendly
    chosen = []
    eq_set = set(equipment or [])
    for ex in EXERCISES:
        if 'none' in ex['equipment'] or eq_set.intersection(ex['equipment']):
            chosen.append(ex)
    # сортировать по соответствию цели (простая эвристика)
    if goal == 'lose_weight':
        return chosen  # кардио не включено в этот минимальный набор — можно добавить
    elif goal == 'gain_weight':
        # приоритет базовым многосуставным
        order = ['squat','deadlift','overhead_press','row','lunge','pushup']
        chosen.sort(key=lambda e: order.index(e['id']) if e['id'] in order else 99)
        return chosen
    else:
        return chosen

def make_weekly_schedule(exs, week_index):
    # week_index 0..3 — добавляем прогрессию веса/объёма
    schedule = []
    # простой 3-дневный сплит: full-body или upper/lower
    if len(exs) < 4:
        # full body 3x per week
        days = ['Mon','Wed','Fri']
        for d in days:
            day_plan = {"day": d, "exercises": []}
            for e in exs:
                base_sets = 3
                base_reps = 8 if e['id'] != 'plank' else 30  # seconds
                sets = base_sets + (1 if week_index>0 else 0)
                reps = base_reps + week_index*1
                day_plan["exercises"].append({
                    "id": e['id'],
                    "name": e['name'],
                    "sets": sets,
                    "reps": reps
                })
            schedule.append(day_plan)
    else:
        # 4-week progression with 4 days (upper/lower)
        days = ['Mon','Tue','Thu','Fri']
        for idx, d in enumerate(days):
            day_plan = {"day": d, "exercises": []}
            # choose roughly 4 exercises per day
            exlist = exs[idx::len(days)]
            for e in exlist:
                sets = 3 + (1 if week_index >= 2 else 0)
                reps = 6 + week_index*2
                day_plan["exercises"].append({
                    "id": e['id'],
                    "name": e['name'],
                    "sets": sets,
                    "reps": reps
                })
            schedule.append(day_plan)
    return schedule

def sample_menu_for_day(macros, preferences):
    # очень простой пример: 3 приёма
    calories = macros['calories']
    prot = macros['protein_g']
    carbs = macros['carb_g']
    fats = macros['fat_g']
    return {
        "breakfast": f"Овсянка + белковый источник — ~{int(calories*0.25)} kcal",
        "lunch": f"Белки + овощи + углеводы — ~{int(calories*0.4)} kcal",
        "dinner": f"Лёгкий белок + овощи — ~{int(calories*0.35)} kcal",
        "notes": f"Цель: {calories} kcal; P {prot}g C {carbs}g F {fats}g"
    }

def base_plan(user_profile: Dict) -> Dict:
    """
    Возвращает базовый план (4-недельный) — тренировки + питание + метрики.
    user_profile ожидает: age, gender, weight_kg, height_cm, activity_level, goals: {goal}, equipment list, preferences
    """
    age = user_profile.get('age', 30)
    gender = user_profile.get('gender', 'male')
    weight = user_profile.get('weight_kg', 70)
    height = user_profile.get('height_cm', 175)
    activity = user_profile.get('activity_level', 'moderate')
    goal = (user_profile.get('goals') or {}).get('goal', 'maintain')
    equipment = user_profile.get('equipment') or []
    preferences = user_profile.get('preferences') or {}

    tdee = calc_tdee(weight, height, age, gender, activity)
    macros = macro_split(tdee, weight, goal)
    exercises = choose_exercises(equipment, goal, activity)

    weeks = []
    for w in range(4):
        week = {
            "week": w+1,
            "training": make_weekly_schedule(exercises, w),
            "nutrition": sample_menu_for_day(macros, preferences),
            "notes": f"Неделя {w+1}: лёгкая прогрессия по объёму/повторениям."
        }
        weeks.append(week)

    plan = {
        "generated_at": str(date.today()),
        "profile_summary": {
            "age": age, "gender": gender, "weight_kg": weight, "height_cm": height,
            "activity_level": activity, "goal": goal
        },
        "tdee": tdee,
        "macros": macros,
        "weeks": weeks,
        "exercises_catalog_used_count": len(exercises)
    }
    return plan
