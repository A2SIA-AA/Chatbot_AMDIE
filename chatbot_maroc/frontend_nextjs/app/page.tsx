"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import {
  Loader, Send, Bot, User, Ellipsis, Server, Trash2,
  LogOut, Shield, UserCheck, Key
} from "lucide-react"

// ========================================
// INTERFACES TYPESCRIPT
// ========================================

interface User {
  username: string
  email: string
  role: 'public' | 'employee' | 'admin'
  permissions: string[]
  full_name: string
  department: string
}

interface LoginResponse {
  access_token: string
  token_type: string
  user: User
  expires_in: number
}

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  isProgress?: boolean
  messageId?: string
  userRole?: string
}

interface Session {
  sessionId: string | null
  isActive: boolean
  lastTimestamp: number
  userRole?: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

// ========================================
// COMPOSANT DE CONNEXION KEYCLOAK
// ========================================

const KeycloakLoginForm = ({ onLogin, isLoading }) => {
  const [loginError, setLoginError] = useState("")
  const [isConnecting, setIsConnecting] = useState(false)

  const FASTAPI_BASE_URL = "http://localhost:8000"

  // Gérer le callback Keycloak
  useEffect(() => {
    const handleKeycloakCallback = async () => {
      const urlParams = new URLSearchParams(window.location.search)
      const code = urlParams.get('code')
      const error = urlParams.get('error')

      if (error) {
        setLoginError(`Erreur Keycloak: ${error}`)
        // Nettoyer l'URL
        window.history.replaceState({}, document.title, window.location.pathname)
        return
      }

      if (code) {
        // Vérifier si on a déjà traité ce code (éviter la double exécution)
        const processedCode = sessionStorage.getItem('processed_keycloak_code')
        if (processedCode === code) {
          console.log('️ Code déjà traité, ignore...')
          window.history.replaceState({}, document.title, window.location.pathname)
          return
        }

        setIsConnecting(true)

        try {
          console.log(" Échange du code Keycloak...")

          // Marquer le code comme traité
          sessionStorage.setItem('processed_keycloak_code', code)

          const response = await fetch(`${FASTAPI_BASE_URL}/api/v1/auth/keycloak/callback`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              code: code,
              redirect_uri: window.location.origin + window.location.pathname
            })
          })

          if (!response.ok) {
            const errorData = await response.json()

            // Si le code est invalide, c'est probablement une réutilisation
            if (errorData.detail && errorData.detail.includes('Code invalide')) {
              setLoginError('Code de connexion expiré. Veuillez vous reconnecter.')
              // Nettoyer et permettre une nouvelle tentative
              sessionStorage.removeItem('processed_keycloak_code')
            } else {
              throw new Error(errorData.detail || 'Erreur callback Keycloak')
            }
            return
          }

          const data: LoginResponse = await response.json()

          // Stocker le token Keycloak
          localStorage.setItem('amdie_token', data.access_token)
          localStorage.setItem('amdie_user', JSON.stringify(data.user))
          localStorage.setItem('amdie_auth_type', 'keycloak')

          console.log(` Connexion Keycloak réussie: ${data.user.full_name} (${data.user.role})`)

          // Nettoyer l'URL et le code traité
          window.history.replaceState({}, document.title, window.location.pathname)
          sessionStorage.removeItem('processed_keycloak_code')

          onLogin(data)

        } catch (error) {
          console.error(' Erreur callback Keycloak:', error)
          setLoginError(error instanceof Error ? error.message : 'Erreur de connexion Keycloak')
          // Nettoyer en cas d'erreur
          window.history.replaceState({}, document.title, window.location.pathname)
          sessionStorage.removeItem('processed_keycloak_code')
        } finally {
          setIsConnecting(false)
        }
      }
    }

