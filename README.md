## `README.md` – Chatbot RAG AMDIE

# Chatbot RAG – AMDIE

## Présentation

Ce projet consiste en un **chatbot intelligent basé sur l'architecture RAG** (Retrieval-Augmented Generation), conçu pour répondre aux questions des utilisateurs en interrogeant une **base vectorielle de documents internes à l'AMDIE**.

L'objectif est de centraliser les connaissances issues de documents disparates et d’éviter de solliciter systématiquement les collaborateurs pour obtenir des réponses.  
Ce projet a été réalisé dans le cadre d’un stage d’ingénieur en 4e année.

---

## Architecture technique

Le système repose sur une architecture modulaire en 4 composants principaux :

- **Frontend (Next.js)** : interface utilisateur de type chat
- **API REST (FastAPI)** : authentification, gestion de sessions, orchestration
- **Serveur MCP** : point d'entrée pour l'exécution du backend LLM
- **Backend IA (LangGraph)** : exécute les agents de traitement, les appels à la base vectorielle (ChromaDB) et renvoie les réponses

---

## Technologies utilisées

| Composant        | Technologie                      |
|------------------|----------------------------------|
| LLM              | Gemini (via MCP - Streamable HTTP) |
| Backend IA       | Python + LangGraph (agents)      |
| API REST         | FastAPI                          |
| Base vectorielle | ChromaDB                         |
| Authentification | Keycloak (OAuth2)                |
| Frontend         | Next.js + Tailwind + Shadcn      |

---

## Structure du projet

```

chatbot_maroc/
├── backend_python/        # Backend IA : agents, vectorisation, extraction
├── message_fastapi/       # API REST FastAPI (auth, orchestration, sessions)
├── mcp-server-amdie/      # Serveur MCP (Streamable HTTP)
├── frontend/              # Interface utilisateur React
├── data/                  # Documents d'entrée classés par niveau (public, admin…)
├── output/                # Fichiers JSON extraits et indexés
├── docs/                  # Documentation générée avec pdoc
└── README.md              # Ce fichier

````

---

## Lancement du projet

Chaque composant doit être lancé **dans un terminal distinct**.

### 1. Lancer Keycloak

```bash
cd keycloak/bin
./kc.sh start-dev --http-port 8080
````

* L’authentification se fait par rôle (`admin`, `employee`, `public`)
* Les tokens JWT sont validés automatiquement par l’API

---

### 2. Lancer l’API REST (FastAPI)

```bash
cd message_fastapi
uvicorn main:app --reload --port 8000
```

* Interface Swagger : [http://localhost:8000/docs](http://localhost:8000/docs)
* Utilise un stockage partagé local : `/tmp/chatbot_sessions.json`

---

### 3. Lancer le serveur MCP (LLM Gemini)

```bash
cd mcp-server-amdie
python mcp_backend_server.py
```

Le serveur est accessible à l’API REST à l’adresse :

```
http://0.0.0.0:8090/mcp/
```

---

### 4. Lancer le frontend (React/Next.js)

```bash
cd frontend
npm install
npm run dev
```

Accessible via : [http://localhost:3000](http://localhost:3000)
L’utilisateur est redirigé vers Keycloak au moment de la connexion.

---

## Fonctionnement

* L’utilisateur se connecte via **Keycloak** (identité, rôle, permissions).
* Il pose une question via l’interface frontend.
* L’**API REST** crée une session et appelle le **serveur MCP**.
* Le **serveur MCP** déclenche le backend (LangGraph) avec les permissions utilisateur.
* Le backend interroge **ChromaDB** et renvoie une réponse personnalisée.
* Les messages sont stockés dans `/tmp/chatbot_sessions.json`.

---

## Accès aux données

Les documents sont automatiquement filtrés à l’indexation selon leur niveau de confidentialité.
La structure suivante est utilisée :

```
data/
├── admin/      # documents confidentiels (accès admin)
├── public/     # documents ouverts (accès public)
├── salarie/    # documents internes (accès salarié) 
```

---

## Documentation

* Documentation générée automatiquement avec `pdoc` : `docs/`
* Notices utilisateurs disponibles :

  * `NOTICE_PUBLIC.md`
  * `NOTICE_SALARIE.md`
  * `NOTICE_ADMIN.md`

---

## Auteur

Projet réalisé par **Assia AIT TALEB** dans le cadre d’un stage à l’AMDIE – 4e année ingénieur.

