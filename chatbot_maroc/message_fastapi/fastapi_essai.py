#!/usr/bin/env python3
"""
Test complet de l'intégration FastAPI + MCP
"""

import requests
import json
import time
import sys

# Configuration
API_BASE = "http://localhost:8000"
TEST_USERS = {
    "public": {
        "email": "public@demo.ma",
        "password": "public123"
    },
    "employee": {
        "email": "salarie@amdie.ma",
        "password": "salarie123"
    },
    "admin": {
        "email": "admin@amdie.ma",
        "password": "admin123"
    }
}


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"🔍 {title}")
    print('=' * 60)


def test_api_health():
    """Test de santé de l'API"""
    print("🏥 Test de santé API...")

    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API: {data['status']}")
            print(f"✅ MCP: {data['services']['mcp']}")
            print(f"✅ Version: {data['version']}")
            return True
        else:
            print(f"❌ API erreur: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API non accessible: {e}")
        return False


def test_mcp_status():
    """Test du statut MCP"""
    print("\n🔗 Test statut MCP...")

    try:
        response = requests.get(f"{API_BASE}/mcp/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP connecté: {data['connected']}")
            if data['connected']:
                print(f"✅ Outils: {data['tools']}")
                print(f"✅ Transport: {data['transport']}")
                if data.get('health'):
                    print(f"✅ Santé: {data['health']['status']}")
            return data['connected']
        else:
            print(f"❌ Erreur statut MCP: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test MCP: {e}")
        return False