    handleKeycloakCallback()
  }, [onLogin])

  const handleKeycloakLogin = async () => {
    setIsConnecting(true)
    setLoginError("")

    try {
      console.log(" Récupération URL Keycloak...")

      const redirectUri = window.location.origin + window.location.pathname
        const response = await fetch(
  `${FASTAPI_BASE_URL}/api/v1/auth/keycloak/login-url?redirect_uri=${encodeURIComponent(redirectUri)}`
        )


      if (!response.ok) {
        throw new Error('Erreur récupération URL Keycloak')
      }

      const data = await response.json()
      console.log(" Redirection vers Keycloak...")

      // Rediriger vers Keycloak
      window.location.href = data.auth_url

    } catch (error) {
      console.error(' Erreur login Keycloak:', error)
      setLoginError(error instanceof Error ? error.message : 'Erreur de connexion')
      setIsConnecting(false)
    }
  }

  const testConnection = async () => {
    try {
      const response = await fetch(`${FASTAPI_BASE_URL}/health`)
      const data = await response.json()
      alert(` Connexion API: ${data.status}`)
    } catch (error) {
      alert(" API non accessible")
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-6 bg-white/90 backdrop-blur-sm">
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="flex justify-center mb-3">
            <img
              src="/amdie.png"
              alt="Logo AMDIE"
              className="w-64 h-auto"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                target.parentElement!.innerHTML = `
                  <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-green-500 rounded-lg shadow-lg flex items-center justify-center">
                    <span class="text-white font-bold text-lg">AMDIE</span>
                  </div>
                `;
              }}
            />
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">
             Connexion Sécurisée
          </h1>
          <p className="text-gray-600 text-sm">
            Assistant IA avec authentification Keycloak
          </p>
        </div>

        {/* Bouton de connexion Keycloak */}
        <div className="space-y-4">
          <Button
            onClick={handleKeycloakLogin}
            className="w-full h-12 bg-gradient-to-r from-blue-600 to-green-600 hover:from-blue-700 hover:to-green-700"
            disabled={isConnecting || isLoading}
          >
            {isConnecting ? (
              <>
                <Loader className="w-5 h-5 mr-2 animate-spin" />
                Connexion en cours...
              </>
            ) : (
              <>
                <Key className="w-5 h-5 mr-2" />
                Se connecter avec Keycloak
              </>
            )}
          </Button>

          {loginError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 text-red-700 text-sm">
               {loginError}
            </div>
          )}
        </div>

        {/* Informations sur les rôles */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-3 text-center">
             Rôles disponibles sur Keycloak
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between p-2 bg-blue-50 rounded">
              <span className="font-medium text-blue-800">public-user</span>
              <span className="text-blue-600">Accès données publiques</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-green-50 rounded">
              <span className="font-medium text-green-800">amdie-employee</span>
              <span className="text-green-600">Accès données internes</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-purple-50 rounded">
              <span className="font-medium text-purple-800">amdie-admin</span>
              <span className="text-purple-600">Accès complet</span>
            </div>
          </div>
        </div>

        {/* Test de connexion */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <Button
            onClick={testConnection}
            variant="outline"
            size="sm"
            className="w-full"
          >
            <Server className="w-4 h-4 mr-2" />
            Tester la connexion API
          </Button>
        </div>
      </Card>
    </div>
  )
}

// ========================================
// COMPOSANT PRINCIPAL AVEC KEYCLOAK
// ========================================

