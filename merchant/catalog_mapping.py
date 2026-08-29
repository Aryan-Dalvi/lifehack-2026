"""Column mapping: which spreadsheet column is which catalog field.

Mapping is deterministic. Headers are matched against a fixed alias table, and the template
in `catalog_template` ships those exact headers - so a file filled in from the template maps
perfectly with no model call, no latency and no cost. A header the table does not know is
reported to the merchant as ignored rather than guessed at, and two headers competing for one
field stop the upload for correction.

The model is still used where judgement genuinely helps - screening product data for faults,
explaining what went wrong, matching photo filenames - just not here.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

from merchant.catalog_cleaner import normalize_key

MAPPING_VERSION = "catalog-mapping.v2"
MAX_SAMPLE_VALUES = 3
MAX_SAMPLE_CHARS = 120

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "item_code", "product_id", "article_no", "product_code"),
    "title": ("title", "name", "product_name"),
    "description": ("description", "details", "product_description"),
    "price_cents": ("price_cents",),
    "price": ("price", "price_sgd", "unit_price", "retail_price", "rrp"),
    "currency": ("currency", "currency_code"),
    "stock": ("stock", "inventory", "quantity", "qty", "on_hand"),
    "ingredients": ("ingredients", "ingredient_list", "inci", "full_inci"),
    "image_url": ("image_url", "image", "photo", "product_image"),
    "rating_avg": ("rating_avg", "rating", "average_rating"),
    "rating_count": ("rating_count", "reviews", "review_count"),
    "size_ml": ("size_ml", "volume_ml"),
    "fragrance_free": ("fragrance_free",),
    "excludes": ("excludes", "free_from"),
    "texture": ("texture", "formulation"),
}

# Facts no model may author. It never sees these columns' values at all.
MODEL_EXCLUDED_TARGETS = {
    "sku",
    "price_cents",
    "price",
    "currency",
    "stock",
    "image_url",
    "rating_avg",
    "rating_count",
}

# Descriptive columns the classifier may read, by normalised header name.
MODEL_DESCRIPTIVE_FIELDS = {
    "title",
    "name",
    "product_name",
    "description",
    "short_description",
    "long_description",
    "details",
    "product_details",
    "product_description",
    "benefits",
    "key_benefits",
    "features",
    "product_features",
    "tags",
    "category",
    "subcategory",
    "product_type",
    "item_type",
    "type",
    "routine_step",
    "skin_type",
    "skin_types",
    "suitable_for",
    "skin_suitability",
    "concern",
    "concerns",
    "skin_concern",
    "skin_concerns",
    "ingredients",
    "ingredient_list",
    "active_ingredients",
    "key_ingredients",
    "inci",
    "fragrance_free",
    "excludes",
    "free_from",
    "texture",
    "formulation",
    "finish",
    "scent",
    "usage_time",
    "when_to_use",
    "directions",
    "how_to_use",
    "claims",
}


@dataclass(frozen=True)
class MappingCandidates:
    """What alias matching could and could not settle."""

    headers: list[str]
    samples: dict[str, list[str]]
    resolved: dict[str, str]
    conflicts: dict[str, list[str]]
    unmapped: list[str]


@dataclass(frozen=True)
class MappingResolution:
    mappings: dict[str, str]
    decisions: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    ignored_columns: list[str]
    source: str

    def report(self) -> dict[str, Any]:
        return {
            "version": MAPPING_VERSION,
            "source": self.source,
            "mappings": self.mappings,
            "decisions": self.decisions,
            "unresolved": self.unresolved,
            "ignored_columns": self.ignored_columns,
        }


def _sample_text(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())[:MAX_SAMPLE_CHARS]


def detect_mappings(rows: list[Any]) -> MappingCandidates:
    """Alias-match headers to catalog fields, recording ties instead of raising on them."""
    headers: list[str] = []
    seen: set[str] = set()
    samples: dict[str, list[str]] = {}
    for row in rows:
        for header, value in row.values.items():
            if header not in seen:
                seen.add(header)
                headers.append(header)
                samples[header] = []
            if value not in (None, "") and len(samples[header]) < MAX_SAMPLE_VALUES:
                text = _sample_text(value)
                if text:
                    samples[header].append(text)

    normalized = {normalize_key(header): header for header in headers}
    resolved: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    claimed: set[str] = set()
    for target, aliases in FIELD_ALIASES.items():
        matches = [normalized[alias] for alias in aliases if alias in normalized]
        if len(matches) > 1:
            conflicts[target] = matches
            claimed.update(matches)
        elif matches:
            resolved[target] = matches[0]
            claimed.add(matches[0])
    return MappingCandidates(
        headers=headers,
        samples=samples,
        resolved=resolved,
        conflicts=conflicts,
        unmapped=[header for header in headers if header not in claimed],
    )


def resolve_mappings(candidates: MappingCandidates) -> MappingResolution:
    """Turn alias matches into the mapping the pipeline uses, and say what was ignored."""
    decisions = [
        {
            "target": target,
            "column": column,
            "method": "exact_alias",
            "reason": "The header matched a known name for this field.",
        }
        for target, column in sorted(candidates.resolved.items())
    ]
    # A column that is neither a known field nor recognised evidence is not an error - a
    # merchant's own internal columns are welcome in the file - but they should be told it
    # was skipped rather than left wondering why it had no effect.
    ignored = [
        header
        for header in candidates.unmapped
        if normalize_key(header) not in MODEL_DESCRIPTIVE_FIELDS
    ]
    unresolved = [
        {
            "target": target,
            "candidate_columns": columns,
            "reason": "Two columns could both be this field.",
        }
        for target, columns in sorted(candidates.conflicts.items())
    ]
    return MappingResolution(
        mappings=dict(candidates.resolved),
        decisions=decisions,
        unresolved=unresolved,
        ignored_columns=ignored,
        source="deterministic_alias_table",
    )
