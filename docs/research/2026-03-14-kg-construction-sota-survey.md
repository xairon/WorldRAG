# Construction de Knowledge Graphs par LLM — État de l'art 2025-2026

Rapport de veille technologique Mars 2026 — Nicolas, LIFAT / Université de Tours
Contexte : projet WorldRAG / NarrativeGraph

## Résumé exécutif

Le domaine de la construction automatique de Knowledge Graphs (KG) par Large Language Models a connu une transformation majeure entre 2024 et 2026. Le paradigme a basculé d'un pipeline NLP classique (NER → RE → Entity Linking) vers des approches entièrement génératives où le LLM remplace chaque étape spécialisée. Trois innovations structurantes ont émergé :

1. **KGGen** (NeurIPS 2025) — premier extracteur text-to-KG avec clustering itératif et benchmark standardisé (MINE), atteignant 66% de précision contre 48% pour GraphRAG.
2. **Graphiti/Zep** (jan. 2025) — moteur de graphe temporel bi-temporel pour mémoire agent, SOTA sur DMR (94.8%) et LongMemEval (+18.5% vs baselines).
3. **GFM-RAG** (NeurIPS 2025 / ICLR 2026) — premier foundation model pour le retrieval sur graphe (GNN 8M params, zero-shot cross-domain).

---

## 1. Contexte et évolution du domaine

### 1.1 Du pipeline NLP classique au paradigme génératif

Avant 2023, la construction de KG reposait sur un pipeline multi-étapes avec des modèles spécialisés : Named Entity Recognition (NER) via spaCy ou BERT fine-tuné, Relation Extraction (RE) via des classifieurs supervisés, et Entity Linking vers des bases comme Wikidata. Ce pipeline nécessitait des données annotées par domaine, des mois de développement, et une expertise NLP pointue.

L'arrivée des LLMs a reconfiguré l'économie et l'accessibilité de ce processus. L'extraction d'information est devenue une tâche générative : au lieu d'entraîner des modèles spécialisés, on enseigne au LLM un schéma cible via un prompt structuré et on le laisse extraire en conséquence. Le few-shot prompting avec GPT-4 ou Claude atteint une précision équivalente — et parfois supérieure — aux modèles supervisés, sans nécessiter de données annotées.

### 1.2 Trois générations d'outils (2024-2026)

| Génération | Période | Représentants | Caractéristique |
|------------|---------|---------------|-----------------|
| Gen 1 | 2024 | MS GraphRAG, OpenIE | Extraction brute, pas d'entity resolution |
| Gen 2 | 2025 | KGGen, LightRAG, Graphiti | Clustering, dual-level retrieval, temporalité |
| Gen 3 | 2025-2026 | GFM-RAG, GKG-LLM, AutoSchemaKG | Foundation models, schéma auto-induit, KG unifié |

### 1.3 Le survey de référence (oct. 2025)

Le survey de Bian et al. (arXiv:2510.20345, oct. 2025) identifie deux paradigmes complémentaires :
- **Schema-based** : le LLM extrait selon un schéma ontologique prédéfini. Favorise la cohérence et la normalisation.
- **Schema-free** : le LLM extrait librement, puis un post-traitement induit le schéma. Favorise la couverture et la découverte.

Les approches SOTA actuelles combinent les deux : extraction libre puis clustering/normalisation (KGGen), ou schéma personnalisable avec induction automatique (Graphiti, AutoSchemaKG).

---

## 2. Taxonomie des approches

### 2.1 Par méthode d'extraction

| Approche | Description | Exemples |
|----------|-------------|----------|
| Prompt engineering | Extraction via prompts structurés (zero/few-shot) | KGGen, Neo4j KG Builder |
| Fine-tuning | LLM fine-tuné sur des tâches KG spécifiques | GKG-LLM, LightKGG |
| Agent-based | Agent LLM autonome qui itère sur l'extraction | AutoSchemaKG (ATLAS) |
| Hybrid GNN+LLM | GNN pour le retrieval, LLM pour la génération | GFM-RAG |

### 2.2 Par type de graphe construit

| Type | Description | Use case |
|------|-------------|----------|
| KG statique | Triplets (s, p, o) sans temporalité | Documentation, FAQ |
| Temporal KG | Triplets avec fenêtres de validité | Narratifs, mémoire agent |
| Event KG | Graphe d'événements ordonnés | Timeline, causalité |
| Community KG | KG + clustering Leiden + résumés | QA globale, synthèse |

