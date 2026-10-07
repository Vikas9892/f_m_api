from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.api.files import router as files_router
from app.db.session import Base, engine
from app.models.file import GeoFile
from app.models.measurement import FeatureMeasurement


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Geospatial File Measurement API",
    version="1.0.0",
    description="Upload KML or zipped Shapefiles and calculate CRS-safe geometry measurements.",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Files",
            "description": "Upload geospatial datasets, extract features, and query calculated measurements.",
        },
        {
            "name": "Health",
            "description": "Service health and liveness checks.",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files_router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}

