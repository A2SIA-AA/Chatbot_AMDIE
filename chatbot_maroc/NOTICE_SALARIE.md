#  Notice Utilisateur – Profil Salarié

##  Objectif
Cette interface permet à un salarié de poser des questions au chatbot et d’obtenir des réponses à partir de documents **publics et internes**.

---

##  Accès à la plateforme

- Connexion via **Keycloak** avec un compte salarié.
- Redirection automatique vers l’interface de chat.

---

##  Fonctionnalité

- L’utilisateur peut poser des questions sur des **documents internes et publics**.
- Les permissions permettent des réponses plus riches que le public, selon le rôle et les métadonnées de documents.
- Le backend filtre automatiquement les documents selon les droits d’accès.

---

##  Interface

- Interface web (React / Next.js).
- Pas d’historique visible pour l’utilisateur.

---

##  Limitations

- Aucune modification des données.
- Aucune gestion d'utilisateurs.
- Aucune visualisation directe de tableaux, logs ou fichiers.

---

## Compte salarié Keycloak

- Utilisateur : `salarie_user`
- Mot de passe : `salarie123`
- Rôle : `employee`
- Permissions : `read_internal_docs`, `chat_basic`, `chat_advanced`, `view_internal_stats`, `download_reports`

