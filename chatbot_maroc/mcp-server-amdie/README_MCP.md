Voici le **README.md** complet et personnalisé pour le dossier `mcp-server-amdie/`, conforme à ton architecture actuelle et ton fonctionnement réel :

---

## 📁 `mcp-server-amdie/` – Serveur MCP pour le lancement du backend

Ce module contient le **serveur MCP** utilisé pour déclencher dynamiquement le backend du chatbot à chaque nouvelle requête utilisateur. Il constitue le **point central d’orchestration** entre l’interface, l’API REST et les outils d’intelligence artificielle embarqués dans le backend.

---

## 🎯 Objectif

* Recevoir une requête de l’API (question, session, rôle, permissions).
* **Lancer dynamiquement le backend** du chatbot via la fonction `start_backend`.
* Transmettre la réponse finale à l’API FastAPI via requête HTTP.
* Servir de **connecteur central** entre le LLM, la base vectorielle, et les rôles d’utilisateurs.

---

## ⚙️ Fichiers principaux

| Fichier                      | Rôle                                                                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| `mcp_backend_server.py`      | Contient la configuration du serveur MCP et la fonction `start_backend`.                  |
| `serveur.json`               | Fichier de configuration (manuel ou par test), utilisé éventuellement par MCP Instructor. |
| `pyproject.toml` / `uv.lock` | Fichiers de gestion des dépendances.                                                      |
| `__init__.py`                | Initialisation du module.                                                                 |

---

## 🚀 Détails techniques

### Démarrage du serveur MCP

Le serveur utilise le protocole `Streamable-HTTP` et s’expose à :

```
http://0.0.0.0:8090/mcp/
```

Le lancement est fait dans `mcp_backend_server.py` avec :

```python
mcp.run(transport="http", host="0.0.0.0", port=8090, path="/mcp/")
```

---

### Fonction de lancement du backend

```python
async def start_backend(question: str, session_id: str, permissions_csv: str, role: str, username: str, email: str)
```

* Appelle la fonction `_spawn_wrapper(...)` du backend.
* Cette fonction démarre le traitement LangGraph à la volée pour la session.
* Retourne la réponse formatée, accompagnée des messages intermédiaires.

---

## 🔄 Communication

* Le **frontend** appelle l’API (FastAPI).
* L’**API** appelle le serveur **MCP** via HTTP.
* Le serveur **MCP** appelle le **backend** (`chatbot_wrapper.py`).
* La réponse est renvoyée à l’**API**, puis affichée à l’utilisateur.

Tous les échanges sont **redirigés via le MCP** : aucun composant n'appelle directement le backend.

---

## 🧪 Mode test

Il est possible d'utiliser MCP Instructor pour simuler des appels au serveur, en se basant sur la configuration `serveur.json`.

---

Souhaites-tu que je passe maintenant au **README du backend (`backend_python/`)** ?
