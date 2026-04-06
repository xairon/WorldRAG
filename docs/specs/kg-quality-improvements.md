# Cahier des charges : Améliorations qualité KG — Post-GOLEM v1.1

> **Version** : 1.0  
> **Date** : 2026-04-06  
> **Contexte** : Le refactor GOLEM v1.1 est déployé et validé (76 chapitres extraits). L'audit KG révèle 6 problèmes critiques de qualité. Ce CDC définit les améliorations à implémenter, priorisées par impact.  
> **Sources académiques** : KGGen (NeurIPS 2025), AutoSchemaKG (HKUST 2025), LightKGG (2025), OneKE (WWW 2025), LLMs4OL 2025 Challenge.

---

## 1. Vue d'ensemble des problèmes et solutions

| # | Problème | Impact | Solution proposée | Inspiration |
|---|----------|--------|-------------------|-------------|
| 1 | 758 RELATES_TO résiduels + 113 types hallucinated | Relations inutilisables pour le RAG | KGGen-style iterative clustering sur les relations | KGGen §3 |
| 2 | 99.4% Objects sans description | RAG ne peut pas exploiter les objets | Prompt improvement + post-extraction enrichment | — |
| 3 | 8/24 edge types GOLEM à 0 | Structure narrative sous-exploitée | Topology-enhanced inference post-processing | LightKGG |
| 4 | ~95 orphan PS/CF (alias mismatch) | Entités déconnectées du graphe | KGGen-style entity resolution (S-BERT + BM25 + LLM) | KGGen §2.3 |
| 5 | 22/24 NarrativeSequence sans events | Arcs narratifs déconnectés | Topology inference + prompt improvement | LightKGG |
| 6 | SocialRelationship naming/quality | SR inutilisables pour le RAG | Schema-guided validation + auto-naming | OneKE |

---

## 2. Amélioration 1 — Entity Resolution KGGen-style

### 2.1 Problème

Le reconciler actuel utilise un pipeline 3-tier (exact → fuzzy thefuzz → LLM-as-Judge) qui rate les alias complexes :
- "the malefic viper" ≠ "malefic viper" ≠ "the viper" ≠ "villy"
- Résultat : ~95 nœuds orphelins (PsychologicalState, CharacterFeature sans HAS_STATE/HAS_FEATURE)

### 2.2 Solution : S-BERT clustering + BM25 fused retrieval

**Inspiré de KGGen** (Stanford/Toronto, NeurIPS 2025) qui atteint 22.4% de réduction d'entités.

**Architecture :**

```
Étape 1 : S-BERT embedding de toutes les entités
         → k-means clustering (clusters de 128)

Étape 2 : Pour chaque entité dans un cluster :
         a) Retrieval top-k=16 (BM25 + cosine S-BERT fusionné)
         b) LLM identifie les duplicatas exacts (tense, pluriel, articles, abbréviations)
         c) Sélection du nom canonique
         d) Retrait de l'entité + duplicatas, itération

Étape 3 : Application de la cluster map aux relations
```

**Ce que ça change vs l'existant :**

| Aspect | Actuel | Proposé |
|--------|--------|---------|
| Similarity | thefuzz token_set_ratio (lexical) | S-BERT cosine + BM25 fused (sémantique + lexical) |
| Scope | Intra-chapitre seulement | Cross-chapitre (book-level post-processing) |
| Clustering | Aucun | k-means en clusters de 128 |
| Retrieval | Comparaison all-vs-all O(n²) | Top-k retrieval O(n·k) |
| Canonicalization | Premier nom vu | LLM sélectionne le meilleur représentant |

### 2.3 Fichiers impactés

- `backend/app/services/extraction/reconciler.py` — Refactor `reconcile_flat_entities()` pour utiliser S-BERT clustering
- `backend/app/services/extraction/book_level.py` — Ajouter `book_level_entity_resolution()` post-extraction
- `backend/app/llm/embeddings.py` — Ajouter méthode `batch_embed_texts()` pour le clustering

### 2.4 Métriques de succès

