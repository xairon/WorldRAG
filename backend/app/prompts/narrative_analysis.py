"""Prompt template for narrative analysis (Pass 6)."""

NARRATIVE_ANALYSIS_PROMPT = """\
Tu es un expert en analyse littéraire spécialisé dans la fiction
LitRPG et fantasy. Analyse le chapitre suivant et identifie les
éléments narratifs avancés.

**Personnages connus :**
{entity_context}

**Texte du chapitre :**
{chapter_text}

Identifie :
1. **Développements de personnages** : changements de personnalité,
   croissance émotionnelle, évolution des motivations, moments de
   prise de conscience
2. **Progressions de puissance** : montées de niveau, acquisition
   de compétences, changement de classe, gains de stats significatifs
3. **Indices de préfiguration (foreshadowing)** : éléments narratifs
   qui annoncent des événements futurs, mystères non résolus,
   promesses narratives
4. **Thèmes récurrents** : motifs narratifs, thèmes philosophiques
   ou moraux qui traversent le récit

Sois précis et ne liste que les éléments que tu identifies avec
confiance. Qualité > quantité.
"""
