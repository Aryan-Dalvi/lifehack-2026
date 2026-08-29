from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.settings import settings

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


MEDICAL_TERMS = {
    "diagnose",
    "diagnosis",
    "cure",
    "treat eczema",
    "treat psoriasis",
    "prescription",
    "melanoma",
}


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
    if any(term in text for term in MEDICAL_TERMS):
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
) -> tuple[dict[str, Any], str]:
    if settings.demo_mode or not settings.openai_api_key:
        return (
            deterministic_interpret(
                message=message, merchant_id=merchant_id, visible_skus=visible_skus
            ),
            "deterministic_demo_parser",
        )

    state = {
        "session_id": session_id,
        "message": message,
        "category": "skincare",
        "merchant_ids": [merchant_id],
        "shopper_cap_cents": shopper_cap_cents,
        "visible_skus": visible_skus,
        "profile_preferences": profile,
    }
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=8.0, max_retries=0)
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
                "You are Sway's skincare Commerce Interpreter. Return only the requested structured "
                "decision.\n"
                "Routes: 'search' when the shopper wants to see products matching a need. "
                "'recommend' when they want a routine, an order of use, morning/night guidance, or "
                "advice on which product to use when — set catalog_query so the routine can be built "
                "from real stock, and leave routine_step null so every step of the routine is covered. "
                "'compare' when they want visible products weighed against each other. "
                "'clarify' ONLY when you genuinely cannot act without more information.\n"
                "Prefer acting over asking: if the shopper has given a skin type or a concern, that is "
                "enough to search or recommend. Never ask the same question twice. Never diagnose, "
                "invent products, widen merchant scope, or treat a search budget as payment consent.\n"
                "Set wants_usage_detail true ONLY when the shopper is asking how to use, apply or "
                "order the products (for example 'how do I use these', 'how often', 'walk me "
                "through it'). Asking for a routine alone is not a request for usage detail. "
                "A 'how do I use these' question is route 'recommend' with wants_usage_detail "
                "true — it is NOT 'compare', which is only for weighing products against "
                "each other."
            ),
            input=json.dumps(state),
            text=text_options,
            max_output_tokens=500,
            store=False,
        )
        return json.loads(response.output_text), "openai_responses"
    except Exception:  # noqa: BLE001 - availability fallback covers SDK and transport failures
        return (
            deterministic_interpret(
                message=message, merchant_id=merchant_id, visible_skus=visible_skus
            ),
            "deterministic_failover",
        )
