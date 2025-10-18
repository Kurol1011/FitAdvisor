from fastapi import FastAPI
from app.api.v1 import users, plans

app = FastAPI(title='FitAdvisor')

app.include_router(users.router, prefix='/api/v1/users', tags=['users'])
app.include_router(plans.router, prefix='/api/v1/plans', tags=['plans'])

@app.get('/health')
async def health():
    return {'status': 'ok'}