from fastapi import FastAPI
from contextlib import asynccontextmanager
from .db.database import engine, Base
from .db.models import Game, Setting

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    print("hello world")

