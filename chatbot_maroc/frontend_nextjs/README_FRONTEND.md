# `chatbot_maroc/` — Frontend (Next.js) du Chatbot AMDIE

Ce dossier contient l’interface utilisateur du chatbot RAG développé à l’AMDIE. Conçu avec **Next.js**, **React**, **Tailwind CSS** et la bibliothèque **Shadcn/ui**, ce frontend assure une expérience fluide, moderne et responsive pour les utilisateurs.

---

## Objectif

L’interface permet aux utilisateurs :

* De **se connecter** via un bouton de redirection vers **Keycloak**
* De **poser des questions** au chatbot
* De **visualiser les messages d’attente** (progression du traitement)
* De recevoir une **réponse contextuelle**, enrichie des sources utilisées
* De visualiser leur **rôle** (`admin`, `salarie`, `public`) dans l’interface

---

##  Technologies utilisées

* **Next.js** (App Router)
* **React 18**
* **Tailwind CSS**
* **Shadcn/ui** (composants pré-stylés)
* **TypeScript**
* **JWT (via Keycloak)** pour l’authentification
* Appels API via `fetch` vers le serveur **FastAPI**

---

## Structure

| Dossier/Fichier      | Rôle principal                                                      |
| -------------------- | ------------------------------------------------------------------- |
| `app/page.tsx`       | Page principale contenant l’interface de chat                       |
| `app/layout.tsx`     | Mise en page globale de l’application                               |
| `components/`        | Composants React : `ChatBox`, `MessageBubble`, `ProgressBar`, etc.  |
| `public/`            | Ressources statiques (logos, favicons…)                             |

---

## Prérequis


* **Node.js** (v18 recommandé)
* **pnpm** ou **npm** ou **yarn**
* Une instance **Keycloak** opérationnelle
* L’URL de l’**API FastAPI** (lancée sur `localhost:8000` par défaut)


---

## Lancement rapide


### Démarrage en développement

```bash
npm run dev
```

Accessible sur : [http://localhost:3000](http://localhost:3000)

---

## Authentification

Le frontend s’appuie sur **Keycloak** pour sécuriser l’accès :

* Un **bouton “Se connecter”** est visible en page d’accueil
* Une fois connecté, l’utilisateur est redirigé vers la page principale de **chat**
* Le **token JWT** est automatiquement inclus dans les appels API pour que le backend filtre les données selon les permissions (`CONFIDENTIAL`, `PUBLIC`, etc.)

---

## Fonctionnement de l’interface

1. **Saisie de la question**

   * L’utilisateur entre une requête dans le champ prévu
2. **Appel à FastAPI**

   * Envoi de la requête contenant : question + rôle + token
3. **Affichage des messages d’attente**

   * Interface interactive avec des messages de progression
4. **Réponse finale**

   * Affichage de la réponse générée par le backend (Gemini)
   * Citations des sources (documents PDF, Excel…)


---

## Test

Actuellement, aucun test automatisé n’est intégré. Pour l’ajouter :

* `jest` pour les tests unitaires
* `cypress` pour les tests end-to-end

---

## Liens utiles

* Interface backend : `FastAPI` sur `http://localhost:8000/docs`
* Serveur MCP (backend IA) : `http://localhost:8090/mcp/`
* Keycloak Admin : `http://localhost:8080/admin/`

---

## Auteur

Projet conçu et développé par **Assia AIT TALEB**
Stage ingénieur – INSA Rouen Normandie – AMDIE (2025)