### 2.3 Par stratégie de retrieval

| Stratégie | Latence | Coût | Profondeur |
|-----------|---------|------|------------|
| Vector search | ~80ms | Faible | Shallow |
| Community traversal (GraphRAG) | ~500ms+ | Élevé (appels LLM) | Profonde |
| Dual-level keys (LightRAG) | ~80ms | Faible | Moyenne |
| Hybrid (Graphiti) | ~300ms | Modéré (pas de LLM au query) | Profonde |
| GNN reasoning (GFM-RAG) | ~100ms | Modéré (inference GNN) | Profonde |

---

## 3. Outils et frameworks SOTA

### 3.1 KGGen — Le nouveau standard d'extraction

**Origine :** Stanford University, University of Toronto, FAR AI
**Publication :** NeurIPS 2025 (poster)
**Papier :** Mo et al., "KGGen: Extracting Knowledge Graphs from Plain Text with Language Models" (arXiv:2502.09956)
**Code :** `pip install kg-gen` — github.com/stair-lab/kg-gen

#### Architecture

KGGen opère en trois étapes distinctes :

1. **Entity extraction** : Le LLM produit une liste structurée d'entités en JSON via DSPy (structured output garanti).
2. **Relation extraction** : Un second appel LLM reçoit la liste d'entités ET le texte source, et produit des triplets (sujet, prédicat, objet). Cette approche en 2 passes améliore significativement la cohérence.
3. **Iterative clustering** : L'innovation principale. Un algorithme examine les nœuds par lots et identifie les synonymes, alias et variantes. Le processus est itératif — pas de one-shot.

#### Résultats

| Méthode | MINE Score | Densité relative |
|---------|-----------|-----------------|
| KGGen | 66.07% | Référence |
| GraphRAG | 47.80% | Sparse |
| OpenIE | 29.84% | Très sparse |

#### Limitations
- Coût élevé si utilisé avec GPT-4o (mais réductible avec Gemini Flash ou modèles locaux).
- Pas de gestion native de la temporalité.
- Le clustering itératif est lent sur de très grands corpus (> 10k chunks).

### 3.2 Graphiti / Zep — Le moteur temporel

**Origine :** Zep AI
**Publication :** arXiv:2501.13956 (jan. 2025), présenté à KGC 2025
**Code :** `pip install graphiti-core` — github.com/getzep/graphiti

#### Modèle bi-temporel

Chaque edge du graphe porte quatre timestamps :

| Timestamp | Dimension | Description |
|-----------|-----------|-------------|
| t_valid | Event time (T) | Quand le fait est devenu vrai dans le monde |
| t_invalid | Event time (T) | Quand le fait a cessé d'être vrai |
| t'_created | Ingestion time (T') | Quand le fait a été ingéré dans le système |
| t'_expired | Ingestion time (T') | Quand le fait a été invalidé dans le système |

#### Architecture du graphe hiérarchique

1. **Episodic subgraph** : Données brutes (épisodes). Ground truth traçable.
2. **Semantic subgraph** : Entités extraites et faits avec timestamps de validité.
3. **Community subgraph** : Clusters Leiden avec résumés de haut niveau.

#### Retrieval hybride (sans LLM au query time)

- Semantic search (BGE-m3 embeddings)
- BM25 keyword search (Lucene/Neo4j)
- Graph traversal (BFS)

Latence P95 de 300ms indépendante de la taille du graphe.

#### Résultats

| Benchmark | Zep/Graphiti | Baseline | Delta |
|-----------|-------------|----------|-------|
| DMR | 94.8% | 93.4% (MemGPT) | +1.4% |
| LongMemEval | — | — | +18.5% |
| Latence P95 | 300ms | ~3000ms | -90% |

### 3.3 Microsoft GraphRAG

**Coût d'indexation très élevé** (~$6-7/livre avec GPT-4o). Batch processing uniquement. Graphes souvent sparse. Non recommandé pour données dynamiques ou narratives.

### 3.4 LightRAG

**Innovation : dual-level retrieval** (low-level entités + high-level thématique). ~$0.50/livre. Updates incrémentaux. ~80ms latence. Pas de temporalité native.

### 3.5 GFM-RAG — Graph Foundation Model

