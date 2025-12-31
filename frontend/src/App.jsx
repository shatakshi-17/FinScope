import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { WorkflowProvider, useWorkflow } from './WorkflowContext'
import LandingPage from './LandingPage'
import ChatDetailPage from './ChatDetailPage'
import SECSearchPage from './SECSearchPage'
import AnalysisPage from './AnalysisPage'
import UploadPage from './UploadPage'

function StatusBar() {
  const { backendStatus, setBackendStatus } = useWorkflow()

  useEffect(() => {
    const checkBackendStatus = async () => {
      try {
        const response = await fetch('/api/health')
        if (response.status === 200) {
          setBackendStatus('Online')
        } else {
          setBackendStatus('Offline')
        }
      } catch (error) {
        setBackendStatus('Offline')
      }
    }

    // Check immediately
    checkBackendStatus()

    // Then check every 5 seconds
    const interval = setInterval(checkBackendStatus, 5000)

    return () => clearInterval(interval)
  }, [setBackendStatus])

  return (
    <div className="glass-card border-b-0 rounded-b-none px-4 py-2">
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            backendStatus === 'Online' ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
        <span className="text-sm text-brand-charcoal">
          Backend: {backendStatus}
        </span>
      </div>
    </div>
  )
}

function AppContent() {
  const { uploadAnalysisData } = useWorkflow()

  // Set up beforeunload warning for active upload sessions
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      // Check if there's an active upload session
      if (uploadAnalysisData && uploadAnalysisData.sessionId) {
        // Modern browsers ignore custom messages, but we can still trigger the warning
        e.preventDefault()
        // For older browsers
        e.returnValue = 'Unsaved temporary session files will persist on the server unless you End Session.'
        // Return the message (though most browsers will show their own message)
        return 'Unsaved temporary session files will persist on the server unless you End Session.'
      }
    }

    // Add the event listener
    window.addEventListener('beforeunload', handleBeforeUnload)

    // Cleanup: remove the event listener when component unmounts or uploadAnalysisData changes
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [uploadAnalysisData])

  return (
    <div className="min-h-screen">
      <StatusBar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/company" element={<SECSearchPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
        <Route path="/history/chat/:sessionId" element={<ChatDetailPage />} />
      </Routes>
    </div>
  )
}

function App() {
  // Clean up any upload-related localStorage keys on mount
  useEffect(() => {
    localStorage.removeItem('upload_session')
    localStorage.removeItem('upload_metadata')
    // Also clean uploadMetadata from active session if it exists
    try {
      const stored = localStorage.getItem('finscope_active_session')
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed.uploadMetadata) {
          delete parsed.uploadMetadata
          localStorage.setItem('finscope_active_session', JSON.stringify(parsed))
        }
      }
    } catch (error) {
      console.error('Failed to clean upload metadata from active session:', error)
    }
  }, [])
  
  return (
    <WorkflowProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </WorkflowProvider>
  )
}

export default App

