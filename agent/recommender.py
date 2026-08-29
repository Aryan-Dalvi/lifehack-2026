"""Routine planning (deterministic) plus the optional Recommendation Phraser.

The plan itself — which product covers which step, and whether that step is used in
the morning, at night, or both — is built in code from catalog rows and the category
pack. The model only phrases what the plan already decided; it cannot add a product,
reorder a routine, or introduce a fact that is not in the payload it was handed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from agent.interpreter import PACK
from app.settings import settings

logger = logging.getLogger(__name__)

MAX_ROUTINE_STEPS = 4

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sku": {"type": "string"},
                    "advice": {"type": "string"},
                },
                "required": ["sku", "advice"],
            },
        },
    },
    "required": ["summary", "steps"],
}


def _match_score(product: dict[str, Any], skin_types: list[str]) -> tuple[int, float]:
    """Rank candidates for one routine step. Skin-type fit first, then rating."""
    attributes = product.get("attributes") or {}
    product_skin_types = attributes.get("skin_types") or []
    overlap = len({skin.lower() for skin in skin_types} & {skin.lower() for skin in product_skin_types})
    rating = product.get("rating_avg")
    return (overlap, float(rating) if rating is not None else 0.0)


def build_routine(products: list[dict[str, Any]], skin_types: list[str]) -> list[dict[str, Any]]:
    """Pick at most one product per routine step and order it the way the pack says.

    Pure code over validated catalog rows: no model output reaches this function.
    """
    usage: dict[str, Any] = PACK["routine_usage"]
    by_step: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        step = (product.get("attributes") or {}).get("routine_step")
        if step in usage:
            by_step.setdefault(step, []).append(product)

    routine = []
    for step, candidates in by_step.items():
        best = max(candidates, key=lambda product: _match_score(product, skin_types))
        routine.append(
            {
                "step": step,
                "label": usage[step]["label"],
                "order": usage[step]["order"],
                "when": usage[step]["when"],
                "product": best,
                "alternatives": len(candidates) - 1,
            }
        )
    routine.sort(key=lambda entry: entry["order"])
    return routine[:MAX_ROUTINE_STEPS]


def deterministic_recommendation(
    routine: list[dict[str, Any]], skin_types: list[str]
) -> dict[str, Any]:
    """A usable answer with zero model calls.

    Every step still gets usage guidance, taken from the category pack rather than
    invented, so a failed or disabled phrasing call never leaves the shopper without
    an explanation of how to use what they were shown.
    """
    if not routine:
        return {"summary": "I could not build a routine from the catalog for that request.", "steps": []}
    usage: dict[str, Any] = PACK["routine_usage"]
    morning = [entry for entry in routine if "morning" in entry["when"]]
    night = [entry for entry in routine if "night" in entry["when"]]
    profile = " and ".join(skin_types) if skin_types else "your"
    return {
        "summary": (
            f"Here is a routine for {profile} skin from Mysa Skin's catalog: "
            f"{len(morning)} steps in the morning, {len(night)} at night, in the order shown."
        ),
        "steps": [
            {
                "sku": entry["product"]["sku"],
                "advice": usage[entry["step"]]["usage_hint"],
            }
            for entry in routine
            if usage.get(entry["step"], {}).get("usage_hint")
        ],
    }


def phrasing_payload(
    routine: list[dict[str, Any]],
    *,
    message: str,
    skin_types: list[str],
    concerns: list[str],
) -> dict[str, Any]:
    """The only thing the phraser is allowed to see: the decided plan, plus catalog facts."""
    return {
        "shopper": {
            "request": message,
            "skin_types": skin_types,
            "concerns": concerns,
        },
        "routine": [
            {
                "order": entry["order"],
                "step": entry["step"],
                "when": entry["when"],
                "sku": entry["product"]["sku"],
                "title": entry["product"]["title"],
                "texture": (entry["product"].get("attributes") or {}).get("texture"),
                "key_ingredients": ((entry["product"].get("attributes") or {}).get("ingredients") or [])[:3],
                "suits_skin_types": (entry["product"].get("attributes") or {}).get("skin_types") or [],
                "fragrance_free": (entry["product"].get("attributes") or {}).get("fragrance_free"),
            }
            for entry in routine
        ],
    }


async def phrase_routine(
    routine: list[dict[str, Any]],
    *,
    message: str,
    skin_types: list[str],
    concerns: list[str],
) -> tuple[dict[str, Any], str]:
    """One bounded model call that explains an already-decided routine.

    Returns (recommendation, source). Any failure degrades to a deterministic summary
    with no per-step prose — the routine plan itself is unaffected either way.
    """
    deterministic = deterministic_recommendation(routine, skin_types)
    if not routine:
        return deterministic, "deterministic_plan"
    if settings.demo_mode or not settings.openai_api_key:
        return deterministic, "deterministic_plan"

    payload = phrasing_payload(routine, message=message, skin_types=skin_types, concerns=concerns)
    text_options: dict[str, Any] = {
        "format": {
            "type": "json_schema",
            "name": "routine_recommendation",
            "strict": True,
            "schema": RECOMMENDATION_SCHEMA,
        },
    }
    if settings.openai_model.startswith("gpt-5"):
        text_options["verbosity"] = "low"

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=10.0, max_retries=0)
    try:
        response = await client.responses.create(
            model=settings.openai_model,
            instructions=(
                "You are Sway's skincare Recommendation Phraser. You are given a routine that has "
                "ALREADY been decided from a merchant's catalog. Explain it to the shopper: write a "
                "short summary, then one line of practical usage advice per step (when to apply it "
                "and roughly how). Use only the products and facts in the payload. Never mention a "
                "product that is not listed, never invent ingredients, prices or benefits, never "
                "diagnose a condition, and never claim a product treats, cures or heals anything. "
                "Keep the summary under 45 words and each advice line under 30 words."
            ),
            input=json.dumps(payload),
            text=text_options,
            max_output_tokens=700,
            store=False,
        )
        return json.loads(response.output_text), "openai_responses"
    except Exception as error:  # noqa: BLE001 - phrasing is optional; the plan stands without it
        # Never silent: a swallowed failure here is indistinguishable from demo mode.
        logger.warning("Recommendation phrasing failed (%s): %s", type(error).__name__, error)
        return deterministic, "deterministic_failover"