**Premier foundation model pour retrieval sur KG.** GNN 8M params, entraîné sur 60 KGs (14M+ triplets). SOTA sur 3 datasets multi-hop QA et 7 datasets domain-specific. Zero-shot cross-domain.

### 3.6 Autres approches notables

- **AutoSchemaKG** : 900M+ nœuds, 5.9B edges, 95% alignement sémantique avec schémas humains.
- **GKG-LLM** : Framework unifié KG + Event KG + Commonsense KG.
- **LightKGG** : SLM 1.5B params, fonctionne sur un seul GPU.

---

## 5. Comparaison synthétique

| Critère | KGGen | Graphiti | GraphRAG | LightRAG | GFM-RAG |
|---------|-------|---------|----------|----------|---------|
| Extraction | 2-pass + clustering | LLM + dedup auto | LLM par chunk | LLM + dedup | GPT-4o-mini |
| Entity resolution | Clustering itératif | LLM Embedding + LLM | Aucun natif | Dedup basique | ColBERTv2 (0.8) |
| Temporalité | Non | Bi-temporel (4 timestamps) | Non | Non | Non |
| Retrieval | N/A | Hybrid 3-modes | Community traversal | Dual-level vector | GNN reasoning |
| Latence query | N/A | 300ms P95 | 500ms+ | 80ms | ~100ms |
| Coût / livre | ~$0.50 (Gemini Flash) | ~$1 (GPT-4o-mini) | ~$7 (GPT-4o) | ~$0.50 | Variable |
| Updates incrémentaux | Non natif | Oui (natif) | Non | Oui | Non natif |

---

## 6. Pipeline optimal pour LitRPG narratif

### Stack recommandé

| Couche | Composant | Technologie |
|--------|-----------|-------------|
| Ingestion | Parsing EPUB | ebooklib |
| Ingestion | Chunking | LangChain RecursiveCharacterTextSplitter (~500 tokens) |
| Extraction | Extracteur | KGGen (kg-gen) |
| Extraction | LLM | Gemini 2.5 Flash via LiteLLM |
| Stockage | Engine | Graphiti (graphiti-core) |
| Stockage | Backend | Neo4j 5.26 |
| Stockage | Temporalité | Bi-temporel natif t_valid/t_invalid par chapitre |
| Retrieval | Semantic search | BGE-m3 embeddings |
| Retrieval | Keyword search | BM25 (Lucene/Neo4j) |
| Retrieval | Graph traversal | Graphiti BFS |

### Estimation des coûts

Pour un livre LitRPG typique (~120 000 mots, ~42 chapitres) : **~$0.35 total** avec Gemini 2.5 Flash. Comparaison : ~$7 avec GraphRAG + GPT-4o.

---

## Références

### Papiers clés

1. Mo, B. et al. (2025). "KGGen: Extracting Knowledge Graphs from Plain Text with Language Models." NeurIPS 2025. arXiv:2502.09956.
2. Rasmussen, P. et al. (2025). "Zep: A Temporal Knowledge Graph Architecture for Agent Memory." arXiv:2501.13956.
3. Luo, L. et al. (2025). "GFM-RAG: Graph Foundation Model for Retrieval Augmented Generation." NeurIPS 2025. arXiv:2502.01113.
4. Bian, H. et al. (2025). "LLM-empowered Knowledge Graph Construction: A Survey." arXiv:2510.20345.
5. Edge, D. et al. (2024). "From Local to Global: A Graph RAG Approach to Query-Focused Summarization." Microsoft Research.
6. Zhang, J. et al. (2026). "GKG-LLM: A Unified Framework for Generalized Knowledge Graph Construction." Information Fusion, 128, 103956.
7. Bai, A. et al. (2025). "AutoSchemaKG: Automatic Schema-based Knowledge Graph Construction." HKUST.
8. Guo, Z. et al. (2024). "LightRAG: Simple and Fast Retrieval-Augmented Generation." HKU Data Science Lab.

### Repositories

| Outil | URL |
|-------|-----|
| KGGen | github.com/stair-lab/kg-gen |
| Graphiti | github.com/getzep/graphiti |
| MS GraphRAG | github.com/microsoft/graphrag |
| LightRAG | github.com/HKUDS/LightRAG |
| GFM-RAG | github.com/RManLuo/gfm-rag |

Rapport généré le 14 mars 2026.
