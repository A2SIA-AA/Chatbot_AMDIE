# Chatbot AMDIE - Assistant IA avec contrôle d'accès

Ce dépôt contient un chatbot intelligent développé pour l’**Agence Marocaine de Développement des Investissements et des Exportations (AMDIE)**.

Le chatbot offre une interface web conversationnelle basée sur un modèle de langage (LLM) capable de :
- répondre à des questions sur des documents internes,
- tout en respectant les **droits d’accès** de l’utilisateur (`public`, `employé`, `admin`) grâce à un système **JWT** intégré.

---

## Architecture

```txt
Utilisateur (Next.js)
      |
      |---> FastAPI (auth, session, gestion des messages)
                        |
                        |---> Script Python backend (`chatbot_wrapper.py`)
                                    |
                                    |---> IA + RAG + ChromaDB (avec filtrage par droits JWT)
````

* **Frontend :** Interface React (Next.js)
* **Backend :** FastAPI (authentification, sessions, appels LLM)
* **IA :** backend séparé (`chatbot_wrapper.py`) intégrant un modèle de langage et RAG vectoriel (Chroma)
* **Stockage temporaire :** En mémoire (liste Python)

---

## Fonctionnalités principales

* Authentification sécurisée avec JWT (3 rôles)
* Lancement de sessions avec logs et ID persistants
* Traitement des questions via un backend IA isolé
* RAG vectorisé avec filtrage des documents selon les droits

---

## Rôles & Permissions

| Rôle    | Permissions                    | Accès                 |
| ------- | ------------------------------ | --------------------- |
| public  | `read_public_docs`             | Données publiques     |
| employé | `read_public_docs`, `employee` | Accès intermédiaire   |
| admin   | `read_all`, `admin`            | Plein accès (interne) |

---

##  Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/A2SIA-AA/Chatbot_AMDIE.git
cd Chatbot_AMDIE/chatbot_maroc
```

### 2. Backend (FastAPI)

```bash
pip install -r requirements.txt
cd message_fastapi
python main.py
```

### 3. Frontend (Next.js)

```bash
cd interface
npm install
npm run dev
```

---

## Variables d’environnement (`.env`)

À créer à la racine, prendre exemple sur le fichier .env.exemple

---

## Exemple d’utilisation

### Connexion (POST)

```bash
POST /api/v1/auth/login
{
  "username": "admin",
  "password": "admin123"
}
```

### Démarrage du traitement

```bash
POST /api/v1/start-processing
Authorization: Bearer <JWT>
{
  "message": "Quels sont les projets en cours ?"
}
```

---

## Principaux Endpoints FastAPI

| Méthode | Endpoint                   | Description                |
| ------- | -------------------------- | -------------------------- |
| POST    | `/api/v1/auth/login`       | Connexion JWT              |
| GET     | `/api/v1/auth/me`          | Infos utilisateur connecté |
| POST    | `/api/v1/messages`         | Ajout de message           |
| POST    | `/api/v1/start-processing` | Lancer le backend IA       |

---

## Backend IA (`chatbot_wrapper.py`)

Ce fichier est exécuté par FastAPI et contient :

* Vérification des permissions JWT
* Initialisation du RAG avec filtrage par rôle
* Exécution de la requête
* Envoi de messages à FastAPI (progression, logs, résultat final)

---

## Arborescence simplifiée

```
chatbot_maroc/
├── backend
│   └──  chatbot_wrapper.py    # Backend IA délégué
├── message_fastapi/           # Frontend React (Next.js)
│   └── main.py                # API FastAPI
│   └── auth.py                # Authentification & JWT
│   └── models.py              # Modèles Pydantic
│   └── message_store.py       # Stockage messages sessions   
├── interface/             # Frontend React (Next.js)
│   └── page.tsx
└── README.md
```

---

## Licence

Projet sous licence MIT - libre d’utilisation et de modification.

---

## Auteur

Projet développé dans le cadre d’un stage à l’AMDIE - par Assia AIT TALEB
Lien : [github.com/A2SIA-AA/Chatbot\_AMDIE](https://github.com/A2SIA-AA/Chatbot_AMDIE)
