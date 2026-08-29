from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from agent.guardian import is_medical_request
from app.settings import settings

logger = logging.getLogger(__name__)

PACK = json.loads(
    (Path(__file__).with_name("packs") / "skincare.json").read_text(encoding="utf-8")
)


INTERPRETATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "route": {
            "type": "string",
            "enum": [
                "clarify",
                "answer",
                "search",
                "recommend",
                "compare",
                "product_detail",
                "cart",
                "unsupported",
            ],
        },
        "missing_required_fields": {"type": "array", "items": {"type": "string"}},
        "clarification": {"type": ["string", "null"]},
        "catalog_query": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "q": {"type": "string"},
                "merchant_ids": {"type": "array", "items": {"type": "string"}},
                "category": {"type": "string", "enum": ["skincare"]},
                "filters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "routine_step": {"type": ["string", "null"]},
                        "skin_types": {"type": "array", "items": {"type": "string"}},
                        "concerns": {"type": "array", "items": {"type": "string"}},
                        "ingredients": {"type": "array", "items": {"type": "string"}},
                        "excludes": {"type": "array", "items": {"type": "string"}},
                        "fragrance_free": {"type": ["boolean", "null"]},
                    },
                    "required": [
                        "routine_step",
                        "skin_types",
                        "concerns",
                        "ingredients",
                        "excludes",
                        "fragrance_free",
                    ],
                },
                "max_price_cents": {"type": ["integer", "null"], "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": [
                "q",
                "merchant_ids",
                "category",
                "filters",
                "max_price_cents",
                "limit",
            ],
        },
        "selected_skus": {"type": "array", "items": {"type": "string"}},
        "quantity": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
        "wants_usage_detail": {"type": "boolean"},
    },
    "required": [
        "route",
        "missing_required_fields",
        "clarification",
        "catalog_query",
        "selected_skus",
        "quantity",
        "wants_usage_detail",
    ],
}

# Openers that mean the shopper is asking something rather than shopping. Used only by the
# deterministic parser; the live interpreter decides the route from the sentence itself.
QUESTION_OPENERS = (
    "what is",
    "whats",
    "what's",
    "what does",
    "what do you",
    "what are",
    "why ",
    "can i ",
    "can you explain",
    "is it ",
    "are there",
    "do you sell",
    "do you have",
    "difference between",
    "should i ",
)

# Phrasings used ONLY by the deterministic parser below — the offline path, where there is no
# model to reason with. When a model is available it routes from intent and the shop's real
# range instead, so these lists never override it; matching on wording is what made the agent
# feel scripted in the first place.
STOCK_QUESTION_TERMS = (
    "do you have",
    "do you sell",
    "do you stock",
    "do you carry",
    "have you got",
    "is there a",
    "are there any",
    "so no ",
    "you don't have",
    "you dont have",
)

USAGE_DETAIL_TERMS = (
    "how do i use",
    "how to use",
    "how should i use",
    "how do i apply",
    "how to apply",
    "how often",
    "walk me through",
    "explain",
    "instructions",
    "in what order",
)


def _price_filter(text: str) -> int | None:
    match = re.search(r"(?:under|below|less than|max(?:imum)?)[^\d]{0,8}(\d+(?:\.\d{1,2})?)", text)
    return round(float(match.group(1)) * 100) if match else None


