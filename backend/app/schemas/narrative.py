"""Pydantic schemas for narrative analysis (Pass 6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CharacterDevelopment(BaseModel):
    """A character development moment detected in text."""

    character: str = Field(..., description="Character name")
    aspect: str = Field(
        ...,
        description="What developed: personality, motivation, worldview, relationships",
    )
    description: str = Field("", description="Brief description of the development")
    trigger_sentences: list[int] = Field(
        default_factory=list,
        description="Approximate sentence indices in chapter",
    )


class PowerChange(BaseModel):
    """A power progression event (level up, skill gain, class change)."""

    character: str = Field(..., description="Character name")
    change_type: str = Field(
        ...,
        description="Type: level_up, skill_acquired, class_change, stat_increase, title_gained",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured details of the change",
    )


class ForeshadowingHint(BaseModel):
    """A narrative hint or foreshadowing element."""

    description: str = Field(..., description="What is being foreshadowed")
    hint_text: str = Field("", description="The actual text that hints")
    confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Confidence this is foreshadowing",
    )


class ThemeOccurrence(BaseModel):
    """A recurring theme or motif detected."""

    theme: str = Field(..., description="Theme name")
    manifestation: str = Field(
        "",
        description="How it manifests in this chapter",
    )


class NarrativeAnalysisResult(BaseModel):
    """Combined narrative analysis result for a chapter."""

    character_developments: list[CharacterDevelopment] = Field(default_factory=list)
    power_changes: list[PowerChange] = Field(default_factory=list)
    foreshadowing_hints: list[ForeshadowingHint] = Field(default_factory=list)
    themes: list[ThemeOccurrence] = Field(default_factory=list)
