#!/usr/bin/env python3
"""
Script de test pour FastMCP
"""
import asyncio
import requests
import json
from mcp_client_utils import mcp_health, mcp_start_backend


async def test_fastmcp():
    """Test FastMCP avec les bons endpoints"""

    print("=== TEST FASTMCP ===\n")

    # 1. Test de base - vérifier que le serveur répond
    print("1. Test endpoint MCP de base...")
    try:
        response = requests.get("http://localhost:8090/mcp", timeout=5)
        print(f"    Serveur FastMCP répond: {response.status_code}")
        print(f"    Headers: {dict(response.headers)}")

        # 406 ou 307 est normal pour un endpoint WebSocket/SSE
        if response.status_code in [406, 307]:
            print("  Réponse normale pour endpoint WebSocket/SSE")

    except requests.exceptions.ConnectionError:
        print("    Serveur FastMCP non accessible sur http://localhost:8090/mcp")
        return False
    except Exception as e:
        print(f"    Erreur: {e}")
        return False

    # 2. Test MCP Health via client
    print("\n2. Test MCP Health via client...")
    try:
        health_result = await mcp_health()
        print(f"    MCP Health: {json.dumps(health_result, indent=2)}")
    except Exception as e:
        print(f"    Erreur MCP Health: {e}")
        print(f"    Type erreur: {type(e)}")
        import traceback
        print(f"    Traceback: {traceback.format_exc()}")
        return False

    # 3. Test start_backend
    print("\n3. Test start_backend...")
    try:
        result = await mcp_start_backend(
            question="Test question FastMCP",
            session_id="test_fastmcp_123",
            permissions_csv="read_public_docs,chat_basic",
            role="public",
            username="public",
            email="public@test.com"
        )
        print(f"    start_backend: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"    Erreur start_backend: {e}")
        print(f"    Type erreur: {type(e)}")
        import traceback
        print(f"    Traceback: {traceback.format_exc()}")
        return False

    return True


# Test basique des endpoints
def test_endpoints():
    """Test des endpoints disponibles"""
    endpoints = [
        ("FastMCP", "http://localhost:8090/mcp"),
        ("FastAPI", "http://localhost:8000/health"),
    ]

    print("=== TEST ENDPOINTS ===\n")

    results = {}
    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=3)
            print(f" {name:10} {url} -> {response.status_code}")
            results[name] = response.status_code
        except requests.exceptions.ConnectionError:
            print(f" {name:10} {url} -> Connexion refusée")
            results[name] = "Connexion refusée"
        except Exception as e:
            print(f"️  {name:10} {url} -> {e}")
            results[name] = str(e)

    return results


async def main():
    """Test principal"""
    print(" Test FastMCP corrigé...\n")

    # Test basique
    endpoint_results = test_endpoints()

    # Vérifier que FastAPI tourne
    if endpoint_results.get("FastAPI") == "Connexion refusée":
        print("\n⚠  ATTENTION: FastAPI n'est pas démarré !")
        print("   Lancez FastAPI avant de continuer:")
        print("   python main.py")
        print()

    # Test FastMCP si le serveur répond
    if endpoint_results.get("FastMCP") not in ["Connexion refusée"]:
        print("\n" + "=" * 50 + "\n")
        success = await test_fastmcp()

        if success:
            print("\n Tous les tests FastMCP réussis !")
        else:
            print("\n Échec des tests FastMCP")
    else:
        print("\n Serveur FastMCP non accessible")


if __name__ == "__main__":
    asyncio.run(main())