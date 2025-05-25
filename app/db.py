from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# 給 FastAPI 用的非同步 Session dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# SQLAlchemy ORM 基底類別
Base = declarative_base()

#Base = declarative_base()

#def get_db():
#    db = SessionLocal()
#    try:
#        yield db
#    finally:
#        db.close()
