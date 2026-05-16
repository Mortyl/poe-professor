from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import anthropic
import os
from services.knowledge_service import build_knowledge_context

router = APIRouter(prefix="/api/companion", tags=["companion"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str


BASE_SYSTEM_PROMPT = """You are The Shaper, a legendary companion and guide in Path of Exile 2. You are ancient, wise, and deeply knowledgeable about all aspects of Wraeclast and the Atlas.

Your personality:
- Speak with gravitas and wisdom, but remain helpful and clear
- Use occasional PoE lore references naturally in conversation
- Address the user as "Exile" occasionally but not every message
- Be concise — give practical answers, not walls of text
- When you are uncertain about specific PoE2 mechanics, say so honestly rather than guessing

Your knowledge covers:
- Path of Exile 2 classes, ascendancies and skills
- Build theory — passive tree, gem links, gear priorities
- Crafting mechanics in PoE2
- Game mechanics — resistances, spirit, stamina, flasks
- General game progression and tips

CRITICAL: You only reference Path of Exile 2. If asked about PoE1 content, clarify the distinction. Never invent specific numbers, node names or mechanics you are not certain about — say you are uncertain instead.

If verified knowledge is provided below, treat it as your primary reference and prioritise it over your training data.

Keep responses to 2-4 sentences unless a detailed explanation is genuinely needed."""


def _extract_context_from_message(message: str) -> dict:
    """
    Attempt to detect which class/ascendancy/weapon the user
    is asking about so we can load relevant knowledge.
    """
    message_lower = message.lower()

    classes = ["warrior", "ranger", "sorceress", "monk", "mercenary", "huntress", "witch", "druid"]
    ascendancies = [
        "titan", "warbringer", "smith of kitava",
        "pathfinder", "deadeye",
        "amazon", "ritualist", "spiritwalker",
        "lich", "infernalist", "bloodmage",
        "stormweaver", "chronomancer", "disciple of varashta",
        "invoker", "acolyte of chayula", "martial artist",
        "gemling legionaire", "witchhunter", "tactician",
        "shaman", "oracle"
    ]
    weapons = ["bow", "mace", "spear", "dagger", "quarterstaff", "axe", "sword", "crossbow", "flail"]

    detected_class = next((c for c in classes if c in message_lower), None)
    detected_ascendancy = next((a for a in ascendancies if a in message_lower), None)
    detected_weapon = next((w for w in weapons if w in message_lower), None)

    return {
        "class_name": detected_class,
        "ascendancy": detected_ascendancy,
        "weapon_type": detected_weapon,
    }


@router.post("/chat", response_model=ChatResponse)
async def companion_chat(request: ChatRequest):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Detect what the user is asking about and load relevant knowledge
    context = _extract_context_from_message(request.message)
    knowledge_context = build_knowledge_context(
        class_name=context["class_name"],
        ascendancy=context["ascendancy"],
        weapon_type=context["weapon_type"],
    )

    # Build system prompt with knowledge appended if available
    system_prompt = BASE_SYSTEM_PROMPT
    if knowledge_context:
        system_prompt += f"\n\n{knowledge_context}"

    # Build message history
    messages = []
    for msg in request.history[-10:]:
        role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system_prompt,
        messages=messages,
    )

    return ChatResponse(response=response.content[0].text)
