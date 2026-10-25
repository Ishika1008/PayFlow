from fastapi import FastAPI

from .database import Base, engine
from . import models  # noqa: F401  (registers the table before create_all)
from .routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PayFlow", version="0.1.0")
app.include_router(router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "PayFlow"}