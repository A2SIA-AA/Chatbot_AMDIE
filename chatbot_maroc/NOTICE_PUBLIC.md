#  Notice Utilisateur – Profil Public

##  Objectif
Cette interface permet à un utilisateur public d'accéder à un chatbot intelligent qui répond à des questions à partir de documents publics indexés automatiquement.

---

##  Accès à la plateforme

- L'accès se fait via **Keycloak** avec un compte dédié au rôle "public" 
\
(identifiant : `public_user`, mot de passe : `public123`).
- Une fois connecté, l'utilisateur est redirigé vers une interface de type chat.

---

##  Fonctionnalité

- L’utilisateur peut poser **une seule question à la fois**.
- Le chatbot répond uniquement à partir des **documents publics** (fichiers situés dans le dossier `data/public/`).
- Les réponses sont générées à partir d’une base de données vectorielle alimentée manuellement.

---

##  Interface

- Interface web développée avec **React / Next.js**.
- Gestion d’historique : Le chatbot a accès aux anciennes questions.
- Aucun accès à la configuration, aux statistiques ou aux documents sources.

---

##  Limitations

- **Aucun accès** aux documents internes ou confidentiels.
- **Aucune personnalisation** des résultats ou des options.

---

## Compte public Keycloak

- Utilisateur : `public_user`
- Mot de passe : `public123`
- Rôle : `public`
- Permissions : `read_public_docs`, `chat_basic`, `view_statistics`