- Orphan PsychologicalState : 52 → < 10
- Orphan CharacterFeature : 36 → < 5
- Entity count reduction : ≥ 15% (benchmark KGGen : 22.4%)
- Pas de faux positifs : 0 entités incorrectement fusionnées

---

## 3. Amélioration 2 — Relation Type Resolution

### 3.1 Problème

758 RELATES_TO résiduels (4e edge le plus peuplé). 113 types hallucinated par le LLM (JAKE_AND_VIPER_FIST_BUMP, FLYING_TOWARDS, DODGES...). Le LLM génère des edges ad-hoc au lieu d'utiliser les types ontologiques.

**KGGen montre que GraphRAG a le même problème** : "nearly as many relation types (966) as edges (981)" — ratio type/edge de 0.98. KGGen réduit ce ratio à 0.10 (chaque type réutilisé 10x en moyenne).

### 3.2 Solution : Relation clustering + coercion en 2 passes

**Passe 1 (extraction time)** — Déjà fait en Phase B : whitelist de 50 types valides, rejet des types > 30 chars.

**Passe 2 (book-level post-processing)** — Nouveau :

```python
# Pour chaque relation type non-standard dans le graphe :
# 1. Embed le type name + context
# 2. Trouver le type ontologique le plus proche (cosine similarity)
# 3. Si similarity > 0.80 → reclassifier
# 4. Sinon → garder comme RELATES_TO (cross-type légitime)
```

**Passe 3 (RELATES_TO Character-Character)** — Nouveau :

```python
# Pour chaque RELATES_TO entre deux Characters :
# 1. Récupérer le context de la relation
# 2. LLM classifie en SocialRelationship type
# 3. Créer le nœud SocialRelationship + INVOLVED_IN edges
# 4. Supprimer RELATES_TO
```

### 3.3 Fichiers impactés

- `backend/app/services/extraction/book_level.py` — Ajouter `reclassify_untyped_relations()`
- `backend/app/services/extraction/relations.py` — Améliorer le coercer avec embedding similarity

### 3.4 Métriques de succès

- RELATES_TO Character-Character : 52 → 0
- Relation types hallucinated (count=1) : 113 → 0
- Ratio type/edge : < 0.15 (benchmark KGGen : 0.10)
- RELATES_TO cross-type légitimes : nombre stable (les Concept-Concept etc. sont acceptables)

---

## 4. Amélioration 3 — Topology-Enhanced Inference

### 4.1 Problème

8/24 edge types GOLEM ont 0 instances. Les edges structurels manquants :
- CHARACTER_IN_WORK (fixé, 78)
- SETTING_OF_WORK (fixé, 21)
- TRIGGERS_EVENT (0) — PsychologicalState → Event causal
- ROLE_IN_SEQUENCE (0) — NarrativeRole → NarrativeSequence
- RELATIONSHIP_CAUSED_BY (0) — SocialRelationship → Event
- FOLLOWS_STATE (15, très bas) — chaînes émotionnelles
- SEQUENCED_IN (4, très bas) — Event → NarrativeSequence

### 4.2 Solution : Inférence topologique post-extraction

**Inspiré de LightKGG** qui utilise bidirectional BFS + transitive closure pour découvrir des relations implicites.

**Algorithmes :**

```
1. TRIGGERS_EVENT : Pour chaque PsychologicalState avec trigger_event non-vide,
   MATCH l'Event par nom fuzzy et créer l'edge.
   Si trigger_event vide, chercher l'Event le plus proche temporellement
   (même chapitre, même personnage participant).

2. FOLLOWS_STATE : Pour chaque paire de PsychologicalState du même personnage
   dans des chapitres consécutifs, créer FOLLOWS_STATE.

3. ROLE_IN_SEQUENCE : Pour chaque NarrativeRole, si le context mentionne un
   NarrativeSequence connu, créer l'edge.

4. SEQUENCED_IN : Pour chaque NarrativeSequence, chercher les Events dans la
   même range de chapitres (chapter_start → chapter_end) et les lier.

5. RELATIONSHIP_CAUSED_BY : Pour chaque SocialRelationship avec trigger_event,
   MATCH et créer l'edge.
```