export default function ChatbotMarocPage() {
  // États d'authentification
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true
  })

  // États existants du chat
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [session, setSession] = useState<Session>({
    sessionId: null,
    isActive: false,
    lastTimestamp: 0
  })

  const FASTAPI_BASE_URL = "http://localhost:8000"

  // Vérification du token au chargement
  useEffect(() => {
    const checkAuthStatus = async () => {
      // Vérifier si on revient d'un logout Keycloak
      const urlParams = new URLSearchParams(window.location.search)
      const isLogout = urlParams.get('logout')

      if (isLogout) {
        console.log('🔄 Retour après logout Keycloak détecté')
        // Nettoyer l'URL
        window.history.replaceState({}, document.title, window.location.pathname)
        // Forcer l'état de déconnexion
        setAuthState({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false
        })
        return
      }

      const token = localStorage.getItem('amdie_token')
      const userStr = localStorage.getItem('amdie_user')
      const authType = localStorage.getItem('amdie_auth_type') || 'classic'

      if (token && userStr) {
        try {
          const user = JSON.parse(userStr)

          // Choisir le bon endpoint selon le type d'auth
          const endpoint = authType === 'keycloak'
            ? `${FASTAPI_BASE_URL}/api/v1/auth/keycloak/me`
            : `${FASTAPI_BASE_URL}/api/v1/auth/me`

          // Vérifier la validité du token
          const response = await fetch(endpoint, {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          })

          if (response.ok) {
            const currentUser = await response.json()
            setAuthState({
              user: currentUser,
              token,
              isAuthenticated: true,
              isLoading: false
            })
            console.log(`✅ Session ${authType} restaurée: ${currentUser.full_name}`)
          } else {
            // Token expiré ou invalide
            localStorage.removeItem('amdie_token')
            localStorage.removeItem('amdie_user')
            localStorage.removeItem('amdie_auth_type')
            setAuthState(prev => ({ ...prev, isLoading: false }))
          }
        } catch (error) {
          console.error('❌ Erreur vérification token:', error)
          localStorage.removeItem('amdie_token')
          localStorage.removeItem('amdie_user')
          localStorage.removeItem('amdie_auth_type')
          setAuthState(prev => ({ ...prev, isLoading: false }))
        }
      } else {
        setAuthState(prev => ({ ...prev, isLoading: false }))
      }
    }

    checkAuthStatus()
  }, [])

  // Gestion de la connexion
  const handleLogin = (loginResponse: LoginResponse) => {
    setAuthState({
      user: loginResponse.user,
      token: loginResponse.access_token,
      isAuthenticated: true,
      isLoading: false
    })
  }

  // Gestion de la déconnexion
  const handleLogout = async () => {
    const authType = localStorage.getItem('amdie_auth_type') || 'classic'

    if (authType === 'keycloak') {
      console.log(' Déconnexion Keycloak locale...')

      // Nettoyage immédiat
      localStorage.removeItem('amdie_token')
      localStorage.removeItem('amdie_user')
      localStorage.removeItem('amdie_auth_type')
      sessionStorage.clear()

      // Mise à jour de l'état React immédiatement
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false
      })

      // Reset du chat
      setMessages([])
      setSession({ sessionId: null, isActive: false, lastTimestamp: 0 })
      setIsLoading(false)

      console.log(' Déconnexion locale réussie')
      return
    }

    // Déconnexion classique
    try {
      await fetch(`${FASTAPI_BASE_URL}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authState.token}`
        }
      })
    } catch (error) {
      console.error(' Erreur déconnexion API:', error)
    }

    // Nettoyer le localStorage et l'état pour auth classique
    localStorage.removeItem('amdie_token')
    localStorage.removeItem('amdie_user')
    localStorage.removeItem('amdie_auth_type')

    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false
    })

    // Reset du chat
    setMessages([])
    setSession({ sessionId: null, isActive: false, lastTimestamp: 0 })
    setIsLoading(false)

    console.log(' Déconnexion classique réussie')
  }

  // Fonction d'envoi de message avec authentification
  const sendMessage = async (message: string) => {
    if (!message.trim() || isLoading || !authState.isAuthenticated) return

    const userMessage: Message = {
      role: 'user',
      content: message.trim(),
      timestamp: new Date(),
      messageId: generateMessageId(),
      userRole: authState.user?.role
    }

    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    try {
      console.log(` Envoi question avec rôle: ${authState.user?.role}`)

      // Utiliser l'endpoint Keycloak si c'est une session Keycloak
      const authType = localStorage.getItem('amdie_auth_type') || 'classic'
      const endpoint = authType === 'keycloak'
        ? `${FASTAPI_BASE_URL}/api/v1/start-processing-keycloak`
        : `${FASTAPI_BASE_URL}/api/v1/start-processing`

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'Authorization': `Bearer ${authState.token}`
        },
        body: JSON.stringify({ question: message.trim() }),
        mode: 'cors'
      })

      if (!response.ok) {
        if (response.status === 401) {
          // Token expiré, forcer la déconnexion
          handleLogout()
          throw new Error("Session expirée, veuillez vous reconnecter")
        } else if (response.status === 403) {
          throw new Error("Permission insuffisante pour cette action")
        }
        const errorText = await response.text()
        throw new Error(`Erreur API ${response.status}: ${errorText}`)
      }

      const data = await response.json()
      const { sessionId } = data

      console.log(`✅ Session démarrée: ${sessionId} pour ${authState.user?.role}`)

      setSession({
        sessionId,
        isActive: true,
        lastTimestamp: 0,
        userRole: authState.user?.role
      })

      startPolling(sessionId)

    } catch (error) {
      console.error("❌ Erreur envoi:", error)
      const errorMessage: Message = {
        role: 'assistant',
        content: `❌ ${error instanceof Error ? error.message : 'Erreur inconnue'}`,
        timestamp: new Date(),
        messageId: generateMessageId()
      }
      setMessages(prev => [...prev, errorMessage])
      setIsLoading(false)
    }
  }

  // Fonction utilitaire
  const generateMessageId = () => `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`

  // Polling (identique à la version existante)
  const startPolling = (sessionId: string) => {
    let lastTimestamp = 0
    let isFinished = false
    let pollCount = 0
    const maxPolls = 300

    const pollMessages = async () => {
      if (isFinished || pollCount > maxPolls) {
        setIsLoading(false)
        return
      }

      pollCount++

      try {
        const pollResponse = await fetch(
          `${FASTAPI_BASE_URL}/api/v1/messages/${sessionId}?since=${lastTimestamp}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authState.token}`
            },
            mode: 'cors'
          }
        )

        if (!pollResponse.ok) {
          if (pollResponse.status === 404) {
            setTimeout(pollMessages, 1000)
            return
          }
          setTimeout(pollMessages, 2000)
          return
        }

        const data = await pollResponse.json()
        const { messages: newMessages, timestamp } = data

        if (newMessages && newMessages.length > 0) {
          const reallyNewMessages = newMessages.filter((msg: any) => msg.timestamp > lastTimestamp)

          if (reallyNewMessages.length > 0) {
            for (const msg of reallyNewMessages) {
              const messageContent = msg.content
              const messageType = msg.type
              const messageTimestamp = new Date(msg.timestamp * 1000)

              if (messageType === 'progress' || messageType === 'agent_result') {
                setMessages(prev => {
                  const withoutProgress = prev.filter(m => m.messageId !== 'PROGRESS_MESSAGE')
                  const newProgressMessage: Message = {
                    role: 'system',
                    content: messageContent,
                    timestamp: messageTimestamp,
                    isProgress: true,
                    messageId: 'PROGRESS_MESSAGE',
                    userRole: authState.user?.role
                  }
                  return [...withoutProgress, newProgressMessage]
                })
              } else {
                const newMessage: Message = {
                  role: messageType === 'final' ? 'assistant' : 'assistant',
                  content: messageContent,
                  timestamp: messageTimestamp,
                  messageId: generateMessageId(),
                  userRole: authState.user?.role
                }

                setMessages(prev => {
                  const withoutProgress = prev.filter(m => m.messageId !== 'PROGRESS_MESSAGE')
                  return [...withoutProgress, newMessage]
                })

                if (messageType === 'final' || messageType === 'error') {
                  isFinished = true
                  setSession(prev => ({ ...prev, isActive: false }))
                  setIsLoading(false)
                  return
                }
              }
            }

            const latestTimestamp = Math.max(...reallyNewMessages.map((msg: any) => msg.timestamp))
            lastTimestamp = latestTimestamp
            setSession(prev => ({ ...prev, lastTimestamp: latestTimestamp }))
          }
        }

        if (!isFinished) {
          setTimeout(pollMessages, 1000)
        }

      } catch (error) {
        console.error("❌ Erreur polling:", error)
        if (!isFinished) {
          setTimeout(pollMessages, 2000)
        }
      }
    }

    setTimeout(pollMessages, 500)

    setTimeout(() => {
      if (!isFinished) {
        isFinished = true
        setIsLoading(false)
        const timeoutMessage: Message = {
          role: 'assistant',
          content: ' Le traitement prend trop de temps. Veuillez réessayer.',
          timestamp: new Date(),
          messageId: generateMessageId()
        }
        setMessages(prev => [...prev, timeoutMessage])
      }
    }, 300000)
  }

  // Suggestions adaptées au rôle utilisateur
  const getRoleSuggestions = () => {
    const baseSuggestions = [
      "Qu'est-ce qu'un ingénieur selon les définitions disponibles ?",
    ]

    if (authState.user?.role === 'public') {
      return [
        ...baseSuggestions,
        "Quelles sont les informations publiques sur l'éducation au Maroc ?"
      ]
    } else if (authState.user?.role === 'employee') {
      return [
        ...baseSuggestions,
        "Montrez-moi les statistiques internes sur nos projets",
        "Quelles sont les données confidentielles accessibles ?"
      ]
    } else if (authState.user?.role === 'admin') {
      return [
        ...baseSuggestions,
        "Analyse complète des données avec accès administrateur",
        "Rapport détaillé incluant toutes les données confidentielles"
      ]
    }

    return baseSuggestions
  }

  // Nettoyage du chat
  const clearChat = async () => {
    if (session.sessionId) {
      try {
        await fetch(`${FASTAPI_BASE_URL}/api/v1/messages/${session.sessionId}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authState.token}`
          },
          mode: 'cors'
        })
      } catch (err) {
        console.error("❌ Erreur nettoyage session:", err)
      }
    }

    setMessages([])
    setSession({ sessionId: null, isActive: false, lastTimestamp: 0 })
    setIsLoading(false)
  }

  // Handlers d'événements
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion)
  }

  // Test de connexion
  const testConnection = async () => {
    try {
      const response = await fetch(`${FASTAPI_BASE_URL}/health`, { mode: 'cors' })
      const data = await response.json()
      alert(`✅ Connexion API: ${data.status}`)
    } catch (error) {
      alert("❌ API non accessible")
    }
  }

  // Fonction pour obtenir la couleur du rôle
  const getRoleColor = (role: string) => {
    switch (role) {
      case 'public': return 'bg-blue-100 text-blue-800'
      case 'employee': return 'bg-green-100 text-green-800'
      case 'admin': return 'bg-purple-100 text-purple-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  // Loading state
  if (authState.isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50 flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-8 h-8 animate-spin mx-auto mb-4" />
          <p>Vérification de la session...</p>
        </div>
      </div>
    )
  }

  // Si non authentifié, afficher le formulaire de connexion Keycloak
  if (!authState.isAuthenticated) {
    return <KeycloakLoginForm onLogin={handleLogin} isLoading={authState.isLoading} />
  }

  // Interface principale avec utilisateur connecté
  const authType = localStorage.getItem('amdie_auth_type') || 'classic'

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50">
      <div className="container mx-auto p-4 h-screen flex flex-col max-w-4xl">

        {/* Logo AMDIE */}
        <div className="text-center mb-4">
          <div className="flex justify-center mb-2">
            <img
              src="/amdie.png"
              alt="Logo AMDIE"
              className="w-64 h-auto"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                target.parentElement!.innerHTML = `
                  <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-green-500 rounded-lg shadow-lg flex items-center justify-center">
                    <span class="text-white font-bold text-sm">AMDIE</span>
                  </div>
                `;
              }}
            />
          </div>
        </div>

        {/* Header avec info utilisateur */}
        <div className="mb-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            {/* Info utilisateur */}
            <div className="flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-green-600" />
              <span className="text-sm font-medium text-gray-700">
                {authState.user?.full_name}
              </span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${getRoleColor(authState.user?.role || '')}`}>
                {authState.user?.role?.toUpperCase()}
              </span>
              {authType === 'keycloak' && (
                <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-medium">
                  KEYCLOAK
                </span>
              )}
            </div>

            {/* Info session */}
            <div className="text-xs text-gray-500">
              {session.sessionId ? (
                <span className="flex items-center gap-1">
                  <div className={`w-2 h-2 rounded-full ${session.isActive ? 'bg-green-500' : 'bg-gray-400'}`} />
                  Session: {session.sessionId.substring(0, 20)}...
                </span>
              ) : (
                <span>Pas de session active</span>
              )}
            </div>
          </div>

          {/* Contrôles */}
          <div className="flex gap-2">
            <Button onClick={testConnection} variant="outline" size="sm">
              <Server className="w-3 h-3 mr-1" />
              Test
            </Button>

            {messages.length > 0 && (
              <Button onClick={clearChat} variant="outline" size="sm" disabled={isLoading}>
                <Trash2 className="w-3 h-3 mr-1" />
                Reset
              </Button>
            )}

            {/* Bouton déconnexion Keycloak complète */}
            {authType === 'keycloak' && (
              <Button
                onClick={() => {
                  // Marquer la déconnexion en cours
                  localStorage.setItem('keycloak_logout_pending', 'true')

                  // Déconnexion complète Keycloak
                  localStorage.clear()
                  sessionStorage.clear()

                  // Rédiriger vers logout Keycloak puis revenir
                  window.location.href = `http://localhost:8080/realms/AMDIE_CHATBOT/protocol/openid-connect/logout?redirect_uri=${encodeURIComponent(window.location.origin + '?logout=true')}`
                }}
                variant="destructive"
                size="sm"
              >
                <Key className="w-3 h-3 mr-1" />
                Déconnexion
              </Button>
            )}
          </div>
        </div>

        {/* Card principale */}
        <Card className="flex-1 flex flex-col bg-white/80 backdrop-blur-sm border border-gray-200 shadow-lg">

          {/* Zone de messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">

            {/* Suggestions initiales basées sur le rôle */}
            {messages.length === 0 && (
              <div className="text-center space-y-6">
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold text-gray-800">
                    🤖 Assistant IA AMDIE
                  </h2>
                  <div className="flex items-center justify-center gap-2">
                    <Shield className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-600">
                      Connecté via {authType === 'keycloak' ? 'Keycloak' : 'Auth classique'} avec niveau d'accès:
                      <span className={`ml-1 px-2 py-1 rounded text-xs font-medium ${getRoleColor(authState.user?.role || '')}`}>
                        {authState.user?.role?.toUpperCase()}
                      </span>
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {getRoleSuggestions().map((text, idx) => (
                    <Button
                      key={idx}
                      variant="outline"
                      className="text-left h-auto p-4 text-sm text-gray-700 hover:bg-blue-50 transition-colors"
                      onClick={() => handleSuggestionClick(text)}
                      disabled={isLoading}
                    >
                      {text}
                    </Button>
                  ))}
                </div>

                {/* Permissions actuelles */}
                <div className="bg-gray-50 rounded-lg p-4 text-xs">
                  <h4 className="font-medium text-gray-700 mb-2">🔐 Vos permissions actuelles:</h4>
                  <div className="flex flex-wrap gap-1">
                    {authState.user?.permissions.map((perm, idx) => (
                      <span key={idx} className="bg-white px-2 py-1 rounded border text-gray-600">
                        {perm}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Messages avec indication du niveau d'accès */}
            {messages.map((msg, idx) => (
              <div
                key={msg.messageId || idx}
                id={msg.messageId === 'PROGRESS_MESSAGE' ? 'progress-message' : undefined}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-green-600" />
                  </div>
                )}

                {msg.role === 'system' && (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    {msg.isProgress ? (
                      <Loader className="w-4 h-4 text-blue-600 animate-spin" />
                    ) : (
                      <Ellipsis className="w-4 h-4 text-blue-600" />
                    )}
                  </div>
                )}

                <div className={`max-w-[80%] rounded-2xl p-4 transition-all duration-300 ${
                  msg.role === 'user'
                    ? 'bg-blue-500 text-white ml-auto'
                    : msg.role === 'system'
                    ? 'bg-blue-50 text-blue-800 border border-blue-200'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                  </div>
                  <div className={`text-xs mt-2 opacity-70 flex items-center justify-between ${
                    msg.role === 'user' ? 'text-blue-100' : 
                    msg.role === 'system' ? 'text-blue-600' : 'text-gray-500'
                  }`}>
                    <span>{msg.timestamp.toLocaleTimeString()}</span>
                    {msg.userRole && (
                      <span className={`px-1 py-0.5 rounded text-xs ${getRoleColor(msg.userRole)} opacity-75`}>
                        {msg.userRole}
                      </span>
                    )}
                  </div>
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <User className="w-5 h-5 text-blue-600" />
                  </div>
                )}
              </div>
            ))}

            {/* Indicateur de chargement */}
            {isLoading && !messages.some(m => m.messageId === 'PROGRESS_MESSAGE') && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-green-600" />
                </div>
                <div className="bg-gray-100 rounded-2xl p-4">
                  <div className="flex items-center gap-2 text-gray-500">
                    <Loader className="w-4 h-4 animate-spin" />
                    <span className="text-sm">
                      Traitement avec niveau {authState.user?.role}...
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Zone de saisie */}
          <div className="border-t border-gray-200 p-4">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <Textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder={`Posez votre question (accès niveau ${authState.user?.role} via ${authType})...`}
                rows={1}
                disabled={isLoading}
                className="resize-none"
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSubmit(e)
                  }
                }}
              />
              <Button
                type="submit"
                disabled={!input.trim() || isLoading}
                size="lg"
                className="px-6"
              >
                {isLoading
                  ? <Loader className="w-4 h-4 animate-spin" />
                  : <Send className="w-4 h-4" />
                }
              </Button>
            </form>
          </div>
        </Card>
      </div>
    </div>
  )
}