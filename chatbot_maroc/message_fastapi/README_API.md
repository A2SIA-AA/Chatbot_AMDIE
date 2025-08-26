# API FastAPI - Chatbot AMDIE

##  Objectif
Ce module expose une API REST centralisée qui :
- Gère l’authentification (JWT ou Keycloak)
- Reçoit les questions utilisateur (frontend)
- Ordonne les appels au backend RAG via MCP
- Gère les sessions et messages (stockage partagé)
- Sert de point de supervision (routes debug / health)

---

##  Arborescence

```

message_fastapi/
├── main.py                # Entrée principale FastAPI
├── auth.py                # Authentification JWT classique
├── auth_keycloack.py      # Authentification via Keycloak
├── models.py              # Schémas Pydantic (utilisateur, message…)
├── message_store.py       # Stockage partagé des messages de session
├── mcp_client_utils.py    # Fonctions pour communiquer avec le serveur MCP
├── fastapi_essai.py       # Version d’essai
├── mcp_backend_essai.py   # Autre test de liaison backend MCP

````

---

##  Lancement rapide

###  Prérequis
- FastAPI
- Uvicorn
- MCP client compatible

###  Lancer le serveur
```bash
python main.py
````

Accessible sur : [http://localhost:8000/docs](http://localhost:8000/docs)

---

##  Authentification

###  JWT classique

* Route : `/api/v1/auth/login`
* Permissions par rôle (`admin`, `employee`, `public`)

### Keycloak

* Route de connexion : `/api/v1/auth/keycloak/login-url`
* Route de callback : `/api/v1/auth/keycloak/callback`
* Décodage du token JWT avec la clé publique du realm

---

##  Gestion des messages et sessions

Tous les échanges passent par le fichier partagé `/tmp/chatbot_sessions.json`, accessible en lecture/écriture par plusieurs processus :

| Route                        | Description                             |
| ---------------------------- | --------------------------------------- |
| `/api/v1/messages`           | Ajout d’un message depuis le backend    |
| `/api/v1/messages/{id}`      | Récupération ou suppression de messages |
| `/api/v1/sessions`           | Lister toutes les sessions actives      |
| `/api/v1/sessions/{id}/info` | Détails d’une session                   |
| `/api/v1/backend/status`     | Vérification disponibilité backend      |

---

##  Démarrage du traitement

###  Route centrale

```http
POST /api/v1/start-processing
```

* Authentification requise
* Crée une session
* Envoie les métadonnées vers MCP
* Appelle `chatbot_wrapper.py` via le serveur MCP (tool `start_backend`)

### Variante Keycloak :

```http
POST /api/v1/start-processing-keycloak
```

---

##  Permissions par rôle

Basées sur :

* `check_permission()` (JWT)
* `check_permission_keycloak()` (Keycloak)

Exemples :

* `read_public_docs`, `chat_basic`, `view_statistics`
* `read_internal_docs`, `chat_advanced`, `download_reports`
* `manage_users`, `upload_documents` (admin)

---

##  Debug & Monitoring

* `GET /api/v1/permissions/test` - vérifie les permissions actuelles
* `GET /api/v1/admin/users` - accessible uniquement aux administrateurs
* `GET /api/v1/auth/me` - profil utilisateur connecté

---

##  Intégration MCP

* Utilise `mcp_client_utils.py` pour appeler dynamiquement le serveur MCP
* Fonction principale : `mcp_start_backend()`
* Autres fonctions disponibles : `send_message`, `cancel_session`, `get_session_info`


---

##  Auteur

Projet conçu et développé par **Assia AIT TALEB**,
Stage ingénieur 4A - INSA Rouen Normandie - AMDIE (2025).

