"""Synthetic chapter text in The Primal Hunter style for extraction testing.

These are NOT verbatim text from the book (copyright). They are original
passages written to exercise every extraction pattern the pipeline handles,
using the same character names, skills, and LitRPG conventions.

Each chapter is paired with a GoldenChapterExpectation from golden_primal_hunter.py
so tests can verify recall (did we find what we should?) and precision
(did we hallucinate entities that don't exist?).
"""

from __future__ import annotations

from tests.fixtures.golden_primal_hunter import GoldenChapterExpectation

# ── Chapter 1: Tutorial start — Characters, Skills, Level-up ────────────

CHAPTER_1_TEXT = """\
Chapter 1: Welcome to the Multiverse

Jake Thayne blinked. One moment he had been sitting in a dull office meeting,
and the next he found himself standing in a clearing surrounded by towering
ancient trees. Ninety-three other humans milled around, equally confused.

A blue panel materialized before his eyes.

[Skill Acquired: Basic Archery - Inferior]

The System notification dissolved as quickly as it appeared. Jake flexed his
fingers, feeling something fundamentally different about his body. He reached
for the crude bow that had appeared on his back — archery had always been a
hobby, and now it seemed the System recognized that.

"Welcome, ninety-third universe," a booming voice echoed through the forest.
"Your Tutorial begins now. Survive. Grow. Or perish."

A second notification appeared:

[Skill Acquired: Archer's Eye - Common]
+2 Perception

He drew the bow experimentally. The arrow flew true, embedding itself in a
distant oak. The Archer's Eye skill gave the world crystalline clarity —
every leaf, every insect, every movement registered with preternatural detail.

Hours passed. Jake hunted small creatures in the forest, gaining experience
with each kill. The familiar thrill of the hunt consumed him. After dispatching
a pack of five Thornback Boars, the System rewarded him:

Level: 1 -> 3
+10 Free Points

Class: Archer (F-grade)

He invested the points into Perception and Agility. Higher ground, better
angles — that was his path forward.

"Jake!" a voice called from behind. Caleb Thayne, his younger brother,
jogged toward him through the undergrowth. "I was hoping I'd find you in
this nightmare."

"Cal." Jake lowered his bow. "You got a class yet?"

"Some kind of lightning warrior thing," Caleb replied, dark sparks flickering
between his fingertips. "The System calls it Warrior (Light). What about you?"

"Archer. Naturally."

They spent the rest of the day together, clearing the immediate area of
hostile wildlife. By nightfall, Jake had reached Level 5, and a new
opportunity appeared:

Title earned: Forerunner of the New World
"""

CHAPTER_1_EXPECTED = GoldenChapterExpectation(
    chapter_number=1,
    expected_characters=frozenset({"Jake Thayne", "Caleb Thayne"}),
    expected_skills=frozenset({"Basic Archery", "Archer's Eye"}),
    expected_classes=frozenset({"Archer", "Warrior (Light)"}),
    expected_titles=frozenset({"Forerunner of the New World"}),
    expected_events=frozenset(),
    expected_locations=frozenset(),
    expected_factions=frozenset(),
    min_entity_count=6,
)


# ── Chapter 2: The Malefic Viper — Patron, Blessing, Profession ────────

CHAPTER_2_TEXT = """\
Chapter 2: The Challenge Dungeon

Jake stood at the entrance of the cave that pulsed with venomous green energy.
The System notification was clear:

[Challenge Dungeon Discovered: Legacy of the Malefic Viper]

He entered alone.

Deep within the twisting tunnels, surrounded by toxic mushrooms and pools
of bubbling acid, Jake encountered something impossible. A presence —
ancient, vast, and utterly alien — pressed against his consciousness.

"Well, well," a voice said, oozing amusement. "A little human who doesn't
cower. How refreshing."

Jake looked up. The being before him was a massive serpent, black scales
shimmering with green highlights, eyes glowing with dim emerald light.
This was Vilastromoz — The Malefic Viper. A Primordial.

"You have potential, hunter," Villy said. That's what Jake decided to call
him. The Primordial seemed entertained rather than offended. "I have watched
you. Your bloodline is... interesting."

[Skill Acquired: Palate of the Malefic Viper - Legendary]

The skill flooded Jake's senses. Suddenly he could taste the mana in the air,
distinguish between seventeen different types of toxin in the mushrooms
around him. His new profession crystallized:

Class: Alchemist of the Malefic Viper (F-grade Profession)

"I offer you my Blessing," Vilastromoz continued, his serpentine eyes
narrowing. "Not the watered-down Lesser Blessing I give my other followers.
For you — a True Blessing."

[Title earned: Holder of a Primordial's True Blessing]

Jake felt power surge through him. The Order of the Malefic Viper had
a new member — and its Primordial patron seemed genuinely pleased for
the first time in eons.

Duskleaf, a fellow disciple who had been watching from the shadows, stepped
forward. "Impressive. The master has not offered a True Blessing in
eighty-five eras."

+5 Wisdom, +5 Willpower
"""

