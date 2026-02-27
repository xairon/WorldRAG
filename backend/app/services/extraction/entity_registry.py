"""EntityRegistry — growing context for chapter-by-chapter extraction.

Accumulates known entities, aliases, and chapter summaries.
Injected into LLM prompts as context for better disambiguation.
Serializable to dict for Neo4j persistence and cross-book sharing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RegistryEntry:
    """A known entity in the registry."""

    canonical_name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    significance: str = ""
    first_seen_chapter: int | None = None
    last_seen_chapter: int | None = None
    description: str = ""


class EntityRegistry:
    """Growing registry of known entities, maintained per book.

    Used to inject context into extraction prompts so later chapters
    benefit from entities already discovered in earlier chapters.
    """

    def __init__(self) -> None:
        self._entities: dict[str, RegistryEntry] = {}  # canonical key -> entry
        self._alias_map: dict[str, str] = {}  # lowercase alias -> canonical key
        self.chapter_summaries: list[str] = []

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def alias_count(self) -> int:
        return len(self._alias_map)

    def add(
        self,
        name: str,
        entity_type: str,
        aliases: list[str] | None = None,
        significance: str = "",
        first_seen_chapter: int | None = None,
        description: str = "",
    ) -> None:
        """Add or update an entity in the registry."""
        canonical = name.lower().strip()
        existing = self._entities.get(canonical)
        if existing:
            # Update: add new aliases, update last_seen
            for alias in aliases or []:
                alias_key = alias.lower().strip()
                if alias_key not in self._alias_map:
                    existing.aliases.append(alias)
                    self._alias_map[alias_key] = canonical
            if significance:
                existing.significance = significance
            if description:
                existing.description = description
            return

        entry = RegistryEntry(
            canonical_name=canonical,
            entity_type=entity_type,
            aliases=list(aliases or []),
            significance=significance,
            first_seen_chapter=first_seen_chapter,
            description=description,
        )
        self._entities[canonical] = entry
        for alias in aliases or []:
            self._alias_map[alias.lower().strip()] = canonical

    def lookup(self, name: str) -> RegistryEntry | None:
        """Look up an entity by name or alias (case-insensitive)."""
        key = name.lower().strip()
        if key in self._entities:
            return self._entities[key]
        canonical = self._alias_map.get(key)
        if canonical:
            return self._entities.get(canonical)
        return None

    def update_last_seen(self, name: str, chapter: int) -> None:
        """Update the last_seen_chapter for an entity."""
        entry = self.lookup(name)
        if entry:
            entry.last_seen_chapter = chapter

    def add_chapter_summary(self, chapter_number: int, summary: str) -> None:
        """Add a summary for a chapter (1-indexed)."""
        while len(self.chapter_summaries) < chapter_number:
            self.chapter_summaries.append("")
        self.chapter_summaries[chapter_number - 1] = summary

    def to_prompt_context(self, max_tokens: int = 2000) -> str:
        """Serialize registry to a string for injection into LLM prompts.

        Prioritizes entities by significance and recency.
        Caps output at approximately max_tokens words.
        """
        lines: list[str] = []
        token_estimate = 0

        # Sort: protagonists first, then by last_seen (most recent first)
        sorted_entries = sorted(
            self._entities.values(),
            key=lambda e: (
                e.significance == "protagonist",
                e.significance == "major",
                e.last_seen_chapter or 0,
            ),
            reverse=True,
        )

        for entry in sorted_entries:
            parts = [f"- {entry.canonical_name} ({entry.entity_type})"]
            if entry.aliases:
                parts.append(f"[aliases: {', '.join(entry.aliases)}]")
            if entry.description:
                # Truncate long descriptions
                desc = entry.description[:100]
                parts.append(f"— {desc}")
            line = " ".join(parts)
            words = len(line.split())
            if token_estimate + words > max_tokens:
                break
            lines.append(line)
            token_estimate += words

        return "\n".join(lines)

    def get_all_names(self) -> set[str]:
        """Get all known names and aliases."""
        names: set[str] = set()
        for entry in self._entities.values():
            names.add(entry.canonical_name)
            for alias in entry.aliases:
                names.add(alias.lower().strip())
        return names

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "entities": {
                k: {
                    "canonical_name": v.canonical_name,
                    "entity_type": v.entity_type,
                    "aliases": v.aliases,
                    "significance": v.significance,
                    "first_seen_chapter": v.first_seen_chapter,
                    "last_seen_chapter": v.last_seen_chapter,
                    "description": v.description,
                }
                for k, v in self._entities.items()
            },
            "alias_map": dict(self._alias_map),
            "chapter_summaries": self.chapter_summaries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EntityRegistry:
        """Deserialize from dict."""
        reg = cls()
        for val in data.get("entities", {}).values():
            reg.add(
                name=val["canonical_name"],
                entity_type=val["entity_type"],
                aliases=val.get("aliases", []),
                significance=val.get("significance", ""),
                first_seen_chapter=val.get("first_seen_chapter"),
                description=val.get("description", ""),
            )
            if val.get("last_seen_chapter") is not None:
                reg.update_last_seen(val["canonical_name"], val["last_seen_chapter"])
        reg.chapter_summaries = data.get("chapter_summaries", [])
        return reg

    @classmethod
    def merge(cls, *registries: EntityRegistry) -> EntityRegistry:
        """Merge multiple registries (e.g., from different books)."""
        merged = cls()
        for reg in registries:
            for entry in reg._entities.values():
                merged.add(
                    name=entry.canonical_name,
                    entity_type=entry.entity_type,
                    aliases=entry.aliases,
                    significance=entry.significance,
                    first_seen_chapter=entry.first_seen_chapter,
                    description=entry.description,
                )
        return merged
