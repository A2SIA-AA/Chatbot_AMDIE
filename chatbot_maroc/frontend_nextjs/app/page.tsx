"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { 
  Loader, Send, Bot, User, Ellipsis, Server, Trash2, 
  LogOut, Shield, Eye, EyeOff, Lock, UserCheck 
} from "lucide-react"
import Image from "next/image"

// ========================================
// INTERFACES TYPESCRIPT ÉTENDUES
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
// COMPOSANT DE CONNEXION
// ========================================

const LoginForm = ({ onLogin, isLoading }) => {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loginError, setLoginError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Comptes de démonstration
  const demoAccounts = [
    {
      email: "public@demo.ma",
      password: "public123",
      role: "Public",
      description: "Accès aux données publiques uniquement",
      color: "bg-blue-100 text-blue-800"
    },
    {
      email: "salarie@amdie.ma",
      password: "salarie123",
      role: "Employé",
      description: "Accès aux données publiques + internes",
      color: "bg-green-100 text-green-800"
    },
    {
      email: "admin@amdie.ma",
      password: "admin123", 
      role: "Admin",
      description: "Accès complet à toutes les données",
      color: "bg-purple-100 text-purple-800"
    }
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      setLoginError("Email et mot de passe requis")
      return
    }

    setIsSubmitting(true)
    setLoginError("")
    const FASTAPI_BASE_URL = "http://0.0.0.0:8000"

    try {
      const response = await fetch(`${FASTAPI_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email: email.trim(), password })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Erreur de connexion')
      }

      const data: LoginResponse = await response.json()
      
      // Stocker le token
      localStorage.setItem('amdie_token', data.access_token)
      localStorage.setItem('amdie_user', JSON.stringify(data.user))
      
      console.log(` Connexion réussie: ${data.user.full_name} (${data.user.role})`)
      onLogin(data)

    } catch (error) {
      console.error(' Erreur login:', error)
      setLoginError(error instanceof Error ? error.message : 'Erreur de connexion')
    } finally {
      setIsSubmitting(false)
    }
  }

  const quickLogin = (account) => {
    setEmail(account.email)
    setPassword(account.password)
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
            Assistant IA avec contrôle d'accès
          </p>
        </div>

        {/* Formulaire de connexion */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="votre@email.ma"
              disabled={isSubmitting}
              className="w-full"
            />
          </div>

          <div>
            <Label htmlFor="password">Mot de passe</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Votre mot de passe"
                disabled={isSubmitting}
                className="w-full pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2"
                disabled={isSubmitting}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {loginError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 text-red-700 text-sm">
              ❌ {loginError}
            </div>
          )}

          <Button 
            type="submit" 
            className="w-full"
            disabled={isSubmitting || isLoading}
          >
            {isSubmitting ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Connexion...
              </>
            ) : (
              <>
                <Lock className="w-4 h-4 mr-2" />
                Se connecter
              </>
            )}
          </Button>
        </form>

        {/* Comptes de démonstration */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-3 text-center">
             Comptes de démonstration
          </h3>
          <div className="space-y-2">
            {demoAccounts.map((account, index) => (
              <button
                key={index}
                onClick={() => quickLogin(account)}
                className="w-full text-left p-2 rounded-md border border-gray-200 hover:bg-gray-50 transition-colors text-xs"
                disabled={isSubmitting}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${account.color}`}>
                      {account.role}
                    </span>
                    <p className="text-gray-600 mt-1">{account.description}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-xs text-gray-500">{account.email}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            Cliquez sur un compte pour remplir automatiquement
          </p>
        </div>
      </Card>
    </div>
  )
}

// ========================================
// COMPOSANT PRINCIPAL AVEC AUTHENTIFICATION
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

  const FASTAPI_BASE_URL = "http://0.0.0.0:8000"

  // Vérification du token au chargement
  useEffect(() => {
    const checkAuthStatus = async () => {
      const token = localStorage.getItem('amdie_token')
      const userStr = localStorage.getItem('amdie_user')
      
      if (token && userStr) {
        try {
          const user = JSON.parse(userStr)
          
          // Vérifier la validité du token
          const response = await fetch(`${FASTAPI_BASE_URL}/api/v1/auth/me`, {
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
            console.log(` Session restaurée: ${currentUser.full_name}`)
          } else {
            // Token expiré ou invalide
            localStorage.removeItem('amdie_token')
            localStorage.removeItem('amdie_user')
            setAuthState(prev => ({ ...prev, isLoading: false }))
          }
        } catch (error) {
          console.error(' Erreur vérification token:', error)
          localStorage.removeItem('amdie_token')
          localStorage.removeItem('amdie_user')
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
    try {
      // Appeler l'API de déconnexion
      await fetch(`${FASTAPI_BASE_URL}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authState.token}`
        }
      })
    } catch (error) {
      console.error(' Erreur déconnexion:', error)
    } finally {
      // Nettoyer le localStorage et l'état
      localStorage.removeItem('amdie_token')
      localStorage.removeItem('amdie_user')
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
      
      console.log(' Déconnexion réussie')
    }
  }

  // Fonction d'envoi de message MODIFIÉE pour inclure l'auth
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

      const response = await fetch(`${FASTAPI_BASE_URL}/api/v1/start-processing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'Authorization': `Bearer ${authState.token}` // TOKEN JWT
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

      console.log(` Session démarrée: ${sessionId} pour ${authState.user?.role}`)

      setSession({
        sessionId,
        isActive: true,
        lastTimestamp: 0,
        userRole: authState.user?.role
      })

      startPolling(sessionId)

    } catch (error) {
      console.error(" Erreur envoi:", error)
      const errorMessage: Message = {
        role: 'assistant',
        content: ` ${error instanceof Error ? error.message : 'Erreur inconnue'}`,
        timestamp: new Date(),
        messageId: generateMessageId()
      }
      setMessages(prev => [...prev, errorMessage])
      setIsLoading(false)
    }
  }

  // Fonction utilitaire
  const generateMessageId = () => `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`

  // Polling (identique à votre version existante)
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
              'Authorization': `Bearer ${authState.token}` // TOKEN JWT
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
        console.error(" Erreur polling:", error)
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
        console.error(" Erreur nettoyage session:", err)
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
      alert(` Connexion API: ${data.status}`)
    } catch (error) {
      alert(" API non accessible")
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

  // Si non authentifié, afficher le formulaire de connexion
  if (!authState.isAuthenticated) {
    return <LoginForm onLogin={handleLogin} isLoading={authState.isLoading} />
  }

  // Interface principale avec utilisateur connecté
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
            
            <Button onClick={handleLogout} variant="outline" size="sm">
              <LogOut className="w-3 h-3 mr-1" />
              Déconnexion
            </Button>
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
                     Assistant IA AMDIE
                  </h2>
                  <div className="flex items-center justify-center gap-2">
                    <Shield className="w-4 h-4 text-green-600" />
                    <span className="text-sm text-gray-600">
                      Connecté avec niveau d'accès: 
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
                  <h4 className="font-medium text-gray-700 mb-2"> Vos permissions actuelles:</h4>
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
                placeholder={`Posez votre question (accès niveau ${authState.user?.role})...`}
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