def test_mcp_simple():
    """Test simple MCP sans auth"""
    print("\n🧪 Test MCP simple...")

    try:
        response = requests.post(
            f"{API_BASE}/mcp/test",
            params={"question": "Test de connexion MCP"}
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Test MCP réussi")
                print(f"📝 Réponse: {data.get('answer', {}).get('answer', 'N/A')[:100]}...")
                return True
            else:
                print(f"❌ Test MCP échoué: {data.get('error')}")
                return False
        else:
            print(f"❌ Erreur HTTP test MCP: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test MCP simple: {e}")
        return False


def login_user(role="public"):
    """Connexion utilisateur"""
    print(f"\n🔐 Connexion {role}...")

    if role not in TEST_USERS:
        print(f"❌ Rôle {role} non configuré")
        return None

    try:
        response = requests.post(
            f"{API_BASE}/api/v1/auth/login",
            json=TEST_USERS[role]
        )

        if response.status_code == 200:
            data = response.json()
            token = data['access_token']
            user = data['user']
            print(f"✅ Connecté: {user['full_name']} ({user['role']})")
            print(f"✅ Permissions: {len(user['permissions'])} permissions")
            return token
        else:
            print(f"❌ Erreur connexion: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return None


def test_chat_mcp(token, role="public"):
    """Test du chat avec authentification"""
    print(f"\n💬 Test chat MCP ({role})...")

    if not token:
        print("❌ Pas de token pour le test")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Questions de test selon le rôle
    test_questions = {
        "public": "Qu'est-ce que l'AMDIE ?",
        "employee": "Quels sont les derniers projets d'investissement ?",
        "admin": "Statistiques détaillées sur les investissements"
    }

    question = test_questions.get(role, "Question de test")

    payload = {
        "question": question,
        "include_debug": False
    }

    try:
        print(f"📤 Question ({role}): {question}")
        start_time = time.time()

        response = requests.post(
            f"{API_BASE}/chat/ask",
            json=payload,
            headers=headers,
            timeout=60
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            if data['success']:
                answer = data['data'].get('answer', '')
                print(f"✅ Réponse reçue en {elapsed:.2f}s")
                print(f"📝 Réponse: {answer[:150]}...")
                print(f"👤 Utilisateur: {data['user']['username']} ({data['user']['role']})")
                print(f"🆔 Session: {data['session_id']}")
                return True
            else:
                print(f"❌ Erreur dans la réponse: {data}")
                return False
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            print(response.text)
            return False

    except requests.exceptions.Timeout:
        print("❌ Timeout - Le chatbot met trop de temps à répondre")
        return False
    except Exception as e:
        print(f"❌ Erreur chat: {e}")
        return False


def test_permissions(token, role):
    """Test des permissions"""
    print(f"\n🔐 Test permissions ({role})...")

    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{API_BASE}/api/v1/permissions/test",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Utilisateur: {data['user']} ({data['role']})")
            print(f"✅ Permissions: {data['permissions']}")
            print(f"✅ Peut lire public: {data['can_read_public']}")
            print(f"✅ Peut lire interne: {data['can_read_internal']}")
            print(f"✅ Peut chatter: {data['can_chat']}")
            return True
        else:
            print(f"❌ Erreur permissions: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test permissions: {e}")
        return False


def test_legacy_compatibility(token):
    """Test de compatibilité avec l'ancien endpoint"""
    print(f"\n🔄 Test compatibilité legacy...")

    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {"question": "Test compatibilité legacy"}

    try:
        response = requests.post(
            f"{API_BASE}/api/v1/start-processing",
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Legacy endpoint fonctionne")
            print(f"📝 Réponse: {data.get('response', '')[:100]}...")
            return True
        else:
            print(f"❌ Erreur legacy: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur test legacy: {e}")
        return False


def main():
    """Test complet"""
    print("🚀 TEST COMPLET INTÉGRATION FASTAPI + MCP")
    print("Version finale avec authentification complète")

    results = {}

    # 1. Santé de l'API
    print_section("TEST DE SANTÉ")
    if test_api_health():
        results["API Health"] = True
    else:
        print("\n❌ ARRÊT: API non accessible")
        return False

    # 2. Statut MCP
    print_section("TEST MCP")
    if test_mcp_status():
        results["MCP Status"] = True
    else:
        print("\n⚠️  MCP non connecté")
        return False

    # 3. Test MCP simple
    if test_mcp_simple():
        results["MCP Simple"] = True

    # 4. Tests par rôle utilisateur
    for role in ["public", "employee", "admin"]:
        print_section(f"TEST UTILISATEUR {role.upper()}")

        # Connexion
        token = login_user(role)
        if not token:
            continue

        # Permissions
        if test_permissions(token, role):
            results[f"Permissions {role}"] = True

        # Chat
        if test_chat_mcp(token, role):
            results[f"Chat {role}"] = True

        # Legacy (test uniquement pour public)
        if role == "public":
            if test_legacy_compatibility(token):
                results["Legacy compatibility"] = True

    # Résumé final
    print_section("RÉSULTATS FINAUX")

    print("📊 Tests réussis:")
    for test_name, passed in results.items():
        if passed:
            print(f"  ✅ {test_name}")

    failed_tests = [name for name, passed in results.items() if not passed]
    if failed_tests:
        print("\n⚠️  Tests échoués:")
        for test_name in failed_tests:
            print(f"  ❌ {test_name}")

    success_rate = len([r for r in results.values() if r]) / len(results) if results else 0

    print(f"\n📈 Taux de réussite: {success_rate:.1%} ({len([r for r in results.values() if r])}/{len(results)})")

    if success_rate >= 0.8:
        print("\n🎉 INTÉGRATION FONCTIONNELLE!")
        print("💡 Votre API FastAPI + MCP est opérationnelle")
        print("\n🔗 ENDPOINTS PRINCIPAUX:")
        print(f"📖 Documentation: {API_BASE}/docs")
        print(f"💬 Chat: POST {API_BASE}/chat/ask")
        print(f"🔍 MCP Status: GET {API_BASE}/mcp/status")
        print(f"🔐 Login: POST {API_BASE}/api/v1/auth/login")
        return True
    else:
        print("\n⚠️  Intégration partielle - corrigez les erreurs")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrompu")
        sys.exit(1)