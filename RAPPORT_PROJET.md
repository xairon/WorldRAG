# FolkloRAG — Application RAG + Knowledge Graph pour le Folklore Français

> Rapport de conception complet — 6 février 2026

---

## 1. Vision du projet

Construire une application full-stack permettant de :

1. **Uploader des documents** (livres de folklore, textes de Wikisource, PDFs)
2. **Construire automatiquement un Knowledge Graph** riche avec une ontologie spécialisée (créatures, lieux, personnages, rituels, schémas narratifs...)
3. **Explorer le graphe visuellement** avec une UI interactive
4. **Interroger en langage naturel** via un système RAG hybride (vector + graph)
5. **Enrichir le modèle** avec un feedback loop Q&A

Le premier corpus cible : *Croyances et légendes du centre de la France* de Laisnel de la Salle (Wikisource), mais l'application doit être générique pour tout texte de folklore/patrimoine.

---

## 2. Analyse de l'existant — Pourquoi pas HippoRAG / GraphRAG / LightRAG ?

### 2.1 Frameworks évalués

| Framework | Publication | Forces | Faiblesses pour notre cas |
|-----------|------------|--------|--------------------------|
| **HippoRAG 2** | NeurIPS '24 / ICML '25 | Multi-hop reasoning, PageRank, mémoire continue | OpenIE générique (mauvais sur français XIXe), pas d'ontologie custom, lourd en GPU |
| **Microsoft GraphRAG** | 2024 | Community detection, résumés globaux | Extrêmement coûteux en tokens, lent, pas conçu pour extraction fine |
| **LightRAG** | EMNLP '25 | Rapide, léger, dual-level retrieval, incrémental | Extraction trop générique, pas de schéma d'entités spécialisé |
| **HyperGraphRAG** | 2025 | Hypergraphes, relations n-aires | Très récent, immature |
| **LinearRAG** | ICLR '26 | Construction sans relations, efficient | Trop récent, pas adapté au folklore |

### 2.2 Pourquoi une approche sur-mesure ?

Les frameworks existants souffrent de **trois limitations critiques** pour notre cas :

1. **Langue** — Tous sont optimisés pour l'anglais. L'OpenIE générique produit des triplets de mauvaise qualité sur du français du XIXe siècle avec du vocabulaire berrichon/patois local.

2. **Ontologie** — Aucun ne propose un schéma d'entités adapté au folklore (créatures, rituels, croyances, schémas narratifs). Le NER standard confond noms de lieux et personnages, rate les créatures folkloriques.

