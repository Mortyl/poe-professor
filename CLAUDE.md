# PoEProfessor — Claude Code Context

## Project Overview
PoEProfessor is a Path of Exile 2 companion web app with AI-powered features. It is inspired by Porofessor.gg (League of Legends companion tool) but built for PoE2.

**Stack:**
- Frontend: Next.js 16 + TypeScript + Tailwind CSS at `frontend/`
- Backend: Python + FastAPI at `backend/`
- AI: Anthropic Claude API (claude-sonnet-4-5)

**Running locally:**
- Backend: `uvicorn main:app --reload` from `backend/` in PyCharm
- Frontend: `npm run dev` from `frontend/` in WebStorm
- Backend runs on `http://localhost:8000`
- Frontend runs on `http://localhost:3000`

---

## Current Folder Structure

```
poe-professor/
  backend/
    knowledge/
      classes/
        warrior.md          ← PoE2 class knowledge (more to be added)
      ascendancies/         ← empty, to be populated
      weapons/              ← empty, to be populated
      mechanics/            ← empty, to be populated
    models/
      schemas.py            ← Pydantic models
    routers/
      builds.py             ← /api/builds/* endpoints
      companion.py          ← /api/companion/chat endpoint
      leaderboard.py        ← /api/leaderboard/* endpoints
    services/
      __init__.py
      build_service.py      ← Claude API build generation
      knowledge_service.py  ← reads knowledge markdown files
      leaderboard_service.py
    main.py
    .env                    ← ANTHROPIC_API_KEY lives here
    requirements.txt
  frontend/
    app/
      components/
        Navbar.tsx
        ShaperCompanion.tsx ← floating AI companion chat widget
        companion.module.css
      builds/
        page.tsx            ← build wizard + guide output
        page.module.css
        components/
          BuildWizard.tsx   ← 4-step build selection wizard
          wizard.module.css
          wizardData.ts     ← static data: classes, ascendancies, weapons, skills
      leaderboard/
        page.tsx
      meta/
        page.tsx
      page.tsx              ← homepage
      page.module.css
      layout.tsx            ← global layout, renders ShaperCompanion globally
      globals.css
    public/
      images/
        companions/
          shaper.jpg        ← Shaper avatar image
        classes/            ← placeholder, awaiting real images
        ascendancies/       ← placeholder, awaiting real images
        weapons/            ← placeholder, awaiting real images
```

---

## Features Built So Far

### 1. Homepage
- Hero section with PoEProfessor branding
- Three feature cards: Leaderboard, Build Guide, Meta Builds
- Dark gold aesthetic (Cinzel/Rajdhani/Share Tech Mono fonts)

### 2. Build Guide Generator (`/builds`)
- 4-step wizard: Class → Ascendancy → Weapon → Skill
- All 8 classes with correct ascendancies
- All weapons listed (bow has real skills, others have mock skills)
- Calls `/api/builds/generate` which calls Claude API
- Displays full build guide: overview, passive tree notes, key skills, gem links, gear priorities, playstyle tips
- "Build Another" button to reset wizard

### 3. Shaper Companion (global, all pages)
- Floating avatar button in bottom-right corner
- Opens chat panel with The Shaper (AI companion)
- Greeting: "Greetings Exile, need assistance?" disappears after first open
- Powered by `/api/companion/chat`
- Markdown rendering via react-markdown (bold text renders in gold)
- Detects class/ascendancy/weapon mentions and loads relevant knowledge
- Chat history persists across page navigation (client-side state)

### 4. Knowledge Base System
- `knowledge_service.py` reads markdown files from `backend/knowledge/`
- Relevant files injected into Claude prompts automatically
- Both build generator and companion use this system
- Currently only `warrior.md` exists — more to be written by Marcus

### 5. Leaderboard (`/leaderboard`)
- Fetches top player data (from leaderboard_service.py)

---

## Key Technical Decisions

### AI Model
- Using `claude-sonnet-4-5`
- System prompts enforce PoE2-only knowledge
- Knowledge base markdown files injected as context
- Plan: migrate to fine-tuned Llama 3 long-term once knowledge base is mature