### 4.3 Fichiers impactés

- `backend/app/services/extraction/book_level.py` — Ajouter `infer_golem_edges()`
- `backend/app/workers/tasks.py` — Appeler après book-level post-processing

### 4.4 Métriques de succès

- TRIGGERS_EVENT : 0 → ≥ 200 (au moins 25% des PS)
- FOLLOWS_STATE : 15 → ≥ 300 (chaînes émotionnelles continues)
- SEQUENCED_IN : 4 → ≥ 50 (chaque NarrativeSequence a ≥ 3 events)
- ROLE_IN_SEQUENCE : 0 → ≥ 10
- RELATIONSHIP_CAUSED_BY : 0 → ≥ 5

---

## 5. Amélioration 4 — Description Enrichment Post-Extraction

### 5.1 Problème

99.4% des Objects n'ont pas de description. 100% des Professions idem. L'extraction LLM ne remplit pas systématiquement le champ description pour les types secondaires.

### 5.2 Solution : LLM enrichment pass

**Approche :** Après l'extraction complète d'un livre, passe de batch enrichment :

```python
# Pour chaque entité sans description :
# 1. Récupérer tous les chunks où l'entité est MENTIONED_IN
# 2. Concatener les passages source (max 2000 tokens)
# 3. LLM génère une description de 1-3 phrases
# 4. SET entity.description = generated_desc
```

**Coût estimé :** ~300 entités × ~100 tokens output = 30K tokens ≈ $0.01 (Gemini Flash).

### 5.3 Fichiers impactés

- `backend/app/services/extraction/book_level.py` — Ajouter `enrich_entity_descriptions()`
- `backend/app/workers/tasks.py` — Appeler après entity summaries

### 5.4 Métriques de succès

- Objects avec description : 0.6% → > 90%
- Professions avec description : 0% → > 90%
- Qualité description : BLEU ≥ 0.3 vs description humaine (spot check 20 entités)

---

## 6. Amélioration 5 — MINE Benchmark Integration

### 6.1 Problème

Aucune métrique objective pour évaluer la qualité du KG extrait. On ne sait pas si une re-extraction est meilleure ou pire que la précédente.

### 6.2 Solution : Adapter le benchmark MINE de KGGen

**MINE** (Measure of Information in Nodes and Edges) — NeurIPS 2025 :

```
Pour chaque article/chapitre :
1. 15 faits manuellement vérifiés (ground truth)
2. Pour chaque fait :
   a. Embed le fait avec S-BERT
   b. Retrieval top-k nœuds les plus similaires dans le KG
   c. Expand aux voisins à 2 hops
   d. LLM juge : le sous-graphe permet-il d'inférer ce fait ? (0/1)
3. Score = % de faits inférables

Score final = moyenne sur tous les articles
```

**Adaptation pour WorldRAG :**
- Utiliser 10 chapitres (au lieu de 100 articles)
- 10 faits par chapitre (au lieu de 15) — annotés manuellement ou via LLM-as-annotator
- Comparer les scores avant/après chaque amélioration

### 6.3 Fichiers impactés

- `backend/app/services/evaluation/` — Nouveau module
- `backend/app/services/evaluation/mine_benchmark.py` — Implémentation MINE
- `scripts/evaluate_kg.py` — CLI pour lancer l'évaluation

### 6.4 Métriques de succès

- Baseline MINE score sur KG actuel
- Chaque amélioration doit augmenter le score MINE de ≥ 5%
- Target : MINE ≥ 0.70 (KGGen atteint 0.66 en open-domain)

---

## 7. Amélioration 6 — Schema Co-Evolution (AutoSchemaKG-style)

### 7.1 Problème

Le `pattern_inducer` actuel est lexical + similarité BGE-m3 post-hoc. Il découvre des types comme "stat", "ability", "potion" mais ne fait pas de conceptualisation (abstraire instances → types sémantiques).

### 7.2 Solution : Conceptualisation AutoSchemaKG

**Inspiré de AutoSchemaKG** (HKUST 2025) qui atteint 92% d'alignement avec des schemas humains.

