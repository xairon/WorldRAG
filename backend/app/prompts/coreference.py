"""Prompt template for coreference resolution (Pass 5b)."""

COREFERENCE_PROMPT = """\
Tu es un expert en analyse linguistique.
Résous les pronoms dans le texte suivant
en les associant au personnage ou entité correct.

**Personnages connus dans cette scène :**
{entity_context}

**Texte :**
{text}

Pour chaque pronom (il, elle, ils, elles, lui, leur, son, sa, ses, he, she, they, his, her, etc.),
indique à quel personnage ou entité il fait référence.

Ne résous que les pronoms pour lesquels tu es confiant (>80%). Ignore les pronoms ambigus.
"""
