from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import builds, companion, analyse, tier_list

app = FastAPI(
    title="PoEProfessor API",
    description="Backend API for PoEProfessor - Path of Exile 2 companion app",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(builds.router, prefix="/api/builds", tags=["Builds"])
app.include_router(tier_list.router, prefix="/api/builds", tags=["Builds"])
app.include_router(companion.router)
app.include_router(analyse.router, prefix="/api/analyse", tags=["Analyse"])

@app.get("/")
def root():
    return {"message": "Welcome to PoEProfessor API"}
