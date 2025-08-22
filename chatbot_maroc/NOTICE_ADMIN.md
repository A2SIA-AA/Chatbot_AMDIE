#  Notice Utilisateur – Profil Administrateur

## Objectif
Cette interface permet à un administrateur d’interroger le chatbot sur **l’ensemble des documents indexés**, y compris ceux marqués comme **confidentiels**.

---

##  Accès à la plateforme

- Connexion via **Keycloak** avec un compte ayant le rôle `admin`.
- Redirection immédiate vers l’interface de chat.
- Authentification sécurisée (token JWT signé via Keycloak).

---

##  Fonctionnalité

- Accès complet aux documents :
  - Publics
  - Internes
  - Confidentiels
- Les réponses tiennent compte du rôle administrateur.
- Possibilité de poser des questions avancées impliquant plusieurs niveaux de permission.

---

##  Interface

- Interface React / Next.js
- Interaction simple : une question à la fois

---

## ️ Sécurité et contrôle

- Le backend filtre automatiquement les documents vectorisés selon le niveau d’accès.
- Les dossiers (`data/admin/`, etc.) sont pris en compte dès l’indexation.

---

##  Compte administrateur Keycloak

- Utilisateur : `admin_user@domaine.com` 
- Rôle : `admin`
- Permissions :
  - `read_confidential_docs`, `chat_advanced`, `chat_admin`
  - `view_admin_stats`, `manage_users`, `upload_documents`, `delete_documents`

---

## Limites

- Pas de visualisation des documents vectorisés
- Pas de dashboard de gestion intégré dans cette version