### Knowledge Base Approach
- Marcus (the developer) is a PoE2 expert and writes the knowledge files
- Files are plain markdown, easy to edit in any text editor
- Knowledge service detects topic from user message and loads relevant file
- No need to restart server when updating knowledge files — read fresh each request

### PoE2-Specific Rules in All Prompts
- No sockets on gear — gems linked in skill menu directly
- One health flask, one mana flask, up to 3 charms
- Spirit resource for auras/persistent skills
- Resistances cap at 75%
- Never reference PoE1 skills (Cyclone, Blade Vortex etc)
- Passive tree nodes described by area/stat type, never invented names

---

## Roadmap

### Phase 1 — Web Companion Chat ✅ COMPLETE
Floating Shaper companion on all pages with Claude-powered chat.

### Phase 2 — Knowledge Base (IN PROGRESS)
- warrior.md written ✅
- All other classes to be written by Marcus
- Ascendancy files, weapon files, mechanics files to follow
- This directly improves both build generator and companion quality

### Phase 3 — Passive Tree Visualisation + PoB Export (NEXT PRIORITY)
**This is critical to the app's usefulness.**
- Get PoE2 passive tree JSON data (check GGG GitHub or Path of Building install)
- Build generator returns list of recommended node IDs alongside build JSON
- Frontend renders zoomed section of passive tree with highlighted nodes (D3.js or Canvas)
- Generate Path of Building export code for direct import
- Check: `https://github.com/grindinggear/skilltree-export` for PoE2 branch
- Check: Path of Building install folder for PoE2 tree JSON data

### Phase 3.5 — Item Crafting Assistant
- User pastes item text (Ctrl+C in PoE2 copies item data)
- Companion reads item, identifies mods, prefix/suffix slots
- Recommends crafting path with reasoning
- Powered by knowledge base crafting mechanics file

### Phase 4 — UI Refining Pass
- Polish all pages to production quality
- Add real class/ascendancy/weapon images (Marcus to provide)
- Fix placeholder icons showing in wizard cards
- Homepage redesign to feature companion selection
- Font and colour system refinement

### Phase 5 — Companion Selection Screen
- Opening screen with avatar picker
- Each companion: name, specialisation, personality, system prompt
- Confirmed companions so far:
  - **Shaper** — default, generalist scholar (avatar created ✅)
  - **Axiom** — saved for future specialist avatar
- Companion choice persists across session

### Phase 6 — Electron Desktop App + Overlay
- Wrap web app in Electron for desktop
- Overlay mode that sits on top of PoE2 while playing
- Hide/show app while keeping companion visible
- Compact mode for playing alongside the game
- Estimated: 3-4 weeks of work

---

## Known Issues / Backlog
- Placeholder icons not showing in wizard cards when images 404 (onError JS fix needed)
- `node_modules/` and `package-lock.json` accidentally created in project root — deleted, but worth noting
- Multiple lockfiles warning in Next.js (root vs frontend) — low priority cleanup
- Mock data in `_get_mock_build()` still references old `playstyle` parameter — harmless since USE_MOCK=False
- Bow skills are real; all other weapon skills are mock data — Marcus to fill in

---

## API Endpoints

### Backend (http://localhost:8000)
- `POST /api/builds/generate` — generate build guide
  - Body: `{ skill, ascendancy, weapon_type, class_name }`
- `POST /api/companion/chat` — Shaper companion chat
  - Body: `{ message, history: [{role, content}] }`
- `GET /api/leaderboard/...` — leaderboard data

### Environment Variables
- `backend/.env` — `ANTHROPIC_API_KEY=your_key_here`
- `frontend/.env.local` — `NEXT_PUBLIC_API_URL=http://localhost:8000`

---

## Developer Notes
- Marcus is a PoE2 expert — his knowledge is the primary source of truth for AI accuracy
- Long-term AI plan: Claude now → fine-tuned Llama 3 once knowledge base is substantial
- PoB (Path of Building) integration is a high priority for build guide credibility
- The app vision is similar to Porofessor.gg but for PoE2 with an AI companion avatar
- Companion avatars are dark fantasy scholar style (see shaper.jpg for reference)
