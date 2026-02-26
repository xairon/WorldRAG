"""BlueBox grouping service — Passe 0.5.

Groups consecutive blue_box paragraphs into coherent BlueBox units.
V2 already tags paragraphs with type="blue_box" during ingestion;
this service groups adjacent ones into logical system notification blocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Gap tolerance: blue boxes separated by at most 1 non-blue-box paragraph
# are considered part of the same notification block
_MAX_GAP = 1

# Classification patterns
_LEVEL_PATTERN = re.compile(r"Level.*?(?:→|->|\d+\s*to\s*\d+)", re.IGNORECASE)
_SKILL_PATTERN = re.compile(r"(?:Skill|Ability)\s+(?:Acquired|Learned|Obtained)", re.IGNORECASE)
_TITLE_PATTERN = re.compile(r"Title\s+(?:earned|obtained|acquired)", re.IGNORECASE)
_STAT_PATTERN = re.compile(
    r"[+-]\d+\s+(?:Strength|Agility|Perception|Endurance|Vitality|Toughness|Wisdom|Intelligence|Willpower|Free\s+Points)",
    re.IGNORECASE,
)


@dataclass
class BlueBoxGroup:
    """A grouped blue box from consecutive blue_box paragraphs."""

    paragraph_start: int
    paragraph_end: int
    raw_text: str
    box_type: str = "mixed"
    paragraph_indexes: list[int] = field(default_factory=list)


def _classify_box(text: str) -> str:
    """Classify a blue box by its content."""
    has_level = bool(_LEVEL_PATTERN.search(text))
    has_skill = bool(_SKILL_PATTERN.search(text))
    has_title = bool(_TITLE_PATTERN.search(text))
    has_stat = bool(_STAT_PATTERN.search(text))

    flags = sum([has_level, has_skill, has_title])
    if flags > 1:
        return "mixed"
    if has_level:
        return "level_up"
    if has_skill:
        return "skill_acquisition"
    if has_title:
        return "title"
    if has_stat:
        return "stat_block"
    return "mixed"


def group_blue_boxes(paragraphs: list[dict[str, Any]]) -> list[BlueBoxGroup]:
    """Group consecutive blue_box paragraphs into BlueBox units.

    Args:
        paragraphs: List of paragraph dicts with keys: index, type, text.

    Returns:
        List of BlueBoxGroup with merged text and classification.
    """
    if not paragraphs:
        return []

    # Find blue_box paragraph indexes
    blue_indexes = [p["index"] for p in paragraphs if p.get("type") == "blue_box"]
    if not blue_indexes:
        return []

    # Build index -> paragraph map
    para_map = {p["index"]: p for p in paragraphs}

    # Group with gap tolerance
    groups: list[list[int]] = []
    current_group: list[int] = [blue_indexes[0]]

    for i in range(1, len(blue_indexes)):
        gap = blue_indexes[i] - blue_indexes[i - 1] - 1
        if gap <= _MAX_GAP:
            current_group.append(blue_indexes[i])
        else:
            groups.append(current_group)
            current_group = [blue_indexes[i]]
    groups.append(current_group)

    # Build BlueBoxGroup objects
    result: list[BlueBoxGroup] = []
    for group_indexes in groups:
        texts = [para_map[idx]["text"] for idx in group_indexes if idx in para_map]
        raw_text = "\n".join(texts)
        box = BlueBoxGroup(
            paragraph_start=group_indexes[0],
            paragraph_end=group_indexes[-1],
            raw_text=raw_text,
            box_type=_classify_box(raw_text),
            paragraph_indexes=group_indexes,
        )
        result.append(box)

    logger.info("blue_boxes_grouped", count=len(result))
    return result
