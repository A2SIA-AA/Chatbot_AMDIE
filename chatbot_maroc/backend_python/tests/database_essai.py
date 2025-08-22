#!/usr/bin/env python3
"""
Script de test pour le système d'historique SQLite avec Keycloak
"""

import os
import sys
from datetime import datetime, timedelta

# Ajouter le path du projet
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ..src.core.memory_store import conversation_memory


def test_memory_system():
    """Test complet du système de mémoire"""

    print("🧪 Test du système d'historique SQLite")
    print("=" * 50)

    # Test 1: Vérification de la santé de la DB
    print("\n📊 1. Vérification de la santé de la base de données")
    health = conversation_memory.check_database_health()
    print(f"   Status: {health['status']}")
    print(f"   Chemin: {health['database_path']}")
    print(f"   Taille: {health.get('file_size_mb', 0)} MB")
    print(f"   Conversations total: {health.get('total_conversations', 0)}")

    # Test 2: Utilisateurs de test
    test_users = [
        ("admin_user", "admin@amdie.ma"),
        ("employee_user", "employee@amdie.ma"),
        ("public_user", "public@amdie.ma"),
        ("keycloak_john", "john.doe@amdie.ma"),
        ("keycloak_marie", "marie.dupont@amdie.ma")
    ]

    print("\n💬 2. Ajout de conversations de test")
    for i, (username, email) in enumerate(test_users):
        # Ajouter quelques conversations
        questions = [
            f"Quelle est la population de Rabat en {2023 - i}?",
            f"Combien d'étudiants en ingénierie à Casablanca?",
            f"Statistiques sur l'éducation au Maroc pour {username}",
            "Peux-tu me rappeler ma dernière question?",
            "Compare les données avec ce qu'on a vu avant"
        ]

        for j, question in enumerate(questions[:3]):  # Limiter à 3 par user
            reponse = f"Réponse automatique #{j + 1} pour {username}: Les données montrent que..."

            success = conversation_memory.save_conversation(
                username=username,
                email=email,
                question=question,
                reponse=reponse,
                session_id=f"test_session_{username}_{j}"
            )

            if success:
                print(f"   ✅ Conversation {j + 1} sauvegardée pour {username}")
            else:
                print(f"   ❌ Erreur pour {username}")

    # Test 3: Récupération de l'historique
    print("\n📜 3. Test de récupération d'historique")
    for username, email in test_users[:2]:  # Test sur 2 users
        print(f"\n   👤 Historique pour {username}:")

        # Stats
        stats = conversation_memory.get_conversation_stats(username, email)
        print(f"      Total: {stats['total_conversations']} conversations")
        print(f"      24h: {stats['conversations_24h']} conversations")

        # Historique récent
        history = conversation_memory.get_user_history_24h(username, email, limit=5)
        print(f"      Historique récupéré: {len(history)} éléments")

        # Contexte formaté
        context = conversation_memory.format_history_for_context(username, email, max_conversations=3)
        print(f"      Contexte généré: {len(context)} caractères")
        if len(context) > 100:
            print(f"      Aperçu: {context[:100]}...")

    # Test 4: Fonctionnalités admin
    print("\n🔧 4. Test des fonctionnalités admin")

    # Liste des utilisateurs
    all_users = conversation_memory.get_all_users()
    print(f"   👥 Utilisateurs dans la base: {len(all_users)}")
    for username, email in all_users[:5]:  # Afficher les 5 premiers
        print(f"      - {username} ({email})")

    # Export de données
    if all_users:
        username, email = all_users[0]
        export_data = conversation_memory.export_user_conversations(username, email)
        print(f"   📤 Export pour {username}: {len(export_data)} conversations")

    # Test 5: Simulation d'utilisation avec l'IA
    print("\n🤖 5. Simulation d'utilisation avec les agents IA")

    # Simuler une conversation avec historique
    test_username = "keycloak_test_user"
    test_email = "test@amdie.ma"

    # Conversation 1
    conversation_memory.save_conversation(
        username=test_username,
        email=test_email,
        question="Combien d'étudiants en ingénierie à Rabat?",
        reponse="D'après les données de 2023, Rabat compte environ 1,200 étudiants en ingénierie répartis dans 3 établissements principaux.",
        session_id="sim_session_1"
    )

    # Conversation 2 (avec référence à la précédente)
    conversation_memory.save_conversation(
        username=test_username,
        email=test_email,
        question="Et à Casablanca, c'est pareil?",
        reponse="Casablanca a un nombre plus élevé avec environ 1,800 étudiants en ingénierie, soit 600 de plus qu'à Rabat.",
        session_id="sim_session_2"
    )

    # Conversation 3 (référence historique)
    conversation_memory.save_conversation(
        username=test_username,
        email=test_email,
        question="Rappelle-moi les chiffres de Rabat de tout à l'heure",
        reponse="Comme mentionné précédemment, Rabat compte 1,200 étudiants en ingénierie. Pour comparaison, Casablanca en a 1,800.",
        session_id="sim_session_3"
    )

    # Récupérer le contexte pour l'IA
    context_for_ai = conversation_memory.format_history_for_context(test_username, test_email)
    print(f"   📝 Contexte IA généré: {len(context_for_ai)} caractères")
    print(f"   📋 Aperçu du contexte:\n{context_for_ai[:300]}...")

    # Test 6: Nettoyage (optionnel)
    print("\n🧹 6. Test de nettoyage (simulation)")

    # Simuler des conversations anciennes
    old_conversation = conversation_memory.save_conversation(
        username="old_user",
        email="old@amdie.ma",
        question="Question ancienne",
        reponse="Réponse ancienne",
        session_id="old_session"
    )

    print(f"   🗓️ Conversation ancienne créée: {old_conversation}")

    # NE PAS VRAIMENT NETTOYER pour garder les données de test
    print("   ⚠️ Nettoyage automatique désactivé pour préserver les données de test")

    # Résumé final
    print("\n" + "=" * 50)
    print("✅ Test du système d'historique terminé")

    final_health = conversation_memory.check_database_health()
    print(f"📊 État final:")
    print(f"   - Total conversations: {final_health.get('total_conversations', 0)}")
    print(f"   - Total utilisateurs: {final_health.get('total_users', 0)}")
    print(f"   - Conversations 24h: {final_health.get('conversations_24h', 0)}")
    print(f"   - Taille DB: {final_health.get('file_size_mb', 0)} MB")

    return True


