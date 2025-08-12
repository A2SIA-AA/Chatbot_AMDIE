#!/usr/bin/env python3
"""
Script de test pour le chatbot AMDIE

Ce script permet de tester le chatbot en posant des questions directement
depuis la ligne de commande, sans avoir besoin de passer par l'interface web.

Usage:
    python questions_essai.py

Le script vous demandera ensuite de saisir votre question.
"""

import os
import sys
import json
import uuid
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Chemin vers le script chatbot_wrapper.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Import du module chatbot_wrapper
import chatbot_wrapper

def afficher_aide():
    """Affiche l'aide du script"""
    print("\n=== Test du Chatbot AMDIE ===")
    print("Commandes disponibles:")
    print("  !aide     - Affiche cette aide")
    print("  !quitter  - Quitte le programme")
    print("  !role     - Change le rôle utilisateur (public, employee, admin)")
    print("  !perms    - Change les permissions utilisateur")
    print("  !session  - Crée une nouvelle session")
    print("Sinon, entrez simplement votre question pour la poser au chatbot.\n")

def main():
    """Fonction principale du script de test"""
    # Configuration par défaut
    session_id = str(uuid.uuid4())
    user_role = "public"
    user_permissions = ["read_public_docs"]
    
    print("\n=== Test du Chatbot AMDIE ===")
    print(f"Session ID: {session_id}")
    print(f"Rôle: {user_role}")
    print(f"Permissions: {', '.join(user_permissions)}")
    print("Tapez !aide pour afficher les commandes disponibles")
    print("Tapez !quitter pour quitter")
    
    while True:
        try:
            # Demander la question à l'utilisateur
            question = input("\n> Votre question: ")
            
            # Traiter les commandes spéciales
            if question.lower() == "!quitter":
                print("Au revoir!")
                break
                
            elif question.lower() == "!aide":
                afficher_aide()
                continue
                
            elif question.lower() == "!role":
                nouveau_role = input("Nouveau rôle (public, employee, admin): ").strip().lower()
                if nouveau_role in ["public", "employee", "admin"]:
                    user_role = nouveau_role
                    print(f"Rôle changé pour: {user_role}")
                else:
                    print(f"Rôle invalide. Utilisation du rôle par défaut: {user_role}")
                continue
                
            elif question.lower() == "!perms":
                nouvelles_perms = input("Nouvelles permissions (séparées par des virgules): ").strip()
                if nouvelles_perms:
                    user_permissions = [p.strip() for p in nouvelles_perms.split(",") if p.strip()]
                    print(f"Permissions changées pour: {', '.join(user_permissions)}")
                else:
                    user_permissions = ["read_public_docs"]
                    print(f"Permissions réinitialisées: {', '.join(user_permissions)}")
                continue
                
            elif question.lower() == "!session":
                session_id = str(uuid.uuid4())
                print(f"Nouvelle session créée: {session_id}")
                continue
                
            # Si la question est vide, continuer
            if not question.strip():
                continue
                
            # Préparer les arguments pour le chatbot
            sys.argv = [
                "chatbot_wrapper.py",
                question,
                session_id,
                ",".join(user_permissions),
                user_role
            ]
            
            # Rediriger stdout pour capturer la sortie JSON
            original_stdout = sys.stdout
            from io import StringIO
            sys.stdout = StringIO()
            
            # Appeler le chatbot
            print(f"\nTraitement de la question avec rôle {user_role}...\n")
            chatbot_wrapper.main()
            
            # Récupérer et analyser la sortie
            output = sys.stdout.getvalue()
            sys.stdout = original_stdout
            
            try:
                result = json.loads(output)
                
                if result.get("success", False):
                    print("\n=== Réponse du chatbot ===")
                    print(result["response"])
                    print("\n=== Métadonnées ===")
                    print(f"Session: {result.get('session_id', 'N/A')}")
                    print(f"Rôle: {result.get('user_role', 'N/A')}")
                    print(f"Permissions: {', '.join(result.get('permissions_used', []))}")
                else:
                    print("\n=== Erreur ===")
                    print(f"Erreur: {result.get('error', 'Erreur inconnue')}")
            except json.JSONDecodeError:
                print("\n=== Erreur ===")
                print("Impossible de décoder la réponse JSON")
                print(f"Sortie brute: {output}")
                
        except KeyboardInterrupt:
            print("\nInterruption détectée. Au revoir!")
            break
        except Exception as e:
            print(f"\nErreur inattendue: {str(e)}")

if __name__ == "__main__":
    main()