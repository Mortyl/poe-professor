# PoEProfessor Backend

FastAPI backend for PoEProfessor — a Path of Exile 2 companion app.

## Setup

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Copy env file and add your keys
cp .env .env
```

## Running the server

```bash
uvicorn main:app --reload
```

Server runs at http://localhost:8000
API docs available at http://localhost:8000/docs

## API Endpoints

### Leaderboard
- GET /api/leaderboard/leagues — Get all available leagues
- GET /api/leaderboard/{league_id} — Get top 200 players for a league

### Builds
- GET /api/builds/skills — Get list of available skills
- GET /api/builds/ascendancies — Get list of ascendancies
- POST /api/builds/generate — Generate a build guide

## Switching from mock to real data

### Claude API
1. Add your ANTHROPIC_API_KEY to .env
2. Open services/build_service.py
3. Change USE_MOCK = True to USE_MOCK = False

### Path of Exile API
1. Add your POE_CLIENT_ID and POE_CLIENT_SECRET to .env
2. Update services/leaderboard_service.py to use the real API calls
   (commented out code is already there ready to uncomment)