def demo_historique_context():
    """Démo spécifique du contexte historique pour les agents"""

    print("\n🎭 DÉMO: Contexte historique pour les agents IA")
    print("=" * 50)

    # Créer un utilisateur démo
    demo_user = "demo_keycloak"
    demo_email = "demo@amdie.ma"

    # Supprimer l'historique existant
    conversation_memory.delete_user_conversations(demo_user, demo_email)

    # Simuler une série de conversations logiques
    conversations = [
        {
            "question": "Combien d'étudiants en ingénierie au Maroc?",
            "reponse": "Le Maroc compte environ 45,000 étudiants en ingénierie répartis dans 50 établissements. Les principales régions sont Rabat-Salé-Kénitra (12,000), Casablanca-Settat (15,000) et Fès-Meknès (8,000)."
        },
        {
            "question": "Et les pourcentages de femmes dans ces établissements?",
            "reponse": "La proportion de femmes étudiantes en ingénierie est de 35% au niveau national. Rabat-Salé-Kénitra affiche 38%, Casablanca-Settat 42%, et Fès-Meknès 31%."
        },
        {
            "question": "Quelle région a le taux le plus élevé?",
            "reponse": "D'après les données précédentes, Casablanca-Settat a le taux le plus élevé de femmes en ingénierie avec 42%, suivie de Rabat-Salé-Kénitra (38%) et Fès-Meknès (31%)."
        },
        {
            "question": "Compare ces chiffres avec les moyennes internationales",
            "reponse": "Les 42% de femmes à Casablanca sont au-dessus de la moyenne OCDE (35%). Le Maroc se positionne bien comparé à la France (27%) ou l'Allemagne (24%), mais reste en-dessous des pays nordiques comme la Finlande (50%)."
        }
    ]

    # Ajouter les conversations avec des délais simulés
    for i, conv in enumerate(conversations):
        success = conversation_memory.save_conversation(
            username=demo_user,
            email=demo_email,
            question=conv["question"],
            reponse=conv["reponse"],
            session_id=f"demo_session_{i + 1}"
        )

        if success:
            print(f"✅ Conversation {i + 1} ajoutée")

    # Maintenant simuler une nouvelle question qui fait référence à l'historique
    print("\n📝 Nouvelle question: 'Rappelle-moi le taux de Rabat qu'on a vu'")

    # Récupérer le contexte comme le ferait l'agent analyseur
    context = conversation_memory.format_history_for_context(demo_user, demo_email)

    print("\n📋 CONTEXTE QUI SERA ENVOYÉ AUX AGENTS IA:")
    print("-" * 50)
    print(context)
    print("-" * 50)

    # Simuler ce que l'agent ferait avec ce contexte
    print("\n🤖 RÉPONSE SIMULÉE DE L'AGENT (avec historique):")
    simulated_response = """D'après notre conversation précédente, le taux de femmes étudiantes en ingénierie 
à Rabat-Salé-Kénitra est de 38%. Pour rappel, cette région compte 12,000 étudiants en ingénierie au total, 
et se positionne en deuxième place après Casablanca-Settat (42%) mais devant Fès-Meknès (31%)."""

    print(simulated_response)

    print(f"\n✅ Démo terminée. L'historique permet à l'IA de répondre avec le contexte complet!")


def cleanup_test_data():
    """Nettoie les données de test (optionnel)"""
    print("\n🧹 Nettoyage des données de test")

    test_users = [
        ("admin_user", "admin@amdie.ma"),
        ("employee_user", "employee@amdie.ma"),
        ("public_user", "public@amdie.ma"),
        ("keycloak_john", "john.doe@amdie.ma"),
        ("keycloak_marie", "marie.dupont@amdie.ma"),
        ("keycloak_test_user", "test@amdie.ma"),
        ("demo_keycloak", "demo@amdie.ma"),
        ("old_user", "old@amdie.ma")
    ]

    total_deleted = 0
    for username, email in test_users:
        deleted = conversation_memory.delete_user_conversations(username, email)
        total_deleted += deleted
        if deleted > 0:
            print(f"   🗑️ {deleted} conversations supprimées pour {username}")

    print(f"\n✅ Nettoyage terminé: {total_deleted} conversations supprimées au total")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test du système d'historique SQLite")
    parser.add_argument("--demo", action="store_true", help="Lancer la démo du contexte historique")
    parser.add_argument("--cleanup", action="store_true", help="Nettoyer les données de test")
    parser.add_argument("--full", action="store_true", help="Test complet + démo + nettoyage")

    args = parser.parse_args()

    if args.full:
        test_memory_system()
        demo_historique_context()
        cleanup_test_data()
    elif args.demo:
        demo_historique_context()
    elif args.cleanup:
        cleanup_test_data()
    else:
        test_memory_system()

    print(f"\n🎯 Pour tester complètement: python {__file__} --full")
    print(f"🎭 Pour voir la démo: python {__file__} --demo")
    print(f"🧹 Pour nettoyer: python {__file__} --cleanup")