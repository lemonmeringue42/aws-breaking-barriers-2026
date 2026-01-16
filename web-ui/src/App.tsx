import { useEffect, useState } from 'react'
import { Amplify } from 'aws-amplify'
import { Authenticator } from '@aws-amplify/ui-react'
import { getCurrentUser, signOut } from 'aws-amplify/auth'
import Chat from './components/Chat'
import UserOnboarding from './components/UserOnboarding'
import UserProfile from './components/UserProfile'
import UKMap from './components/UKMap'
import Dashboard from './components/Dashboard'
import AccessibilityToggle from './components/AccessibilityToggle'
import { LanguageSelector } from './components/LanguageSelector'
import { useSessions } from './hooks/useSessions'
import { getCognitoUserInfo, getDisplayName } from './services/cognitoUserService'
import { ensureUserExists } from './services/userService'
import { userProfileService } from './services/userProfileService'
import outputs from '../../amplify_outputs.json'
import '@aws-amplify/ui-react/styles.css'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'
import './styles/citizens-advice.css'

Amplify.configure(outputs)

interface User {
  username: string
  email?: string
  userId: string
  name?: string
}

const AppWithSessions = ({ user, onSignOut }: { user: User; onSignOut: () => void }) => {
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [showDashboard, setShowDashboard] = useState(false)
  const [profileLoading, setProfileLoading] = useState(true)
  const [displayName, setDisplayName] = useState<string>(user.username)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [userPostcode, setUserPostcode] = useState<string | undefined>()
  const [userRegion, setUserRegion] = useState<string | undefined>()
  const [currentMessages, setCurrentMessages] = useState<any[]>([])
  const [language, setLanguage] = useState(() => localStorage.getItem('preferredLanguage') || 'en')

  const handleLanguageChange = (lang: string) => {
    setLanguage(lang)
    localStorage.setItem('preferredLanguage', lang)
  }

  const { sessions, currentSession, loading, switchToSession, startNewConversation, getMessages, refreshSessions, updateCurrentSession } = useSessions(user.userId)

  useEffect(() => {
    if (currentSession) {
      getMessages(currentSession.id).then(msgs => setCurrentMessages(msgs))
    } else {
      setCurrentMessages([])
    }
  }, [currentSession, getMessages])

  const loadProfile = async () => {
    try {
      const profile = await userProfileService.getUserProfile(user.userId)
      if (!profile || !profile.onboardingCompleted) setShowOnboarding(true)
      if (profile?.name) setDisplayName(profile.name)
      if (profile?.postcode) setUserPostcode(profile.postcode)
      if (profile?.region) setUserRegion(profile.region)
    } catch {
      setShowOnboarding(true)
    } finally {
      setProfileLoading(false)
    }
  }

  useEffect(() => {
    loadProfile()
  }, [user.userId])

  if (profileLoading) {
    return (
      <div className="ca-loading">
        <div className="ca-loading-spinner"></div>
        <p>Setting up your profile...</p>
      </div>
    )
  }

  return (
    <div className="ca-app">
      <a href="#main-content" className="ca-skip-link">Skip to main content</a>
      <ToastContainer theme="dark" />
      {showOnboarding && <UserOnboarding user={user} onComplete={() => {
        setShowOnboarding(false)
        loadProfile()
      }} />}
      <UserProfile user={user} isOpen={showProfile} onClose={() => { setShowProfile(false); loadProfile() }} />
      
      {showDashboard && (
        <div className="modal-overlay" onClick={() => setShowDashboard(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowDashboard(false)}>&times;</button>
            <Dashboard userId={user.userId} />
          </div>
        </div>
      )}

      <header className="ca-header" role="banner">
        <div className="ca-header-brand">
          <div className="ca-logo" aria-hidden="true">
            <img src="/favicon.png" alt="Citizens Advice" style={{ width: '40px', height: '40px', borderRadius: '8px' }} />
          </div>
          <div>
            <h1>Citizens Advice</h1>
            <span className="ca-tagline">Free, confidential advice. Whoever you are.</span>
          </div>
        </div>
        
        <nav className="ca-header-actions" aria-label="User menu">
          <LanguageSelector currentLang={language} onLanguageChange={handleLanguageChange} />
          <AccessibilityToggle />
          <span className="ca-welcome">Welcome, {displayName}</span>
          <button onClick={() => setShowDashboard(true)} className="ca-btn ca-btn-ghost" aria-label="View your dashboard">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
            </svg>
            Dashboard
          </button>
          <button onClick={() => setShowProfile(true)} className="ca-btn ca-btn-ghost" aria-label="View your profile">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M20 21V19C20 16.79 18.21 15 16 15H8C5.79 15 4 16.79 4 19V21"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            Profile
          </button>
          <button onClick={onSignOut} className="ca-btn ca-btn-outline" aria-label="Sign out of your account">Sign Out</button>
        </nav>
      </header>

      <div className="ca-layout">
        <aside className={`ca-sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
          <button 
            className="ca-sidebar-toggle" 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d={sidebarOpen ? "M15 18l-6-6 6-6" : "M9 18l6-6-6-6"} />
            </svg>
          </button>
          
          {sidebarOpen && (
            <>
              <div className="ca-sidebar-section">
                <h3>Your Details</h3>
                <div className="ca-user-info">
                  <p><strong>{displayName}</strong></p>
                  {userPostcode && <p>📍 {userPostcode}</p>}
                  {userRegion && <p>🏴 {userRegion}</p>}
                </div>
              </div>
              
              {userPostcode && (
                <div className="ca-sidebar-section">
                  <h3>Your Location</h3>
                  <UKMap postcode={userPostcode} />
                </div>
              )}
            </>
          )}
        </aside>

        <main id="main-content" className="ca-main">
        <Chat
          user={user}
          currentSession={currentSession}
          sessions={sessions}
          onSwitchSession={(id) => { const s = sessions.find(x => x.id === id); if (s) switchToSession(s) }}
          getMessages={getMessages}
          refreshSessions={refreshSessions}
          updateCurrentSession={updateCurrentSession}
          onMessagesUpdate={setCurrentMessages}
          onNewChat={startNewConversation}
          canStartNewChat={!loading}
          language={language}
        />
        </main>
      </div>
    </div>
  )
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    getCurrentUser()
      .then(async (cu) => {
        await ensureUserExists(cu.userId)
        const info = await getCognitoUserInfo(cu.userId)
        setUser({ username: getDisplayName(info), email: info.email || cu.signInDetails?.loginId, userId: cu.userId, name: info.fullName })
      })
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) {
    return <div className="ca-loading"><div className="ca-loading-spinner"></div><p>Loading...</p></div>
  }

  return (
    <Authenticator signUpAttributes={['email', 'given_name', 'family_name']}>
      {({ user: au }) => {
        if (au && !user) {
          Promise.all([ensureUserExists(au.userId), getCognitoUserInfo(au.userId)])
            .then(([_, i]) => setUser({ username: getDisplayName(i), email: i.email, userId: au.userId, name: i.fullName }))
            .catch(() => setUser({ username: au.username, email: au.signInDetails?.loginId, userId: au.userId }))
        }
        return user ? <AppWithSessions user={user} onSignOut={async () => { await signOut(); setUser(null) }} /> : <></>
      }}
    </Authenticator>
  )
}

export default App