CHAPTER_2_EXPECTED = GoldenChapterExpectation(
    chapter_number=2,
    expected_characters=frozenset({"Jake Thayne", "Vilastromoz", "Duskleaf"}),
    expected_skills=frozenset({"Palate of the Malefic Viper"}),
    expected_classes=frozenset(),
    expected_titles=frozenset({"Holder of a Primordial's True Blessing"}),
    expected_events=frozenset(),
    expected_locations=frozenset(),
    expected_factions=frozenset({"Order of the Malefic Viper"}),
    min_entity_count=5,
)


# ── Chapter 3: Haven — Politics, City, Miranda, Factions ───────────────

CHAPTER_3_TEXT = """\
Chapter 3: Building Haven

The post-tutorial world was unrecognizable. Earth had transformed into a
mana-saturated realm of danger and opportunity. Jake was the first to
claim a Civilization Pylon, establishing what would become Haven — the
first true settlement in the new world.

Miranda Wells arrived on the third day. The former manufacturing plant
manager had survived the tutorial through cunning and determination,
leading a group of twelve survivors to Jake's settlement.

"Someone needs to actually run this place," Miranda said, her practical
nature cutting through the chaos. "You're not exactly management material,
Thayne."

Jake agreed without hesitation. Miranda became the City Lord of Haven.

[Skill Acquired: Dreams of the Verdant Lagoon - Legendary]

The skill came to Miranda in her sleep — a gift from the Ladies of the
Verdant Lagoon. She received their Divine Blessing, and with it, power
over verdant magic that could sustain and grow the settlement.

Hank, Miranda's longtime friend, served as Haven's chief defender. The
big man had been a construction worker before the System, and now his
Warrior (Heavy) class made him a walking fortress.

News arrived from the east. Caleb Thayne had established Skyggen,
operating the Court of Shadows — a faction focused on intelligence and
espionage. The brothers had chosen very different paths.

Meanwhile, rumors spread of The Holy Church consolidating power in the
south, and Valhal establishing a warrior stronghold in Scandinavia.

Level: 31 -> 32
+5 Free Points

Jake looked out over Haven. This was just the beginning.
"""

CHAPTER_3_EXPECTED = GoldenChapterExpectation(
    chapter_number=3,
    expected_characters=frozenset({"Jake Thayne", "Miranda Wells", "Hank", "Caleb Thayne"}),
    expected_skills=frozenset({"Dreams of the Verdant Lagoon"}),
    expected_classes=frozenset({"Warrior (Heavy)"}),
    expected_titles=frozenset(),
    expected_events=frozenset(),
    expected_locations=frozenset({"Haven", "Skyggen"}),
    expected_factions=frozenset({"Haven", "Court of Shadows", "The Holy Church", "Valhal"}),
    min_entity_count=8,
)


# ── Chapter 4: Combat — Events, Level-ups, Evolution ───────────────────

CHAPTER_4_TEXT = """\
Chapter 4: The King of the Forest

The beast stood forty meters tall — a D-grade Unique Lifeform that the
System simply called the King of the Forest. Ancient bark covered its
body like armor, and massive root-tentacles writhed in every direction.

Jake nocked an arrow. The Ambitious Hunter class thrummed with power as
he activated Gaze of the Apex Predator. His eyes shifted to a predatory
yellow, and the King of the Forest actually hesitated.

"Come on then," Jake whispered.

The battle was brutal. Sylphie, the little hawk with emerald feathers,
darted through the air, distracting the behemoth with wind-blades. She
had grown since hatching — already E-grade, and ferociously loyal.

Jake unleashed Arcane Powershot after Arcane Powershot. Each arrow
carved chunks from the monster's bark-armor. Purple and green arcane
energy trailed behind every shot.

The King of the Forest roared and swept a root-tentacle. Jake activated
One Step Mile, blinking fifty meters sideways. The tentacle carved a
trench where he'd stood.

Three hours. Twelve Healing Potions. One near-death experience.

The King fell.

Level: 74 -> 75
+5 Free Points

[Skill Acquired: Moment of the Primal Hunter - Ancient]
+10 Perception, +5 Agility

Evolution: Ambitious Hunter -> Avaricious Arcane Hunter (D-grade)

The evolution washed over Jake in a wave of power. His class had advanced
to D-grade. The System acknowledged his achievement:

Title earned: Prodigious Slayer of the Mighty

Jake sat down heavily, Sylphie landing on his shoulder. "We did it, girl."
The hawk chirped happily.

Arnold approached from the tree line, his rifle still smoking. The sniper
had provided covering fire throughout the battle. "Not bad, Thayne."

"Thanks for the backup." Jake grinned. Haven's strongest had proven they
could handle the worst the forest could throw at them.
"""