**Processus :**

```
1. Extraction instance-level (déjà fait par le pipeline V4)
2. Conceptualisation :
   a. Grouper les instances par similarité sémantique
   b. LLM abstrait chaque groupe en un concept-type
   c. Vérifier l'alignement avec l'ontologie existante
   d. Si nouveau type valide → extend_with_induced()
   e. Si sous-type d'un type existant → parent_type
3. Itération : les nouveaux types améliorent l'extraction suivante
```

**Différence avec l'existant :**

| Aspect | pattern_inducer actuel | Proposé (AutoSchemaKG) |
|--------|----------------------|------------------------|
| Input | 3 premiers chapitres | Livre entier (post-extraction) |
| Méthode | LLM one-shot induction | Clustering instances → abstraction |
| Scope | Types + regex patterns | Types + hiérarchie + relations |
| Iteration | Single-shot | Itératif (feedback loop) |
| Validation | Similarité BGE-m3 | Alignement ontologique formel |

### 7.3 Fichiers impactés

- `backend/app/services/extraction/pattern_inducer.py` — Ajouter `conceptualize_instances()`
- `backend/app/core/ontology_loader.py` — Support hiérarchie multi-niveaux
- `backend/app/workers/tasks.py` — Appeler après book-level

### 7.4 Métriques de succès

- Types induits avec parent_type : ≥ 50% (vs 0% actuellement)
- Alignement ontologique : ≥ 85% (benchmark AutoSchemaKG : 92%)
- Réduction des GenreEntity catch-all : 107 → < 30

---

## 8. Plan d'implémentation

### Phase 1 : Fondations (3 jours)

| # | Tâche | Priorité | Impact |
|---|-------|----------|--------|
| 1a | MINE benchmark baseline | P0 | Mesure objective avant toute amélioration |
| 1b | Entity resolution KGGen-style | P0 | Fix 95 orphans, -15% entités |
| 1c | Description enrichment batch | P0 | Fix 99.4% Objects sans desc |

### Phase 2 : Edges structurels (2 jours)

| # | Tâche | Priorité | Impact |
|---|-------|----------|--------|
| 2a | Topology inference (FOLLOWS_STATE, TRIGGERS_EVENT) | P0 | +500 edges GOLEM structurels |
| 2b | Relation reclassification (RELATES_TO → types) | P0 | -700 RELATES_TO |
| 2c | SEQUENCED_IN auto-linkage | P1 | Fix NarrativeSequence isolation |

### Phase 3 : Schema evolution (3 jours)

| # | Tâche | Priorité | Impact |
|---|-------|----------|--------|
| 3a | AutoSchemaKG conceptualisation | P1 | Réduction GenreEntity catch-all |
| 3b | Cross-book entity resolution | P1 | Prépare multi-série Stoff |
| 3c | MINE re-evaluation | P0 | Mesure impact total |

### Estimation totale : ~8 jours

---

## 9. Références

| Référence | Utilisation |
|-----------|-----------|
| KGGen (Stanford/Toronto, NeurIPS 2025) — [arXiv:2502.09956](https://arxiv.org/abs/2502.09956) | Entity resolution S-BERT+BM25, MINE benchmark, relation clustering |
| AutoSchemaKG (HKUST, 2025) — [arXiv:2505.23628](https://arxiv.org/abs/2505.23628) | Conceptualisation instances→types, schema induction autonome |
| LightKGG (2025) — [arXiv:2510.23341](https://arxiv.org/abs/2510.23341) | Topology-enhanced inference, bidirectional BFS, transitive closure |
| OneKE (ZJU, WWW 2025) — [GitHub](https://github.com/zjunlp/OneKE) | Multi-agent validation, schema-guided extraction |
| LLMs4OL 2025 Challenge — [Site](https://sites.google.com/view/llms4ol2025) | Benchmark ontology learning, hybrid pipelines |
| Survey LLM-KG Construction — [arXiv:2510.20345](https://arxiv.org/abs/2510.20345) | Vue d'ensemble schema-based vs schema-free |
