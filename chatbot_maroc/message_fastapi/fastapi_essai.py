#!/usr/bin/env python3
"""
Test final pour vérifier que la correction Pydantic fonctionne
"""
import asyncio
import sys
import time
import requests

# Ajouter le chemin vers mcp_client_utils
sys.path.append('/home/aissa/Bureau/Projet_Chatbot/Chatbot_AMDIE/chatbot_maroc/message_fastapi')


async def test_final_fix():
    """Test final après correction Pydantic"""
    print("=== TEST FINAL ===\n")

    try:
        from mcp_client_utils import mcp_send_progress, mcp_send_final
        print(" Import MCP réussi")

    except ImportError as e:
        print(f" Erreur import MCP: {e}")
        return False

    # Session de test
    test_session_id = f"test_final_fix_{int(time.time())}"
    print(f"Session de test: {test_session_id}")

    try:
        # 1. Envoyer via MCP
        print("\n1. Envoi messages via MCP...")

        progress_result = await mcp_send_progress(test_session_id, "Message de progression - Test final")
        print(f"MCP progress: {progress_result.get('ok', False)}")

        final_result = await mcp_send_final(test_session_id, "Réponse finale du chatbot - Test réussi !")
        print(f"MCP final: {final_result.get('ok', False)}")

        # 2. Vérifier via FastAPI
        print("\n2. Vérification via FastAPI...")

        await asyncio.sleep(1)

        response = requests.get(f"http://localhost:8000/api/v1/messages/{test_session_id}")
        print(f"FastAPI status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f" Messages récupérés via FastAPI: {data['messageCount']}")

            if data['messageCount'] > 0:
                print("\nMessages détaillés:")
                for i, msg in enumerate(data['messages']):
                    print(f"  {i + 1}. [{msg['type']}] {msg['content']}")

                # Chercher le message final
                final_messages = [msg for msg in data['messages'] if msg['type'] == 'final']
                if final_messages:
                    print("\n MESSAGE FINAL TROUVÉ VIA FASTAPI!")
                    print(f"Contenu: {final_messages[0]['content']}")
                    print("\n SUCCÈS COMPLET !")
                    print(" MCP → MessageStore → FastAPI → Frontend")
                    print(" Toute la chaîne de communication fonctionne !")
                    return True
                else:
                    print("\n️ Message final manquant")
            else:
                print("\n Aucun message trouvé")
        elif response.status_code == 500:
            print(f" Erreur serveur FastAPI: {response.text}")
            print("️ Il reste un problème de sérialisation")
        else:
            print(f" Erreur FastAPI {response.status_code}: {response.text}")

        return False

    except Exception as e:
        print(f" Erreur test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_direct_message_store():
    """Test direct du MessageStore corrigé"""
    print("\n=== TEST DIRECT MESSAGE STORE ===\n")

    try:
        from message_store import MessageStore

        store = MessageStore()
        test_session = "test_direct_store"

        # Ajouter un message
        await store.add_message(test_session, {
            'type': 'progress',
            'content': 'Test message store direct',
            'metadata': {'source': 'test_direct'}
        })

        # Récupérer les messages
        messages = await store.get_messages(test_session)

        print(f"Messages récupérés: {len(messages)}")

        if len(messages) > 0:
            msg = messages[0]
            print(f"Type du message: {type(msg)}")

            if isinstance(msg, dict):
                print(" MessageStore retourne des dictionnaires")
                print(f"Contenu: {msg}")
                return True
            else:
                print(f" MessageStore retourne {type(msg)} au lieu de dict")
        else:
            print(" Aucun message récupéré")

        return False

    except Exception as e:
        print(f" Erreur test direct: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("Démarrage test final...\n")

    # Test 1: MessageStore direct
    direct_success = await test_direct_message_store()

    if direct_success:
        # Test 2: Chaîne complète MCP → FastAPI
        complete_success = await test_final_fix()

        if complete_success:
            print("\n" + "=" * 50)
            print(" TOUS LES TESTS RÉUSSIS !")
            print(" Vous pouvez maintenant tester avec une vraie question !")
            print(" L'interface web devrait afficher les réponses du chatbot")
            print("=" * 50)
        else:
            print("\n⚠ MessageStore OK mais chaîne complète échouée")
            print("Vérifiez que FastAPI est redémarré avec le nouveau message_store.py")
    else:
        print("\n Problème dans MessageStore - Vérifiez la correction")

    print("\n=== FIN TEST FINAL ===")


if __name__ == "__main__":
    asyncio.run(main())