def deterministic_interpret(
    *,
    message: str,
    merchant_id: str,
    visible_skus: list[str],
) -> dict[str, Any]:
    text = " ".join(message.lower().strip().split())
    wants_usage_detail = any(term in text for term in USAGE_DETAIL_TERMS)
    if not text:
        return {
            "route": "clarify",
            "missing_required_fields": ["concern_or_routine_step"],
            "clarification": "What would you like help with: a skin concern, a routine step, or a specific product?",
            "catalog_query": None,
            "selected_skus": [],
            "quantity": None,
            "wants_usage_detail": wants_usage_detail,
        }
    if is_medical_request(text):
        return {
            "route": "unsupported",
            "missing_required_fields": [],
            "clarification": (
                "I can compare cosmetic skincare products, but I can’t diagnose or recommend treatment "
                "for a medical condition. A qualified clinician can help with that safely."
            ),
            "catalog_query": None,
            "selected_skus": [],
            "quantity": None,
            "wants_usage_detail": wants_usage_detail,
        }
    asks_a_question = any(text.startswith(opener) for opener in QUESTION_OPENERS) or any(
        term in text for term in STOCK_QUESTION_TERMS
    )
    if asks_a_question and not wants_usage_detail:
        return {
            "route": "answer",
            "missing_required_fields": [],
            "clarification": None,
            "catalog_query": None,
            "selected_skus": [],
            "quantity": None,
            "wants_usage_detail": wants_usage_detail,
        }
    if "compare" in text and len(visible_skus) >= 2:
        selected = [sku for sku in visible_skus if sku.lower() in text]
        return {
            "route": "compare",
            "missing_required_fields": [],
            "clarification": None,
            "catalog_query": None,
            "selected_skus": selected or visible_skus[:3],
            "quantity": None,
            "wants_usage_detail": wants_usage_detail,
        }

    routine_steps = {
        "cleanser": ("cleanser", "cleanser"),
        "wash": ("cleanser", "cleanser"),
        "moisturiser": ("moisturiser", "moisturiser"),
        "moisturizer": ("moisturiser", "moisturiser"),
        "serum": ("serum", "serum"),
        "sunscreen": ("sunscreen", "sunscreen"),
        "spf": ("sunscreen", "sunscreen"),
    }
    routine_step = next((value[0] for key, value in routine_steps.items() if key in text), None)
    skin_types = [
        skin_type
        for skin_type in ("dry", "oily", "combination", "normal", "sensitive")
        if skin_type in text
    ]
    concern_aliases = {
        "dryness": ["dry", "dehydrated", "dryness"],
        "barrier support": ["barrier", "irritated"],
        "redness": ["redness", "red"],
        "congestion": ["acne", "breakout", "congestion", "clogged"],
        "oiliness": ["oily", "oiliness"],
        "dullness": ["dull", "brighten", "dullness"],
        "sun protection": ["spf", "sunscreen", "sun protection"],
    }
    concerns = [
        concern for concern, aliases in concern_aliases.items() if any(alias in text for alias in aliases)
    ]
    fragrance_free = True if any(term in text for term in ("fragrance free", "sensitive", "no fragrance")) else None
    if not routine_step and not concerns and not skin_types and text in {"help", "not sure", "recommend", "products"}:
        return {
            "route": "clarify",
            "missing_required_fields": ["concern_or_routine_step"],
            "clarification": "What is your main concern right now—dryness, sensitivity, breakouts, or something else?",
            "catalog_query": None,
            "selected_skus": [],
            "quantity": None,
            "wants_usage_detail": wants_usage_detail,
        }
    wants_routine = any(
        term in text
        for term in (
            "routine",
            "morning",
            "night",
            "evening",
            "am and pm",
            "step",
            "steps",
            "order",
            "when do i",
            "when should i",
            "how do i use",
            "how should i use",
            "which one should i use",
        )
    )
    # A routine has to span every step, so a single-step filter cannot apply to it.
    if wants_routine:
        routine_step = None
    search_terms = [routine_step or "", *concerns, *skin_types]
    return {
        "route": "recommend" if wants_routine else "search",
        "missing_required_fields": [],
        "clarification": None,
        "catalog_query": {
            "q": " ".join(term for term in search_terms if term) or text,
            "merchant_ids": [merchant_id],
            "category": "skincare",
            "filters": {
                "routine_step": routine_step,
                "skin_types": skin_types,
                "concerns": concerns,
                "ingredients": [],
                "excludes": ["fragrance"] if fragrance_free else [],
                "fragrance_free": fragrance_free,
            },
            "max_price_cents": _price_filter(text),
            "limit": 5,
        },
        "selected_skus": [],
        "quantity": None,
        "wants_usage_detail": wants_usage_detail,
    }