3. **Schémas narratifs** — Extraire des patterns narratifs (le héros trompé, l'épreuve initiatique, le pacte avec le diable) relève de la narratologie computationnelle, pas du RAG classique.

**Conclusion** : On prend le meilleur de chaque approche (retrieval hybride vector+graph comme LightRAG, extraction structurée par LLM, ontologie custom) dans un pipeline maîtrisé.

---

## 3. Stack technique

| Composant | Technologie | Justification |
|-----------|------------|---------------|
| **LLM** | OpenAI GPT-4o | Excellent en français, structured outputs natifs, bon rapport qualité/coût |
| **Embeddings** | OpenAI text-embedding-3-small | 1536 dims, bon en français, peu coûteux |
| **Backend** | Python 3.12 + FastAPI (async) | Écosystème NLP, async natif, rapide |
| **Graph DB** | Neo4j 5.x Community + vector index natif | Mature, Cypher, visualisation intégrée, vector search sans service supplémentaire |
| **Metadata DB** | SQLite via SQLAlchemy async | Léger, zero-config, suffisant pour les métadonnées |
| **Task Queue** | Celery + Redis | Traitement async des pipelines d'extraction |
| **Frontend** | Next.js 15 (App Router) + React 19 + TypeScript | SSR, écosystème riche, App Router moderne |
| **UI Components** | Tailwind CSS + shadcn/ui | Design system propre, accessible, customisable |
| **Graph Viz** | react-force-graph-2d + cytoscape.js | Interactif, performant, layouts avancés |
| **Déploiement** | Docker Compose | Reproductible, tous services orchestrés |

---

## 4. Architecture

```
                        ┌──────────────────────────────────────┐
                        │           Docker Compose             │
                        │                                      │
┌─────────────────┐     │  ┌──────────────────┐  ┌──────────┐ │
│                 │     │  │                  │  │          │ │
│   Next.js UI    │◄───►│  │  FastAPI Backend  │◄►│  Neo4j   │ │
│   (port 3000)   │ API │  │  (port 8000)     │  │  :7687   │ │
│                 │ +WS │  │                  │  │  :7474   │ │
│  - Dashboard    │     │  │  - REST API      │  │          │ │
│  - Upload       │     │  │  - WebSocket     │  │ + vector │ │
│  - Graph Viz    │     │  │  - SSE streaming │  │   index  │ │
│  - Chat         │     │  │                  │  │          │ │
│  - Entities     │     │  └────────┬─────────┘  └──────────┘ │
│                 │     │           │                          │
└─────────────────┘     │  ┌────────▼─────────┐  ┌──────────┐ │
                        │  │                  │  │          │ │
                        │  │  Celery Workers  │◄►│  Redis   │ │
                        │  │  (extraction     │  │  :6379   │ │
                        │  │   pipeline)      │  │          │ │
                        │  │                  │  └──────────┘ │
                        │  └──────────────────┘               │
                        │                                      │
                        │  ┌──────────────────┐               │
                        │  │  SQLite (local)  │               │
                        │  │  docs, jobs, Q&A │               │
                        │  └──────────────────┘               │
                        └──────────────────────────────────────┘

                        ┌──────────────────┐
                        │   OpenAI API     │
                        │  - GPT-4o        │
                        │  - Embeddings    │
                        └──────────────────┘
```

### Flux de données

```
Utilisateur                Frontend              Backend                Neo4j
    │                         │                     │                     │
    │── Upload document ─────►│── POST /upload ────►│                     │
    │                         │                     │── Celery task ────► │
    │                         │◄── WS progress ────│                     │
    │                         │                     │── 1. Parse ────►    │
    │                         │                     │── 2. Chunk ────►    │
    │                         │                     │── 3. Extract ──►GPT-4o
    │                         │                     │◄── entities ───     │
    │                         │                     │── 4. Dedup ────►    │
    │                         │                     │── 5. MERGE ────────►│
    │                         │                     │── 6. Embed ────────►│
    │                         │◄── "Done!" ────────│                     │
    │                         │                     │                     │
    │── Question NL ─────────►│── POST /chat ──────►│                     │
    │                         │                     │── vector search ───►│
    │                         │                     │◄── chunks ─────────│
    │                         │                     │── graph traverse ──►│
    │                         │                     │◄── subgraph ───────│
    │                         │                     │── GPT-4o RAG ──►    │
    │                         │◄── SSE stream ─────│◄── response ───     │
    │◄── Réponse + sources ──│                     │                     │
```

---

## 5. Structure du projet

```
E:\RAG/
│
├── docker-compose.yml              # Orchestration de tous les services
├── .env.example                    # Variables d'environnement template
├── .env                            # Variables d'environnement (ignoré par git)
├── .gitignore
├── RAPPORT_PROJET.md               # Ce fichier
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml              # Dépendances Python (uv/pip)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, CORS, lifespan, routers
│   │   ├── config.py               # Pydantic BaseSettings (.env)
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── documents.py    # POST upload, GET list, DELETE, GET chunks
│   │   │   │   ├── graph.py        # GET stats, explore, search, paths
│   │   │   │   ├── chat.py         # POST chat (SSE), GET history, POST feedback
│   │   │   │   └── entities.py     # GET list, GET detail, PUT update, POST merge
│   │   │   └── websocket.py        # WS /ws/pipeline/{job_id}
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py         # SQLAlchemy async engine + session
│   │   │   ├── document.py         # Document, Chunk, ProcessingJob
│   │   │   └── qa.py               # QAPair, Feedback
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py        # Parse PDF (pdfplumber), TXT, URL (httpx+bs4)
│   │   │   ├── chunking.py         # Structure-aware chunking
│   │   │   ├── extraction.py       # GPT-4o structured output extraction
│   │   │   ├── graph_builder.py    # Neo4j MERGE/CREATE operations
│   │   │   ├── deduplication.py    # Fuzzy matching + embedding similarity
│   │   │   ├── embeddings.py       # OpenAI embedding generation + Neo4j storage
│   │   │   ├── retrieval.py        # Hybrid retrieval (vector + Cypher)
│   │   │   ├── cypher_generator.py # NL → Cypher via GPT-4o
│   │   │   └── chat_engine.py      # Query routing + RAG + response generation
│   │   │
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── extraction.py       # System/user prompts pour extraction FR
│   │   │   ├── cypher.py           # Prompts NL→Cypher avec schéma
│   │   │   └── qa.py               # Prompts RAG Q&A
│   │   │
│   │   └── workers/
│   │       ├── __init__.py
│   │       └── pipeline.py         # Celery tasks : process_document, extract_chunk
│   │
│   └── tests/
│       ├── test_chunking.py
│       ├── test_extraction.py
│       └── test_retrieval.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   │
│   └── src/
│       ├── app/
│       │   ├── layout.tsx              # Root layout : sidebar + header
│       │   ├── page.tsx                # Dashboard (stats, activité récente)
│       │   ├── documents/
│       │   │   └── page.tsx            # Upload drag&drop + liste documents
│       │   ├── graph/
│       │   │   └── page.tsx            # Visualisation graphe interactive
│       │   ├── chat/
│       │   │   └── page.tsx            # Interface Q&A conversationnelle
│       │   └── entities/
│       │       ├── page.tsx            # Table d'entités filtrable
│       │       └── [id]/
│       │           └── page.tsx        # Fiche détail entité
│       │
│       ├── components/
│       │   ├── ui/                     # shadcn/ui (Button, Card, Dialog, etc.)
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx         # Navigation latérale
│       │   │   └── Header.tsx          # Barre supérieure
│       │   ├── graph/
│       │   │   ├── ForceGraph.tsx      # react-force-graph-2d wrapper
│       │   │   ├── GraphFilters.tsx    # Filtres par type d'entité (checkboxes colorées)
│       │   │   └── NodeTooltip.tsx     # Tooltip au survol d'un noeud
│       │   ├── chat/
│       │   │   ├── ChatWindow.tsx      # Container messages + input
│       │   │   ├── MessageBubble.tsx   # Bulle message (user/assistant)
│       │   │   ├── SourceCard.tsx      # Carte citation cliquable
│       │   │   └── FeedbackButtons.tsx # Pouce haut/bas + correction
│       │   ├── documents/
│       │   │   ├── UploadZone.tsx      # Zone drag & drop + URL input
│       │   │   ├── DocumentCard.tsx    # Carte document avec statut
│       │   │   └── ProcessingBar.tsx   # Barre de progression WebSocket
│       │   └── entities/
│       │       ├── EntityCard.tsx      # Carte entité (icône type + infos)
│       │       ├── EntityTable.tsx     # Table paginée + filtres
│       │       └── MiniGraph.tsx       # Petit graphe relations (page détail)
│       │
│       └── lib/
│           ├── api.ts                  # Client API typé (fetch wrapper)
│           ├── websocket.ts            # Hook useWebSocket
│           └── types.ts               # Types TypeScript partagés
│
└── scripts/
    ├── seed_wikisource.py              # Import depuis Wikisource (URL → upload)
    └── init_neo4j.cypher               # Création indexes + contraintes
```

---

## 6. Schéma Neo4j — Ontologie du Folklore

### 6.1 Labels (types de noeuds)

```cypher
// === ENTITES FOLKLORIQUES ===

(:Creature {
    name: String,           // "Loup-garou", "Feu follet"
    description: String,    // Description extraite du texte
    aliases: [String],      // Noms alternatifs, orthographes
    creature_type: String,  // "fantôme", "fée", "démon", "animal_surnaturel"
    powers: [String],       // "métamorphose", "invisibilité"
    weakness: String        // "eau bénite", "sel"
})

(:Personnage {
    name: String,           // "Jean le Sot", "la Mère Lusine"
    description: String,
    aliases: [String],
    role: String,           // "héros", "victime", "sage", "trickster"
    social_status: String   // "paysan", "seigneur", "curé", "berger"
})

(:Lieu {
    name: String,           // "Forêt de Tronçais", "Berry"
    description: String,
    region: String,         // "Berry", "Bourbonnais", "Marche"
    lieu_type: String,      // "forêt", "fontaine", "carrefour", "église"
    coordinates: String     // Optionnel, pour cartographie future
})

(:Histoire {
    name: String,           // "Le Loup-garou du moulin"
    summary: String,        // Résumé généré
    themes: [String],       // "métamorphose", "punition divine"
    moral: String,          // Morale si identifiable
    source_chapter: String  // Référence au chapitre d'origine
})

(:Rituel {
    name: String,           // "Conjuration du loup-garou"
    description: String,
    purpose: String,        // "protection", "guérison", "divination"
    period: String          // "nuit de la Saint-Jean", "Toussaint"
})

(:Croyance {
    name: String,           // "Les feux follets sont des âmes"
    description: String,
    origin: String,         // "celtique", "chrétienne", "mixte"
    domain: String          // "mort", "nature", "maladie", "météo"
})

(:Fete {
    name: String,           // "Saint-Jean", "Chandeleur"
    description: String,
    date_period: String,    // "24 juin", "2 février"
    season: String          // "été", "hiver"
})

(:Objet {
    name: String,           // "Branche de gui", "Pierre de foudre"
    description: String,
    powers: [String],       // "protection", "chance"
    material: String        // "bois", "fer", "pierre"
})

(:Plante {
    name: String,           // "Verveine", "Gui"
    description: String,
    usage_magique: String,  // "guérison", "protection", "amour"
    cueillette: String      // Conditions de cueillette rituelle
})

(:SchemaNarratif {
    name: String,           // "Pacte avec le diable", "Épreuve initiatique"
    description: String,
    archetype: String       // Classification type Propp/ATU
})

// === ENTITES STRUCTURELLES ===

(:Document {
    title: String,
    author: String,
    year: Integer,
    source_url: String,
    uploaded_at: DateTime,
    status: String          // "processing", "completed", "error"
})

(:Chunk {
    text: String,
    position: Integer,      // Ordre dans le document
    chapter: String,        // "Livre 1, Chapitre 3"
    section: String,        // Sous-section si applicable
    token_count: Integer,
    embedding: [Float]      // Vector 1536d pour Neo4j vector index
})

(:QAPair {
    question: String,
    answer: String,
    validated: Boolean,     // Validé par l'utilisateur
    corrected_answer: String, // Correction utilisateur si applicable
    created_at: DateTime,
    query_type: String      // "factual", "explorative", "comparative"
})
```

### 6.2 Relations typées

```cypher
// --- Structure documentaire ---
(:Document)-[:CONTIENT {position: Int}]->(:Chunk)
(:Chunk)-[:MENTIONNE {context: String}]->(:Creature|Personnage|Lieu|Objet|Plante)
(:Chunk)-[:RACONTE]->(:Histoire)
(:Chunk)-[:DECRIT]->(:Rituel|Croyance|Fete)

// --- Relations folkloriques ---
(:Creature)-[:APPARAIT_A {frequence: String}]->(:Lieu)
(:Creature)-[:INTERVIENT_DANS {role: String}]->(:Histoire)
(:Creature)-[:ASSOCIEE_A]->(:Croyance)
(:Personnage)-[:RENCONTRE {circonstance: String}]->(:Creature)
(:Personnage)-[:VIT_A]->(:Lieu)
(:Personnage)-[:PROTAGONISTE_DE {role: String}]->(:Histoire)
(:Rituel)-[:PROTEGE_CONTRE]->(:Creature)
(:Rituel)-[:INVOQUE]->(:Creature)
(:Rituel)-[:SE_DEROULE_PENDANT]->(:Fete)
(:Rituel)-[:UTILISE]->(:Plante|Objet)
(:Rituel)-[:PRATIQUE_A]->(:Lieu)
(:Histoire)-[:SE_DEROULE_A]->(:Lieu)
(:Histoire)-[:SUIT_SCHEMA]->(:SchemaNarratif)
(:Histoire)-[:ILLUSTRE]->(:Croyance)
(:Histoire)-[:LIEE_A {type_lien: String}]->(:Histoire) // Variantes, suites
(:Plante)-[:POUSSE_A]->(:Lieu)
(:Objet)-[:UTILISE_DANS]->(:Rituel)
(:Fete)-[:CELEBREE_A]->(:Lieu)

// --- Feedback ---
(:QAPair)-[:BASEE_SUR]->(:Chunk)
(:QAPair)-[:CONCERNE]->(:Creature|Personnage|Lieu|...)
```

### 6.3 Index et contraintes

```cypher
// Vector index pour le RAG
CREATE VECTOR INDEX chunk_embeddings FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
}}

// Fulltext pour recherche
CREATE FULLTEXT INDEX entity_names
FOR (n:Creature|Personnage|Lieu|Histoire|Rituel|Croyance|Fete|Objet|Plante)
ON EACH [n.name]

// Index de performance
CREATE INDEX creature_name FOR (n:Creature) ON (n.name)
CREATE INDEX personnage_name FOR (n:Personnage) ON (n.name)
CREATE INDEX lieu_name FOR (n:Lieu) ON (n.name)
CREATE INDEX histoire_name FOR (n:Histoire) ON (n.name)
CREATE INDEX document_title FOR (n:Document) ON (n.title)
CREATE INDEX chunk_position FOR (n:Chunk) ON (n.position)

// Contraintes d'unicité (par label)
CREATE CONSTRAINT creature_unique FOR (n:Creature) REQUIRE n.name IS UNIQUE
CREATE CONSTRAINT lieu_unique FOR (n:Lieu) REQUIRE n.name IS UNIQUE
CREATE CONSTRAINT document_unique FOR (n:Document) REQUIRE n.source_url IS UNIQUE
```

---

## 7. Pipeline de traitement — Détail

### 7.1 Ingestion (`services/ingestion.py`)

```
Input: fichier (PDF, TXT) ou URL Wikisource
Output: texte brut + métadonnées structurelles

- PDF → pdfplumber (extraction texte + détection titres via taille de police)
- TXT → lecture directe
- URL Wikisource → httpx GET + BeautifulSoup
  - Extraire le contenu de <div class="mw-parser-output">
  - Détecter les <h2>, <h3>, <h4> pour la structure
  - Nettoyer les notes de bas de page, liens internes
```

### 7.2 Chunking intelligent (`services/chunking.py`)

```
Input: texte brut + structure détectée
Output: liste de Chunks avec métadonnées

Stratégie :
1. Découper d'abord par section/chapitre (respecter les frontières narratives)
2. Si une section > 1500 tokens → sous-découper par paragraphe
3. Si un paragraphe > 1500 tokens → découper avec overlap de 200 tokens
4. Chaque chunk conserve : chapitre, section, position, texte avant/après (context window)

Taille cible : 1000-1500 tokens (sweet spot pour GPT-4o extraction)
```

### 7.3 Extraction GPT-4o (`services/extraction.py`)

C'est le coeur du système. On utilise les **structured outputs** de GPT-4o (response_format avec JSON schema) pour garantir la structure de sortie.

```
Input: un Chunk de texte
Output: {entities: [...], relations: [...], summary: String}

Prompt système (résumé) :
"""
Tu es un expert en folklore français. Analyse ce passage extrait d'un texte
du XIXe siècle sur les croyances et légendes du centre de la France.

Extrais TOUTES les entités mentionnées selon cette ontologie :
- Creature : être surnaturel (loup-garou, fée, fantôme, feu follet...)
- Personnage : personne nommée ou archétypale (le berger, Jean, la sorcière...)
- Lieu : endroit géographique ou type de lieu (forêt, Berry, fontaine...)
- Histoire : récit, légende, conte identifiable
- Rituel : pratique magique ou superstitieuse
- Croyance : croyance populaire ou superstition
- Fete : fête calendaire ou religieuse
- Objet : objet à valeur magique ou rituelle
- Plante : plante à usage magique ou médicinal
- SchemaNarratif : pattern narratif récurrent

Pour chaque entité, fournis : name, type, description (1-2 phrases), aliases (si variantes)
Pour chaque relation entre entités, fournis : source, relation_type, target, context

IMPORTANT :
- Utilise l'orthographe moderne pour les noms
- Regroupe les variantes orthographiques dans aliases
- Sois exhaustif mais précis
- Conserve le contexte original pour chaque relation
"""

JSON Schema de sortie :
{
    "entities": [{
        "name": "string",
        "type": "enum[Creature,Personnage,Lieu,...]",
        "description": "string",
        "aliases": ["string"],
        "properties": {}  // propriétés spécifiques au type
    }],
    "relations": [{
        "source": "string",      // nom de l'entité source
        "source_type": "string",
        "relation": "string",    // type de relation
        "target": "string",      // nom de l'entité cible
        "target_type": "string",
        "context": "string"      // phrase du texte justifiant la relation
    }],
    "summary": "string",         // résumé du chunk en 2-3 phrases
    "narrative_schema": "string|null" // schéma narratif si identifiable
}
```

### 7.4 Déduplication (`services/deduplication.py`)

```
Problème : "loup-garou", "Loup-Garou", "loup garou", "lycanthrope" = même entité

Stratégie en 3 passes :
1. Normalisation : lowercase, accents, tirets → matching exact
2. Fuzzy matching : Levenshtein distance < 0.3 → candidats
3. Embedding similarity : cosine > 0.92 → candidats
4. Pour les cas ambigus : appel GPT-4o "Ces entités sont-elles identiques ?"

Résultat : MERGE dans Neo4j, aliases mises à jour
```

### 7.5 Construction du graphe (`services/graph_builder.py`)

```cypher
// Pour chaque entité extraite :
MERGE (e:Creature {name: $name})
ON CREATE SET e.description = $description, e.aliases = $aliases, ...
ON MATCH SET e.description = CASE WHEN size(e.description) < size($description)
    THEN $description ELSE e.description END

// Pour chaque relation :
MATCH (a {name: $source}), (b {name: $target})
CREATE (a)-[:RELATION_TYPE {context: $context, chunk_id: $chunk_id}]->(b)

// Lier le chunk au document et aux entités
MATCH (d:Document {id: $doc_id})
CREATE (d)-[:CONTIENT {position: $pos}]->(c:Chunk {text: $text, ...})
WITH c
UNWIND $entity_names AS ename
MATCH (e {name: ename})
CREATE (c)-[:MENTIONNE]->(e)
```

### 7.6 Embeddings (`services/embeddings.py`)

```
Pour chaque Chunk :
1. Appel OpenAI text-embedding-3-small → vecteur 1536d
2. Stockage dans la propriété `embedding` du noeud Chunk
3. Indexé automatiquement par le vector index Neo4j

Batch processing : 100 chunks par appel API (limite OpenAI)
```

---

## 8. Système RAG — Retrieval & Chat

### 8.1 Types de requêtes et routing

Le chat engine classifie chaque question en un type, puis choisit la stratégie de retrieval :

| Type | Exemple | Stratégie |
|------|---------|-----------|
| **Factuelle** | "Qu'est-ce qu'un feu follet ?" | Vector search → chunks pertinents → GPT-4o |
| **Explorative** | "Liste toutes les créatures" | Cypher direct : `MATCH (c:Creature) RETURN c` |
| **Relationnelle** | "Quels rituels protègent du loup-garou ?" | Graph traversal : `MATCH (r:Rituel)-[:PROTEGE_CONTRE]->(c:Creature {name:'Loup-garou'}) RETURN r` |
| **Comparative** | "Différences entre les fées et les sorcières ?" | Vector search + graph paths → GPT-4o |
| **Narrative** | "Quelles histoires se déroulent en forêt ?" | Cypher : `MATCH (h:Histoire)-[:SE_DEROULE_A]->(l:Lieu {lieu_type:'forêt'}) RETURN h` |
| **Timeline** | "Quelles fêtes au printemps ?" | Cypher + tri par date_period |

### 8.2 Retrieval hybride (`services/retrieval.py`)

```python
async def hybrid_retrieve(question: str, top_k: int = 10):
    # 1. Vector search — trouver les chunks sémantiquement proches
    query_embedding = await get_embedding(question)
    vector_results = await neo4j.execute("""
        CALL db.index.vector.queryNodes('chunk_embeddings', $k, $embedding)
        YIELD node, score
        RETURN node.text AS text, node.chapter AS chapter, score
    """, k=top_k, embedding=query_embedding)

    # 2. Graph search — entités mentionnées dans la question
    entities = await extract_entities_from_question(question)  # GPT-4o
    graph_results = await neo4j.execute("""
        UNWIND $names AS name
        CALL db.index.fulltext.queryNodes('entity_names', name)
        YIELD node, score
        MATCH (node)-[r]-(related)
        RETURN node, type(r) AS relation, related, score
    """, names=entities)

    # 3. Merge & rerank
    return merge_and_rerank(vector_results, graph_results)
```

### 8.3 NL → Cypher (`services/cypher_generator.py`)

Pour les requêtes explorative/relationnelle/narrative, on traduit directement en Cypher :

```
Prompt GPT-4o :
"""
Voici le schéma Neo4j : [schéma complet injecté]
Traduis cette question en requête Cypher.
Question : {question}
Retourne UNIQUEMENT la requête Cypher valide.
"""

Sécurité :
- Whitelist des opérations (MATCH, RETURN, WHERE, ORDER BY, LIMIT)
- Rejet de tout WRITE (CREATE, DELETE, SET, MERGE)
- Validation syntaxique avant exécution
```

### 8.4 Génération de réponse (`services/chat_engine.py`)

```
Prompt RAG :
"""
Tu es un expert en folklore français. Réponds à la question de l'utilisateur
en te basant UNIQUEMENT sur les sources suivantes.

Sources (chunks de texte) :
{chunks avec métadonnées}

Contexte du graphe (entités et relations) :
{sous-graphe pertinent}

Q&A validées précédentes (si pertinentes) :
{qa_pairs validées}

Question : {question}

Instructions :
- Cite tes sources [Chapitre X, Section Y]
- Si l'information n'est pas dans les sources, dis-le explicitement
- Réponds en français
- Sois précis et détaillé
"""
```

---

## 9. Endpoints API — Spécification complète

### 9.1 Documents

| Méthode | Route | Description | Body/Params |
|---------|-------|-------------|-------------|
| `POST` | `/api/documents/upload` | Upload fichier ou URL | `multipart/form-data` : file OU `{url: string}` |
| `GET` | `/api/documents` | Liste tous les documents | `?page=1&limit=20` |
| `GET` | `/api/documents/{id}` | Détail document + statut | — |
| `DELETE` | `/api/documents/{id}` | Supprimer doc + entités orphelines | — |
| `GET` | `/api/documents/{id}/chunks` | Liste les chunks d'un doc | `?page=1&limit=50` |

### 9.2 Graphe

| Méthode | Route | Description | Params |
|---------|-------|-------------|--------|
| `GET` | `/api/graph/stats` | Stats globales du KG | — |
| `GET` | `/api/graph/explore` | Sous-graphe autour d'une entité | `?entity_id=X&depth=2&limit=50` |
| `GET` | `/api/graph/search` | Recherche fulltext dans le graphe | `?q=loup-garou&types=Creature,Lieu` |
| `GET` | `/api/graph/paths` | Chemins entre deux entités | `?from=X&to=Y&max_depth=4` |
| `GET` | `/api/graph/full` | Graphe complet (limité) | `?limit=200&types=Creature,Lieu` |

### 9.3 Entités

| Méthode | Route | Description | Body/Params |
|---------|-------|-------------|-------------|
| `GET` | `/api/entities` | Liste paginée + filtres | `?type=Creature&q=loup&page=1&limit=20` |
| `GET` | `/api/entities/{id}` | Détail + relations + chunks sources | — |
| `PUT` | `/api/entities/{id}` | Corriger une entité | `{name?, description?, aliases?}` |
| `POST` | `/api/entities/merge` | Fusionner des doublons | `{entity_ids: [id1, id2], keep_id: id1}` |
| `DELETE` | `/api/entities/{id}` | Supprimer une entité | — |

### 9.4 Chat

| Méthode | Route | Description | Body/Params |
|---------|-------|-------------|-------------|
| `POST` | `/api/chat` | Question → réponse streamée (SSE) | `{question: string, conversation_id?: string}` |
| `GET` | `/api/chat/history` | Historique conversations | `?page=1&limit=20` |
| `GET` | `/api/chat/{conversation_id}` | Messages d'une conversation | — |
| `POST` | `/api/chat/{message_id}/feedback` | Valider/corriger une réponse | `{validated: bool, corrected_answer?: string}` |

### 9.5 WebSocket

| Route | Description | Messages |
|-------|-------------|----------|
| `WS /ws/pipeline/{job_id}` | Progression temps réel | `{step: "chunking", progress: 45, message: "..."}` |

---

## 10. Pages Frontend — Détail

### 10.1 Dashboard (`/`)
- **Statistiques** : nb documents, nb entités par type (bar chart), nb relations, nb Q&A
- **Activité récente** : derniers documents uploadés, dernières questions posées
- **Entités populaires** : top 10 entités les plus connectées
- **Santé du graphe** : composantes connexes, densité

### 10.2 Documents (`/documents`)
- **UploadZone** : drag & drop fichier + champ URL Wikisource + bouton "Analyser"
- **Liste documents** : cards avec titre, auteur, date upload, statut (badge coloré)
- **ProcessingBar** : barre de progression en temps réel (WebSocket) avec étapes nommées
- **Actions** : voir chunks, relancer extraction, supprimer

### 10.3 Explorateur de graphe (`/graph`)
- **ForceGraph** : graphe interactif (react-force-graph-2d)
  - Noeuds colorés par type (légende interactive)
  - Taille des noeuds proportionnelle au nombre de connexions
  - Zoom, pan, drag
  - Clic sur noeud → panneau détail latéral
  - Clic sur arête → afficher le contexte/la citation
- **GraphFilters** : checkboxes par type d'entité, slider profondeur, recherche
- **Mini-map** : vue d'ensemble du graphe complet
- **Export** : PNG, SVG, JSON

### 10.4 Chat (`/chat`)
- **ChatWindow** : interface conversationnelle style messagerie
- **MessageBubble** (assistant) : texte formaté markdown + citations inline [1][2]
- **SourceCard** : cards cliquables sous la réponse (chapitre, extrait, lien vers le texte)
- **FeedbackButtons** : pouce haut/bas, bouton "Corriger", champ correction
- **Suggestions** : questions suggérées basées sur le graphe ("Essayez : Quelles créatures...")
- **Mode** : toggle entre "Chat libre" et "Requête structurée" (auto-détecté)

### 10.5 Navigateur d'entités (`/entities`)
- **Filtres** : dropdown type, recherche texte, tri (nom, nb connexions, nb mentions)
- **Vue grille** : EntityCards avec icône type, nom, description courte, nb connexions
- **Vue table** : EntityTable paginée, colonnes triables
- **Bulk actions** : sélection multiple → fusionner, supprimer

### 10.6 Détail entité (`/entities/[id]`)
- **Fiche** : nom, type (badge), description, aliases, propriétés spécifiques
- **MiniGraph** : graphe des relations directes (profondeur 1-2)
- **Sources** : liste des chunks qui mentionnent cette entité (avec texte surligné)
- **Relations** : table des relations entrantes/sortantes
- **Actions** : éditer, fusionner avec une autre, supprimer

---

## 11. Phases d'implémentation

### Phase 1 — Infrastructure et fondations
**Objectif** : `docker compose up` → tous les services démarrent et communiquent.

- [ ] `docker-compose.yml` (Neo4j, Redis, backend, frontend)
- [ ] `backend/Dockerfile` + `pyproject.toml` (dépendances)
- [ ] `app/main.py` (FastAPI, CORS, lifespan avec connexion Neo4j)
- [ ] `app/config.py` (BaseSettings, .env)
- [ ] Connexion Neo4j async + script init schéma (`init_neo4j.cypher`)
- [ ] SQLAlchemy async + models (Document, Chunk, ProcessingJob)
- [ ] `GET /api/health` → vérifier toutes les connexions
- [ ] `frontend/` : `npx create-next-app`, Tailwind, shadcn/ui init
- [ ] Layout de base : sidebar navigation, header, pages vides
- [ ] `.env.example` + `.gitignore`

**Critère de validation** : `docker compose up` → frontend accessible sur :3000, backend sur :8000/docs, Neo4j sur :7474

### Phase 2 — Ingestion & Extraction (coeur)
**Objectif** : Uploader un texte Wikisource → voir des entités apparaître dans Neo4j Browser.

- [ ] `POST /api/documents/upload` (fichier + URL)
- [ ] `services/ingestion.py` — parser Wikisource (httpx + BeautifulSoup)
- [ ] `services/chunking.py` — chunking structure-aware
- [ ] `prompts/extraction.py` — prompts FR pour GPT-4o
- [ ] `services/extraction.py` — appel GPT-4o structured outputs
- [ ] `services/graph_builder.py` — MERGE/CREATE dans Neo4j
- [ ] `services/embeddings.py` — génération + stockage embeddings
- [ ] `workers/pipeline.py` — tâche Celery orchestrant le tout
- [ ] `api/websocket.py` — progression temps réel
- [ ] Frontend : page Documents avec UploadZone + ProcessingBar
- [ ] Tester avec le Tome 1 de *Croyances et légendes*

**Critère de validation** : Upload URL Wikisource → progression visible → entités dans Neo4j Browser (localhost:7474)

### Phase 3 — Exploration du graphe (valeur visible)
**Objectif** : Naviguer visuellement dans le knowledge graph.

- [ ] `GET /api/graph/stats` + `GET /api/graph/explore` + `GET /api/graph/search`
- [ ] `GET /api/entities` + `GET /api/entities/{id}`
- [ ] Frontend : Dashboard avec stats
- [ ] Frontend : ForceGraph interactif + filtres
- [ ] Frontend : EntityTable + EntityCard
- [ ] Frontend : page détail entité avec MiniGraph

**Critère de validation** : Voir le graphe du folklore, filtrer par créatures, cliquer sur "Loup-garou" → voir ses relations

### Phase 4 — RAG & Chat (intelligence)
**Objectif** : Poser des questions en français et obtenir des réponses sourcées.

- [ ] `services/retrieval.py` — retrieval hybride (vector + graph)
- [ ] `services/cypher_generator.py` — NL → Cypher
- [ ] `services/chat_engine.py` — routing + RAG + génération
- [ ] `POST /api/chat` avec SSE streaming
- [ ] `models/qa.py` — stockage Q&A pairs
- [ ] `POST /api/chat/{id}/feedback` — validation/correction
- [ ] Frontend : ChatWindow + MessageBubble + SourceCard + FeedbackButtons

**Critère de validation** : "Quelles créatures apparaissent en Berry ?" → réponse pertinente avec citations

### Phase 5 — Raffinement et polish
**Objectif** : Qualité production.

- [ ] `services/deduplication.py` — dédup avancée (fuzzy + embeddings + LLM)
- [ ] UI correction d'entités (édition inline)
- [ ] UI fusion de doublons
- [ ] `GET /api/graph/paths` — chemins entre entités
- [ ] Export données (JSON, CSV)
- [ ] Timeline visualization (pour fêtes et événements)
- [ ] Dark mode
- [ ] Tests unitaires et d'intégration
- [ ] Optimisations performance (cache, batch processing)

---

## 12. Dépendances — Versions recommandées

### Backend (`pyproject.toml`)

```toml
[project]
name = "folklorag-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # API
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "python-multipart>=0.0.18",
    "websockets>=14.0",
    # Database
    "neo4j>=5.27",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.20",
    # LLM & Embeddings
    "openai>=1.60",
    # Task Queue
    "celery[redis]>=5.4",
    # Document parsing
    "beautifulsoup4>=4.12",
    "httpx>=0.28",
    "pdfplumber>=0.11",
    # Utils
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "python-dotenv>=1.0",
    "thefuzz>=0.22",           # Fuzzy string matching
]
```

### Frontend (`package.json`)

```json
{
    "dependencies": {
        "next": "^15.1",
        "react": "^19.0",
        "react-dom": "^19.0",
        "react-force-graph-2d": "^1.25",
        "lucide-react": "^0.469",
        "zustand": "^5.0",
        "tailwind-merge": "^2.6",
        "clsx": "^2.1"
    },
    "devDependencies": {
        "typescript": "^5.7",
        "@types/react": "^19.0",
        "tailwindcss": "^3.4",
        "postcss": "^8.4",
        "autoprefixer": "^10.4"
    }
}
```

---

## 13. Estimation des coûts API (OpenAI)

Pour le Tome 1 de *Croyances et légendes* (~200 pages, ~80 000 tokens) :

| Opération | Appels estimés | Coût estimé |
|-----------|---------------|-------------|
| Extraction (GPT-4o) | ~60 chunks × ~2000 tokens input | ~$1.50 |
| Embeddings (3-small) | ~60 chunks | ~$0.01 |
| Dédup (GPT-4o) | ~30 comparaisons | ~$0.30 |
| Q&A (par question) | ~1 appel | ~$0.05 |
| **Total indexation 1 livre** | | **~$2** |

Budget raisonnable pour un corpus de 10-20 livres : **$20-50**.

---

## 14. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Extraction GPT-4o peu fiable sur français XIXe | Graphe pollué | Few-shot prompts avec exemples réels, human-in-the-loop |
| Déduplication insuffisante | Doublons dans le graphe | Pipeline 3 passes (exact → fuzzy → LLM), UI de fusion |
| Coûts API incontrôlés | Facture salée | Compteur de tokens, limites par document, cache |
| Schéma Neo4j trop rigide | Entités qui ne rentrent dans aucune catégorie | Label "Autre" + possibilité d'ajouter des types |
| NL→Cypher génère des requêtes invalides | Erreurs chat | Validation + fallback sur vector search pur |
| Performances graphe sur gros corpus | UI lente | Pagination, limites de profondeur, lazy loading |

---

## 15. Pour reprendre le projet

1. Relire ce rapport
2. Commencer par la **Phase 1** (infrastructure)
3. Tester avec un petit extrait (1 chapitre) avant le livre entier
4. Itérer sur les prompts d'extraction avec des exemples réels
5. Chaque phase produit un résultat testable — ne pas passer à la suivante sans valider

**Commande pour démarrer** :
```bash
cd E:\RAG
# On commence par le docker-compose et les boilerplates
```
