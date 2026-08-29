"""The Adviser: answers a skincare question instead of forcing it into a search.

Every other route is transactional — find products, compare them, plan a routine, buy.
A shopper also asks things like "what's the difference between a serum and a moisturiser?"
or "do you sell anything fragrance-free?". Without somewhere for those to land they get
shoehorned into a product search and answered with a spec table, which is what made the
agent feel scripted.

This is the one place a model is allowed to contribute general category knowledge rather
than only phrasing. The trade is bounded on both sides: the model is handed the merchant's
real catalog so it can talk about actual stock, and the Guardian rejects any product,
price or medical claim it did not get from that catalog.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from agent.interpreter import PACK
from app.settings import settings

logger = logging.getLogger(__name__)

MAX_DIGEST_PRODUCTS = 40

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "cited_skus": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "cited_skus"],
}


def catalog_summary(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A compact, fact-only view of the shop. Prices stay in cents so nothing is reworded."""
    summary = []
    for product in products[:MAX_DIGEST_PRODUCTS]:
        attributes = product.get("attributes") or {}
        summary.append(
            {
                "sku": product["sku"],
                "title": product["title"],
                "routine_step": attributes.get("routine_step"),
                "price_cents": product["price_cents"],
                "currency": product.get("currency", "SGD"),
                "skin_types": attributes.get("skin_types") or [],
                "concerns": attributes.get("concerns") or [],
                "ingredients": (attributes.get("ingredients") or [])[:5],
                "fragrance_free": attributes.get("fragrance_free"),
                "texture": attributes.get("texture"),
                "rating_avg": product.get("rating_avg"),
            }
        )
    return summary


def _fallback_answer(products: list[dict[str, Any]]) -> dict[str, Any]:
    """No model available: say what the shop stocks rather than pretending to explain."""
    steps = sorted({(p.get("attributes") or {}).get("routine_step") for p in products} - {None, ""})
    if not steps:
        return {
            "answer": "I can help you find products from this catalog. What is your main skin concern?",
            "cited_skus": [],
        }
    return {
        "answer": (
            "I can help with products from Mysa Skin's catalog — currently "
            f"{', '.join(steps)}. Tell me your skin type or concern and I'll show what fits."
        ),
        "cited_skus": [],
    }


async def answer_question(
    *,
    question: str,
    products: list[dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """One bounded call that answers a skincare or catalog question.

    Returns (answer, source). Failure degrades to a deterministic catalog summary.
    """
    fallback = _fallback_answer(products)
    if settings.demo_mode or not settings.openai_api_key:
        return fallback, "deterministic_plan"

    payload = {
        "question": question,
        "merchant": "Mysa Skin",
        "shopper_profile": profile,
        "catalog": catalog_summary(products),
        "guardrails": PACK["guardrails"],
    }
    text_options: dict[str, Any] = {
        "format": {
            "type": "json_schema",
            "name": "skincare_answer",
            "strict": True,
            "schema": ANSWER_SCHEMA,
        },
    }
    if settings.openai_model.startswith("gpt-5"):
        text_options["verbosity"] = "low"

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=12.0, max_retries=0)
    try:
        response = await client.responses.create(
            model=settings.openai_model,
            instructions=(
                "You are Sway's skincare adviser for the merchant Mysa Skin. Answer the "
                "shopper's question directly and briefly — under 80 words, plain sentences, "
                "no lists or headings.\n"
                "You may explain general skincare concepts (what a product type does, the "
                "order of a routine, what an ingredient is generally used for).\n"
                "For anything about THIS shop — which products exist, their price, "
                "ingredients, or who they suit — use only the catalog in the payload, and put "
                "the SKU of any product you mention in cited_skus. Never invent a product or "
                "an ingredient.\n"
                "NEVER write a price, an amount or a number of cents in the answer text — not "
                "even one from the catalog. If asked what something costs, cite the product "
                "and say its price is shown on the card; the card is displayed beside your "
                "answer and carries the real figure.\n"
                "Never give medical advice. Do not use the words cure, heal, diagnose or "
                "prescribe, and do not name a skin condition such as eczema, psoriasis, "
                "rosacea or dermatitis — write about skin feeling dry, tight or sensitive "
                "instead. These words are rejected outright, so an answer containing one is "
                "thrown away and the shopper gets nothing. If the question is medical, say it "
                "is outside what you can help with and suggest a clinician.\n"
                "If the question is not about skincare or this shop, say only that it is "
                "outside what you help with and offer to help with skincare — do not answer "
                "it, even if you know the answer."
            ),
            input=json.dumps(payload),
            text=text_options,
            max_output_tokens=600,
            store=False,
        )
        return json.loads(response.output_text), "openai_responses"
    except Exception as error:  # noqa: BLE001 - the shop summary still answers something
        logger.warning("Adviser answer failed (%s): %s", type(error).__name__, error)
        return fallback, "deterministic_failover"