async def interpret(
    *,
    session_id: str,
    message: str,
    merchant_id: str,
    visible_skus: list[str],
    profile: dict[str, Any],
    shopper_cap_cents: int | None,
    catalog: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str]:
    if settings.demo_mode or not settings.openai_api_key:
        return (
            deterministic_interpret(
                message=message, merchant_id=merchant_id, visible_skus=visible_skus
            ),
            "deterministic_demo_parser",
        )

    # The medical boundary is decided in code, never by the model. Asked about a condition
    # the model declines but routes to 'clarify' or 'search', which renders as an ordinary
    # follow-up (or an empty catalog result) instead of the safety boundary. Checking here
    # keeps the refusal identical whether or not a model is in the loop.
    if is_medical_request(message):
        return (
            deterministic_interpret(
                message=message, merchant_id=merchant_id, visible_skus=visible_skus
            ),
            "deterministic_safety_guard",
        )

    state = {
        "session_id": session_id,
        "message": message,
        "category": "skincare",
        "merchant_ids": [merchant_id],
        "shopper_cap_cents": shopper_cap_cents,
        "visible_skus": visible_skus,
        "profile_preferences": profile,
        # What the shop actually sells. Without this the router is guessing: asked for an
        # eye cream it would route to 'search' and the fuzzy matcher would answer with a
        # moisturiser. Knowing the range, it can tell a stocked request from an absent one.
        "shop_sells": [
            {
                "sku": product["sku"],
                "title": product["title"],
                "routine_step": (product.get("attributes") or {}).get("routine_step"),
            }
            for product in (catalog or [])
        ],
    }
    # One retry: transient APIConnectionError is common on venue wifi and fails fast,
    # so a retry costs far less than silently degrading to the canned parser.
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=8.0, max_retries=1)
    text_options: dict[str, Any] = {
        "format": {
            "type": "json_schema",
            "name": "commerce_interpretation",
            "strict": True,
            "schema": INTERPRETATION_SCHEMA,
        },
    }
    if settings.openai_model.startswith("gpt-5"):
        text_options["verbosity"] = "low"
    try:
        response = await client.responses.create(
            model=settings.openai_model,
            instructions=(
                "You are the shop assistant for a skincare merchant. Decide what the shopper "
                "wants, the way a good assistant on the shop floor would. `shop_sells` is the "
                "merchant's entire range — read it before deciding.\n"
                "\n"
                "Pick the route by what the shopper is trying to do:\n"
                "- answer: they asked a question and want it answered in words. Covers "
                "questions about skincare in general, about an ingredient, and about this "
                "shop — including whether something is stocked. If the thing they asked for "
                "is NOT in shop_sells, always use answer, never search: searching would show "
                "them the nearest product as though it were the one they asked for.\n"
                "- search: they want to be shown products that fit a need.\n"
                "- recommend: they want a routine, an order of use, or morning/night guidance. "
                "Set catalog_query and leave routine_step null so every step is covered.\n"
                "- compare: they want products they can already see weighed against each other.\n"
                "- product_detail: they asked about one particular product.\n"
                "- clarify: only when you genuinely cannot act without more information.\n"
                "- unsupported: not about skincare or this shop.\n"
                "\n"
                "Judge intent, not wording — the same question arrives phrased a hundred ways. "
                "Prefer acting over asking: a stated skin type or concern is enough to work "
                "with. Do not ask something the shopper already answered.\n"
                "\n"
                "wants_usage_detail is true only when they are asking how to apply or how "
                "often to use something. Wanting a routine is not the same as wanting "
                "application instructions.\n"
                "\n"
                "Never invent a product that is not in shop_sells, never widen beyond this "
                "merchant, never diagnose, and never treat a budget as permission to buy."
            ),
            input=json.dumps(state),
            text=text_options,
            max_output_tokens=500,
            store=False,
        )
        return json.loads(response.output_text), "openai_responses"
    except Exception as error:  # noqa: BLE001 - availability fallback covers SDK and transport failures
        # Never silent: a swallowed failure here is indistinguishable from demo mode.
        logger.warning("Interpretation failed (%s): %s", type(error).__name__, error)
        return (
            deterministic_interpret(
                message=message, merchant_id=merchant_id, visible_skus=visible_skus
            ),
            "deterministic_failover",
        )
