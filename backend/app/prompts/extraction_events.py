"""Prompts for Pass 3: Events & Timeline Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting narrative events, battles, discoveries, deaths,
and arc developments with temporal anchoring.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extract ALL significant narrative events from this chapter text.

For each EVENT, extract:
- name: a short, descriptive name (2-6 words)
- description: what happened (1-2 sentences)
- event_type: action, state_change, achievement, process, dialogue
- significance: minor, moderate, major, critical, arc_defining
- participants: list of character names involved
- location: where it happened (if mentioned)
- is_flashback: true if the event is narrated as a past event

EVENT TYPE GUIDE:
- action: a character does something (fights, casts, moves, speaks)
- state_change: something changes state (alliance shifts, power gained, location changes)
- achievement: a milestone is reached (level up, class evolution, quest complete)
- process: an ongoing activity (training, crafting, traveling)
- dialogue: a significant conversation that reveals information or advances plot

SIGNIFICANCE GUIDE:
- minor: flavor events, minor actions, brief mentions
- moderate: character development, skill usage, plot movement
- major: important battles, key revelations, significant power-ups
- critical: deaths, major betrayals, arc-changing moments
- arc_defining: events that define or conclude a narrative arc

IMPORTANT RULES:
- Capture events in CHRONOLOGICAL ORDER as they appear in the text.
- For flashbacks, set is_flashback=true but still capture them.
- Include ALL participants by name, even witnesses.
- If an event CAUSES another event, note the causal link.
- Do NOT over-extract: combine closely related micro-actions into one event.
- Each event should be a semantically complete unit.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "The Steelback Drake roared, its scales gleaming in the dim light. "
            "Jake notched an arrow, channeling Arcane Powershot. "
            "The arrow pierced through its defenses, striking true. "
            "The beast fell, and the dungeon trembled as a notification appeared: "
            "[Dungeon Boss Defeated]\n"
            "Sylphie landed beside him, chirping triumphantly. "
            '"That was reckless," the Sword Saint said, emerging from the shadows.'
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Jake notched an arrow, channeling Arcane Powershot",
                attributes={
                    "name": "Jake defeats Steelback Drake",
                    "event_type": "action",
                    "significance": "major",
                    "participants": "Jake Thayne, Sylphie",
                    "description": (
                        "Jake channels Arcane Powershot to kill the Steelback Drake dungeon boss"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Dungeon Boss Defeated",
                attributes={
                    "name": "Dungeon boss cleared",
                    "event_type": "achievement",
                    "significance": "major",
                    "participants": "Jake Thayne",
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text='"That was reckless," the Sword Saint said',
                attributes={
                    "name": "Sword Saint critiques Jake",
                    "event_type": "dialogue",
                    "significance": "minor",
                    "participants": "Miyamoto, Jake Thayne",
                    "description": "The Sword Saint comments on Jake's reckless combat style",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Zac remembered the day his planet was integrated. The pillar of light "
            "had descended without warning, killing millions in an instant. "
            "His mother had been among them. Now, standing before the World Tree, "
            "he swore to protect what remained."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="event",
                extraction_text=(
                    "The pillar of light had descended without warning, killing millions"
                ),
                attributes={
                    "name": "Earth integration event",
                    "event_type": "state_change",
                    "significance": "arc_defining",
                    "participants": "Zac Atwood",
                    "is_flashback": "true",
                    "description": (
                        "Earth was integrated by the System, "
                        "killing millions including Zac's mother"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="standing before the World Tree, he swore to protect what remained",
                attributes={
                    "name": "Zac's oath at World Tree",
                    "event_type": "state_change",
                    "significance": "major",
                    "participants": "Zac Atwood",
                    "location": "World Tree",
                    "description": "Zac swears to protect what remains after the integration",
                },
            ),
        ],
    ),
]
