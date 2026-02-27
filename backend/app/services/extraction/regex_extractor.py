"""Passe 0 — Regex-based pre-extraction for LitRPG blue boxes and system notifications.

Extracts structured data (skills, levels, classes, titles, stats) from
semi-structured blue box text patterns common in LitRPG novels.

This pass is:
- FREE ($0 — no LLM calls)
- FAST (instant regex matching)
- HIGH CONFIDENCE (~95% on well-formatted blue boxes)
- GROUNDED (exact character offsets for source tracking)

Results feed into LLM Passes 1-4 as context to improve extraction quality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml

from app.core.logging import get_logger
from app.schemas.book import RegexMatch

if TYPE_CHECKING:
    from app.core.ontology_loader import OntologyLoader

logger = get_logger(__name__)


@dataclass
class RegexPattern:
    """A compiled regex pattern for entity extraction."""

    name: str
    pattern: re.Pattern[str]
    entity_type: str
    captures: dict[str, int]  # capture_name → group_index


@dataclass
class RegexExtractor:
    """Regex-based extractor for LitRPG system notifications.

    Loads patterns from ontology YAML files and applies them
    to chapter text to extract structured entities.
    """

    patterns: list[RegexPattern] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> RegexExtractor:
        """Load regex patterns from an ontology YAML file.

        Args:
            yaml_path: Path to the YAML file containing regex_patterns section.

        Returns:
            RegexExtractor with compiled patterns.
        """
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        patterns: list[RegexPattern] = []
        regex_section = data.get("regex_patterns", {})

        for name, spec in regex_section.items():
            try:
                compiled = re.compile(spec["pattern"], re.MULTILINE | re.IGNORECASE)
                patterns.append(
                    RegexPattern(
                        name=name,
                        pattern=compiled,
                        entity_type=spec["entity_type"],
                        captures=spec.get("captures", {}),
                    )
                )
            except re.error as e:
                logger.warning("regex_compile_failed", pattern_name=name, error=str(e))

        logger.info("regex_patterns_loaded", count=len(patterns), source=yaml_path)
        return cls(patterns=patterns)

    @classmethod
    def from_ontology(cls, ontology: OntologyLoader) -> RegexExtractor:
        """Create a RegexExtractor from ontology YAML patterns.

        Loads all regex patterns from active ontology layers via OntologyLoader,
        replacing the need to manually specify YAML paths or use hardcoded defaults.

        Args:
            ontology: Loaded OntologyLoader instance with regex patterns.

        Returns:
            RegexExtractor with compiled patterns from all active layers.
        """
        patterns: list[RegexPattern] = []
        for spec in ontology.get_regex_patterns_list():
            try:
                compiled = re.compile(spec["pattern"], re.IGNORECASE | re.MULTILINE)
                patterns.append(
                    RegexPattern(
                        name=spec["name"],
                        pattern=compiled,
                        entity_type=spec["entity_type"],
                        captures=spec["captures"],
                    )
                )
            except re.error as e:
                logger.warning(
                    "regex_compile_failed",
                    pattern_name=spec.get("name", "unknown"),
                    error=type(e).__name__,
                )

        logger.info(
            "regex_patterns_loaded",
            count=len(patterns),
            source="ontology",
            layers=ontology.layers_loaded,
        )
        return cls(patterns=patterns)

    @classmethod
    def default(cls) -> RegexExtractor:
        """Create extractor with hardcoded default patterns.

        Fallback if YAML loading fails. Covers the most common LitRPG patterns.
        """
        patterns = [
            RegexPattern(
                name="skill_acquired",
                pattern=re.compile(
                    r"\[(?:Skill|Ability)\s+(?:Acquired|Learned|Gained):\s*(.+?)(?:\s*-\s*(.+?))?\]",
                    re.IGNORECASE,
                ),
                entity_type="Skill",
                captures={"name": 1, "rank": 2},
            ),
            RegexPattern(
                name="level_up",
                pattern=re.compile(
                    r"Level:\s*(\d+)\s*(?:→|->|=>)\s*(\d+)",
                    re.IGNORECASE,
                ),
                entity_type="Level",
                captures={"old_value": 1, "new_value": 2},
            ),
            RegexPattern(
                name="class_obtained",
                pattern=re.compile(
                    r"Class:\s*(.+?)\s*\((.+?)\)",
                    re.IGNORECASE,
                ),
                entity_type="Class",
                captures={"name": 1, "tier_info": 2},
            ),
            RegexPattern(
                name="title_earned",
                pattern=re.compile(
                    r"Title\s+(?:earned|obtained|acquired):\s*(.+?)(?:\n|$)",
                    re.IGNORECASE,
                ),
                entity_type="Title",
                captures={"name": 1},
            ),
            RegexPattern(
                name="stat_increase",
                pattern=re.compile(
                    r"\+(\d+)\s+(Strength|Agility|Endurance|Vitality|Toughness|Wisdom|Intelligence|Perception|Willpower|Charisma)",
                    re.IGNORECASE,
                ),
                entity_type="StatIncrease",
                captures={"value": 1, "stat_name": 2},
            ),
            RegexPattern(
                name="evolution",
                pattern=re.compile(
                    r"(?:Evolution|Upgrade|Breakthrough).*?(?:→|->|=>)\s*(.+?)(?:\n|$)",
                    re.IGNORECASE,
                ),
                entity_type="Evolution",
                captures={"target": 1},
            ),
            # Layer 3: Primal Hunter series-specific
            RegexPattern(
                name="bloodline_notification",
                pattern=re.compile(
                    r"\[Bloodline\s+(?:Awakened|Evolved|Activated):\s*(.+?)\]",
                    re.IGNORECASE,
                ),
                entity_type="Bloodline",
                captures={"name": 1},
            ),
            RegexPattern(
                name="profession_obtained",
                pattern=re.compile(
                    r"Profession\s+(?:Obtained|Acquired|Gained):\s*(.+?)\s*(?:\((.+?)\))?$",
                    re.IGNORECASE | re.MULTILINE,
                ),
                entity_type="Profession",
                captures={"name": 1, "tier_info": 2},
            ),
            RegexPattern(
                name="blessing_received",
                pattern=re.compile(
                    r"\[Blessing\s+(?:of|from)\s+(.+?)(?:\s+received|\])",
                    re.IGNORECASE,
                ),
                entity_type="Church",
                captures={"name": 1},
            ),
            RegexPattern(
                name="blue_box_generic",
                pattern=re.compile(
                    r"\[([^\[\]]{5,200})\]",
                ),
                entity_type="SystemNotification",
                captures={"content": 1},
            ),
        ]
        return cls(patterns=patterns)

    def extract(self, text: str, chapter_number: int) -> list[RegexMatch]:
        """Extract all regex matches from chapter text.

        Args:
            text: Full chapter text.
            chapter_number: Chapter number for metadata.

        Returns:
            List of RegexMatch objects with grounding offsets.
        """
        matches: list[RegexMatch] = []
        seen_spans: set[tuple[int, int]] = set()  # deduplicate overlapping matches

        # Apply specific patterns first (skill, level, class, title)
        # then generic blue_box last (to avoid duplicates)
        specific = [p for p in self.patterns if p.name != "blue_box_generic"]
        generic = [p for p in self.patterns if p.name == "blue_box_generic"]

        for pattern in [*specific, *generic]:
            for match in pattern.pattern.finditer(text):
                span = (match.start(), match.end())

                # Skip if this span overlaps with an already-captured specific match
                if pattern.name == "blue_box_generic" and any(
                    s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1] for s in seen_spans
                ):
                    continue

                seen_spans.add(span)

                # Extract named captures
                captures: dict[str, str] = {}
                for capture_name, group_idx in pattern.captures.items():
                    try:
                        value = match.group(group_idx)
                        if value:
                            captures[capture_name] = value.strip()
                    except IndexError:
                        pass

                matches.append(
                    RegexMatch(
                        pattern_name=pattern.name,
                        entity_type=pattern.entity_type,
                        captures=captures,
                        raw_text=match.group(0),
                        char_offset_start=match.start(),
                        char_offset_end=match.end(),
                        chapter_number=chapter_number,
                    )
                )

        logger.info(
            "regex_extraction_completed",
            chapter=chapter_number,
            total_matches=len(matches),
            by_type={
                t: sum(1 for m in matches if m.entity_type == t)
                for t in {m.entity_type for m in matches}
            },
        )
        return matches
