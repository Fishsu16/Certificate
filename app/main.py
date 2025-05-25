from fastapi import FastAPI
from app.api import router as api_router

app = FastAPI(title="Custom CA Certificate Server")

app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "CA Certificate Server is running."}