CHAPTER_4_EXPECTED = GoldenChapterExpectation(
    chapter_number=4,
    expected_characters=frozenset({"Jake Thayne", "Sylphie", "Arnold"}),
    expected_skills=frozenset(
        {
            "Gaze of the Apex Predator",
            "One Step Mile",
            "Moment of the Primal Hunter",
        }
    ),
    expected_classes=frozenset({"Avaricious Arcane Hunter"}),
    expected_titles=frozenset({"Prodigious Slayer of the Mighty"}),
    expected_events=frozenset(),
    expected_locations=frozenset(),
    expected_factions=frozenset(),
    min_entity_count=7,
)


# ── Chapter 5: Multi-entity dense — Everything at once ─────────────────

CHAPTER_5_TEXT = """\
Chapter 5: Nevermore

Jake stepped through the portal into Nevermore, the legendary multi-layered
dungeon that spanned an entire pocket dimension. The Order of the Malefic
Viper had pulled strings to secure his entry.

"Focus," Villy's voice echoed in his mind. The Malefic Viper rarely spoke
directly, but Nevermore demanded respect even from Primordials.

The first floor was a sprawling wilderness filled with C-grade beasts.
Jake's Arcane Hunter of Horizon's Edge class had reached its peak, and
he needed the challenge. He activated Shroud of the Primordial to mask
his presence, then drew his bow.

Miranda had wished him luck before his departure from Haven.
"Don't die, Thayne. I don't want to deal with the paperwork."

On the seventy-eighth floor, Jake encountered Carmen, another Earth
prodigy. The berserker woman had carved her own path through Nevermore
with nothing but her fists and an unbreakable will.

"Thayne," Carmen grinned, blood splattered across her armor. "Race you
to the top?"

[Skill Acquired: Event Horizon - Legendary]

The skill allowed Jake to compress space around him, creating a zone of
distorted gravity. Combined with his archery, it was devastating.

Level: 199 -> 200
+10 Free Points

Evolution: Arcane Hunter of Horizon's Edge -> Arcane Hunter of the Boundless Horizon (B-grade)

Title earned: Perfect Evolution (B-grade)

Title earned: Sacred Prodigy

Title earned: Peerless Conqueror of Nevermore

Vilastromoz laughed in Jake's mind. "Not bad for a little human. The
93rd universe might actually be interesting after all."

The Pantheon of Life had been watching Jake's progress with growing
concern. His connection to the Malefic Viper — and his bloodline — made
him unpredictable. The Empire of Blight saw an opportunity.

Ell'Hakan, the schemer, plotted from the shadows. The self-styled
"Chosen" of Eversmile had his own plans for Earth.
"""

CHAPTER_5_EXPECTED = GoldenChapterExpectation(
    chapter_number=5,
    expected_characters=frozenset(
        {
            "Jake Thayne",
            "Vilastromoz",
            "Miranda Wells",
            "Carmen",
            "Ell'Hakan",
        }
    ),
    expected_skills=frozenset({"Event Horizon", "Shroud of the Primordial"}),
    expected_classes=frozenset({"Arcane Hunter of the Boundless Horizon"}),
    expected_titles=frozenset(
        {
            "Perfect Evolution (B-grade)",
            "Sacred Prodigy",
            "Peerless Conqueror of Nevermore",
        }
    ),
    expected_events=frozenset(),
    expected_locations=frozenset({"Nevermore", "Haven"}),
    expected_factions=frozenset(
        {
            "Order of the Malefic Viper",
            "Pantheon of Life",
            "Empire of Blight",
        }
    ),
    min_entity_count=12,
)


# ── All chapters for parametrized tests ─────────────────────────────────

ALL_CHAPTERS: list[tuple[str, GoldenChapterExpectation]] = [
    (CHAPTER_1_TEXT, CHAPTER_1_EXPECTED),
    (CHAPTER_2_TEXT, CHAPTER_2_EXPECTED),
    (CHAPTER_3_TEXT, CHAPTER_3_EXPECTED),
    (CHAPTER_4_TEXT, CHAPTER_4_EXPECTED),
    (CHAPTER_5_TEXT, CHAPTER_5_EXPECTED),
]
