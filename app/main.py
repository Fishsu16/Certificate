from fastapi import FastAPI
from app.api import router as api_router
from app.db import get_db, engine, Base

app = FastAPI(title="Custom CA Certificate Server")

# create table
@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "CA Certificate Server is running."}
