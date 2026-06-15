# PoEProfessor

**An AI-powered companion app for Path of Exile 2** — a build-guide generator, an interactive
passive-skill-tree visualiser, and a context-aware AI chat companion, all grounded in a curated
knowledge base and real player data so the answers stay accurate in a fast-moving, Early-Access game.

Path of Exile 2 has thousands of interacting mechanics and an overwhelming learning curve.
PoEProfessor lowers that barrier: it explains builds, surfaces the relevant passive nodes, and
answers mechanics questions *in context* — without the confident-but-wrong answers you get from
asking a general-purpose LLM about a game it only half-knows.

---

## Features

- **AI build-guide generator** — turns a class/skill selection into a structured, end-to-end build
  guide (passives, gear priorities, gem links), grounded in current-patch data.
- **Shaper AI chat companion** — a floating assistant that answers PoE2 mechanics and build
  questions using only verified game knowledge, aware of the class/ascendancy you're looking at.
- **Interactive passive skill tree** — a custom-rendered, zoomable/pannable tree that highlights
  the nodes a build actually takes.
- **Archetype browser & leaderboard** — explore popular builds by league-starter vs. endgame,
  backed by statistics scraped from real ladders.
- **Crafting assistant** — PoE2-accurate currency mechanics and step-by-step crafting recipes.
- **Tier list / meta browser** — see what's strong this patch, from real adoption data.

## How it works — grounded AI, not guesswork

The core engineering challenge is **keeping an LLM accurate in a domain that changes every patch**.
PoE2 is in Early Access, and a general model will happily blend in outdated or PoE1 knowledge.
PoEProfessor solves this with a knowledge-grounding layer rather than relying on the model's
training data:

- **Curated knowledge base** — 80+ hand-authored markdown documents covering mechanics, classes,
  ascendancies, weapons and crafting. Every fact is verified against the current patch, so the
  model reasons from a trusted source of truth.
- **Keyword-triggered context injection** — relevant knowledge documents are dynamically selected
  and injected into the prompt at inference time based on the user's query and the active
  class/skill context, so the model only ever sees pertinent, accurate material.
- **Real-data grounding** — a resumable data pipeline scrapes and statistically analyses 20,000+
  real player builds (gem links, passive adoption, gear co-occurrence), and those statistics are
  fed into build generation so recommendations reflect what actually works, not what the model
  imagines.
- **Multi-model orchestration** — Claude **Sonnet** powers the reasoning-heavy chat companion,
  while Claude **Haiku** handles fast, structured build-guide generation — balancing answer
  quality, latency and cost.
- **Anti-hallucination prompting** — system prompts encode explicit PoE2 rules and instruct the
  model to defer ("I don't know") rather than invent node names or mechanics.

## Tech stack

**Frontend** — Next.js 16 (App Router, React 19), TypeScript, Tailwind CSS 4, a custom WebGL
passive-tree renderer built on PIXI.js, NextAuth with Discord & Google OAuth, Drizzle ORM.

**Backend** — Python, FastAPI, the Anthropic Claude API, Pydantic, Redis (caching) and SQLite
(pipeline state), plus a resumable scraping-and-analysis pipeline over public ladder data.

## Architecture

```
Next.js / React frontend  ──►  FastAPI backend  ──►  Anthropic Claude API
  custom PIXI.js tree            knowledge-grounding layer (80+ docs)
  OAuth (Discord/Google)         data pipeline ──► 20k+ analysed builds
```

## Running locally

**Prerequisites:** Node.js 18+, Python 3.11+, and an [Anthropic API key](https://console.anthropic.com/).

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
uvicorn main:app --reload                            # serves http://localhost:8000
```

**Frontend**
```bash
cd frontend
npm install
# add OAuth + auth secrets to .env.local (see frontend/.env.local.example if present)
npm run dev                                           # serves http://localhost:3000
```

## Project structure

```
poe-professor/
├── backend/      FastAPI app, AI routers, knowledge base, data pipeline
│   ├── routers/      build generation, companion chat, analysis, crafting, tier list
│   ├── services/     knowledge-grounding + build logic
│   └── knowledge/    80+ curated PoE2 markdown documents
└── frontend/     Next.js app — build UI, passive-tree canvas, companion, auth
```

---

> Built and maintained solo. A live demo is available on request.
