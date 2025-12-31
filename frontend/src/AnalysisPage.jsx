import { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Send, Loader2, FileText, Newspaper, MessageSquare, X, ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react'
import { useWorkflow } from './WorkflowContext'

function AnalysisPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { 
    secWorkflowData, 
    setSecWorkflowData, 
    analysisData, 
    setAnalysisData, 
    selectionMetadata,
    uploadMetadata,
    setUploadMetadata,
    uploadAnalysisData,
    setUploadAnalysisData
  } = useWorkflow()
  
  // Loading state - start as false if we have cached data to avoid flash
  // For upload workflow, show loading if we're coming from a fresh upload (location.state)
  const [loading, setLoading] = useState(() => {
    // Check if we're coming from a fresh upload (location.state has isUpload)
    const isFreshUpload = location.state && location.state.isUpload
    
    // If it's a fresh upload, show loading screen (even if analysisData exists)
    if (isFreshUpload) {
      return true
    }
    
    // Check if sourceType is 'upload'
    const isUploadSourceType = analysisData && analysisData.sourceType === 'upload'
    
    // If we have upload analysis data (either from analysisData or uploadAnalysisData) and it's not a fresh upload, don't show loading
    if (isUploadSourceType && analysisData && analysisData.sessionId) {
      return false
    }
    
    // Also check uploadAnalysisData
    // Note: uploadAnalysisData is not available in useState initializer, so we check it in useEffect
    
    // For SEC workflow or no data, show loading
    return !analysisData || !analysisData.sessionId
  })
  const [loadingTeaser, setLoadingTeaser] = useState(0)
  const [error, setError] = useState(null)
  
  // Analysis data
  const [sessionId, setSessionId] = useState(null)
  const [executiveSummary, setExecutiveSummary] = useState('')
  const [newsArticles, setNewsArticles] = useState([])
  const [companyInfo, setCompanyInfo] = useState(null)
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([])
  const [userInput, setUserInput] = useState('')
  const [sendingMessage, setSendingMessage] = useState(false)
  const [showEndSessionDialog, setShowEndSessionDialog] = useState(false)
  const [endingSession, setEndingSession] = useState(false)
  const [expandedReferences, setExpandedReferences] = useState(new Set())
  const chatEndRef = useRef(null)
  const chatContainerRef = useRef(null)
  
  const toggleReferences = (messageIndex) => {
    setExpandedReferences(prev => {
      const newSet = new Set(prev)
      if (newSet.has(messageIndex)) {
        newSet.delete(messageIndex)
      } else {
        newSet.add(messageIndex)
      }
      return newSet
    })
  }
  
  // Loading teasers - different for SEC vs Upload workflows
  // Check if sourceType is 'upload' or if we have uploadAnalysisData
  const isUploadWorkflow = !secWorkflowData || 
                          (analysisData && analysisData.sourceType === 'upload') ||
                          (uploadAnalysisData && uploadAnalysisData.sessionId)
  
  const secLoadingTeasers = [
    'Fetching SEC Filings: Accessing the EDGAR database for the latest reports...',
    'RAG Initialization: Building a searchable vector index of the document...',
    'AI Synthesis: Gemini is generating your executive summary...',
    'Market Context: Gathering real-time news for broader perspective...'
  ]
  
  const uploadLoadingTeasers = [
    'Processing your local document...',
    'Gemini is reading your PDF/TXT...',
    'RAG Initialization: Building a searchable vector index of the document...',
    'AI Synthesis: Gemini is generating your executive summary...',
    'Market Context: Gathering real-time news for broader perspective...'
  ]
  
  const loadingTeasers = isUploadWorkflow ? uploadLoadingTeasers : secLoadingTeasers
  
  // Computed values that prioritize uploadAnalysisData when sourceType is 'upload'
  const displayExecutiveSummary = useMemo(() => {
    const isUploadSourceType = analysisData && analysisData.sourceType === 'upload'
    if (isUploadSourceType && uploadAnalysisData && uploadAnalysisData.executiveSummary) {
      return uploadAnalysisData.executiveSummary
    }
    return executiveSummary
  }, [analysisData, uploadAnalysisData, executiveSummary])

  const displayNewsArticles = useMemo(() => {
    const isUploadSourceType = analysisData && analysisData.sourceType === 'upload'
    if (isUploadSourceType && uploadAnalysisData && uploadAnalysisData.newsArticles) {
      return uploadAnalysisData.newsArticles
    }
    return newsArticles
  }, [analysisData, uploadAnalysisData, newsArticles])

  const displayChatMessages = useMemo(() => {
    // Chat messages should always come from analysisData (they're updated during chat)
    // But we can check uploadAnalysisData as a fallback if needed
    const isUploadSourceType = analysisData && analysisData.sourceType === 'upload'
    if (isUploadSourceType && analysisData && analysisData.chatMessages) {
      return analysisData.chatMessages
    }
    return chatMessages
  }, [analysisData, chatMessages])
  
  // Rotate loading teasers
  useEffect(() => {
    if (!loading) return
    
    const interval = setInterval(() => {
      setLoadingTeaser((prev) => (prev + 1) % loadingTeasers.length)
    }, 5000)
    
    return () => clearInterval(interval)
  }, [loading, loadingTeasers.length])
  
  // Scroll chat to bottom when new messages arrive (only within chat container)
  useEffect(() => {
    if (chatContainerRef.current && chatEndRef.current) {
      // Scroll the container, not the entire page
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth'
      })
    }
  }, [chatMessages])
  
  // Start analysis on mount
  useEffect(() => {
    const startAnalysis = async () => {
      // Check if sourceType is 'upload'
      const isUploadSourceType = analysisData && analysisData.sourceType === 'upload'
      
      // Check if we have analysis data from upload workflow (already processed)
      // This handles both navigation back and page refresh
      const isUploadWorkflow = isUploadSourceType && 
                               analysisData.sessionId && 
                               !secWorkflowData
      
      if (isUploadWorkflow) {
        // Check if we have uploadAnalysisData
        if (uploadAnalysisData && uploadAnalysisData.sessionId) {
          // Use data from uploadAnalysisData if available
          
          // Restore from uploadAnalysisData
          setSessionId(uploadAnalysisData.sessionId)
          setExecutiveSummary(uploadAnalysisData.executiveSummary || analysisData.executiveSummary || '')
          setNewsArticles(uploadAnalysisData.newsArticles || analysisData.newsArticles || [])
          setChatMessages(analysisData.chatMessages || [])
        } else {
          // Fallback to analysisData
          
          // Restore from cached data
          setSessionId(analysisData.sessionId)
          setExecutiveSummary(analysisData.executiveSummary || '')
          setNewsArticles(analysisData.newsArticles || [])
          setChatMessages(analysisData.chatMessages || [])
        }
        
        // Check if this is a fresh upload (coming from UploadPage with location.state)
        const isFreshUpload = location.state && location.state.isUpload
        
        // Use uploadMetadata if available, otherwise try to fetch from API
        if (uploadMetadata && uploadMetadata.companyName) {
          setCompanyInfo({
            companyName: uploadMetadata.companyName || 'Unknown Company',
            docTitle: uploadMetadata.docTitle || '',
            docType: uploadMetadata.docType || 'Local Upload'
          })
        } else {
          // Fallback: Try to fetch metadata from API
          try {
            const historyResponse = await fetch(`/api/history/chat/${analysisData.sessionId}`)
            if (historyResponse.ok) {
              const historyData = await historyResponse.json()
              const metadata = historyData.metadata || {}
              setCompanyInfo({
                companyName: metadata.company || 'Unknown Company',
                docTitle: metadata.doc_title || '',
                docType: metadata.doc_type || 'Local Upload'
              })
              
              // Also update uploadMetadata if we got it from API
              // This ensures it's available for future refreshes
              if (metadata.company && !uploadMetadata) {
                // Note: We can't set uploadMetadata here as it's not in the dependencies
                // But the data is already in analysisData, so it should be fine
              }
            } else {
              // Use defaults if API fails
              setCompanyInfo({
                companyName: 'Unknown Company',
                docTitle: '',
                docType: 'Local Upload'
              })
            }
          } catch (err) {
            console.warn('Could not fetch metadata on refresh:', err)
            setCompanyInfo({
              companyName: 'Unknown Company',
              docTitle: '',
              docType: 'Local Upload'
            })
          }
        }
        
        // On refresh, optionally fetch latest chat messages from backend to ensure sync
        // But only if we don't have chat messages in analysisData
        if (!isFreshUpload && (!analysisData.chatMessages || analysisData.chatMessages.length === 0)) {
          // Try to fetch chat history from backend (non-blocking)
          fetch(`/api/history/chat/${analysisData.sessionId}`)
            .then(response => {
              if (response.ok) {
                return response.json()
              }
              return null
            })
            .then(historyData => {
              if (historyData && historyData.messages && Array.isArray(historyData.messages)) {
                // Convert backend message format to frontend format
                const formattedMessages = historyData.messages.map(msg => ({
                  role: msg.role || (msg.sender === 'user' ? 'user' : 'assistant'),
                  content: msg.content || msg.message || '',
                  references: msg.references || '',
                  timestamp: msg.timestamp || new Date().toISOString()
                }))
                
                if (formattedMessages.length > 0) {
                  setChatMessages(formattedMessages)
                  // Update analysisData with fetched messages
                  if (setAnalysisData) {
                    setAnalysisData(prevData => {
                      if (!prevData) return prevData
                      return {
                        ...prevData,
                        chatMessages: formattedMessages
                      }
                    })
                  }
                }
              }
            })
            .catch(err => {
              console.warn('Could not fetch chat history on refresh:', err)
              // Continue with cached messages
            })
        }
        
        // Show loading screen only for fresh uploads (not for refresh/resume)
        if (isFreshUpload) {
          setTimeout(() => {
            setLoading(false)
          }, 2000) // Show for 2 seconds to match SEC flow timing
        } else {
          // For refresh/resume, no loading screen
          setLoading(false)
        }
        return
      }
      
      // If we have upload workflow data but no analysis data yet (shouldn't happen normally)
      // Check for uploadAnalysisData first
      if (!secWorkflowData && uploadMetadata && (!analysisData || !analysisData.sessionId)) {
        // Check if we have uploadAnalysisData
        if (uploadAnalysisData && uploadAnalysisData.sessionId) {
          setLoading(true)
          
          // Restore from uploadAnalysisData
          setSessionId(uploadAnalysisData.sessionId)
          setExecutiveSummary(uploadAnalysisData.executiveSummary || '')
          setNewsArticles(uploadAnalysisData.newsArticles || [])
          setCompanyInfo({
            companyName: uploadMetadata.companyName || 'Unknown Company',
            docTitle: uploadMetadata.docTitle || '',
            docType: uploadMetadata.docType || 'Local Upload'
          })
          
          // Update analysisData with uploadAnalysisData
          if (setAnalysisData) {
            setAnalysisData({
              sessionId: uploadAnalysisData.sessionId,
              executiveSummary: uploadAnalysisData.executiveSummary || '',
              newsArticles: uploadAnalysisData.newsArticles || [],
              chatMessages: [],
              sourceType: 'upload'
            })
          }
          
          setTimeout(() => {
            setLoading(false)
          }, 2000)
          return
        }
        
        setLoading(true)
        
        // Try to get sessionId from location state
        const locationState = location.state
        if (locationState && locationState.sessionId) {
          try {
            const historyResponse = await fetch(`/api/history/chat/${locationState.sessionId}`)
            if (historyResponse.ok) {
              const historyData = await historyResponse.json()
              const metadata = historyData.metadata || {}
              
              setSessionId(locationState.sessionId)
              setExecutiveSummary(metadata.executive_summary || '')
              setNewsArticles(metadata.news_articles || [])
              setCompanyInfo({
                companyName: uploadMetadata.companyName || metadata.company || 'Unknown Company',
                docTitle: uploadMetadata.docTitle || metadata.doc_title || '',
                docType: uploadMetadata.docType || metadata.doc_type || 'Local Upload'
              })
              
              if (setAnalysisData) {
                setAnalysisData({
                  sessionId: locationState.sessionId,
                  executiveSummary: metadata.executive_summary || '',
                  newsArticles: metadata.news_articles || [],
                  chatMessages: [],
                  sourceType: 'upload'
                })
              }
              
              setTimeout(() => {
                setLoading(false)
              }, 2000)
              return
            }
          } catch (err) {
            console.error('Failed to fetch upload analysis:', err)
            setError('Failed to load analysis. Please try again.')
            setLoading(false)
            return
          }
        }
        
        setError('Analysis data not found. Please try uploading again.')
        setLoading(false)
        return
      }
      
      // SEC workflow: Check if we have workflow data
      if (!secWorkflowData || !secWorkflowData.selected_filing) {
        setError('Missing workflow data. Please start from the company search page or upload page.')
        setLoading(false)
        return
      }
      
      const { ticker, company_name, selected_filing } = secWorkflowData
      
      // Smart Reproduction: Check if we already have analysis data for this selection
      if (analysisData && selectionMetadata) {
        const currentFilingId = selected_filing.accession_number
        const storedFilingId = selectionMetadata.selected_filing?.accession_number
        
        if (analysisData.sessionId && 
            selectionMetadata.ticker === ticker && 
            currentFilingId === storedFilingId) {
          
          // Restore from cached data
          setSessionId(analysisData.sessionId)
          setExecutiveSummary(analysisData.executiveSummary || '')
          setNewsArticles(analysisData.newsArticles || [])
          setChatMessages(analysisData.chatMessages || [])
          setCompanyInfo({
            ticker: ticker,
            companyName: company_name,
            filing: selected_filing
          })
          
          setLoading(false)
          return
        } else {
          // Selection changed - clear old analysis data
          setAnalysisData(null)
        }
      }
      
      // No cached data or mismatch - fetch new analysis
      try {
        setLoading(true)
        setError(null)
        
        // Call /api/start-analysis
        const response = await fetch('/api/start-analysis', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            ticker: ticker,
            companyName: company_name,
            filingId: selected_filing.accession_number
          })
        })
        
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
        }
        
        const data = await response.json()
        
        // Store session data
        const newSessionId = data.sessionId
        const newExecutiveSummary = data.executiveSummary || ''
        const newCompanyInfo = {
          ticker: ticker,
          companyName: company_name,
          filing: selected_filing
        }
        
        setSessionId(newSessionId)
        setExecutiveSummary(newExecutiveSummary)
        setCompanyInfo(newCompanyInfo)
        
        // Get news articles from response
        let newNewsArticles = []
        if (data.newsArticles && Array.isArray(data.newsArticles)) {
          newNewsArticles = data.newsArticles
          setNewsArticles(newNewsArticles)
        } else {
          // Try to fetch from session metadata as fallback
          try {
            const historyResponse = await fetch(`/api/history/chat/${newSessionId}`)
            if (historyResponse.ok) {
              const historyData = await historyResponse.json()
              const metadata = historyData.metadata || {}
              if (metadata.news_articles && Array.isArray(metadata.news_articles)) {
                newNewsArticles = metadata.news_articles
                setNewsArticles(newNewsArticles)
              }
            }
          } catch (err) {
            console.warn('Could not fetch news from metadata:', err)
          }
        }
        
        // Save to context for persistence
        if (setAnalysisData) {
          setAnalysisData({
            sessionId: newSessionId,
            executiveSummary: newExecutiveSummary,
            newsArticles: newNewsArticles,
            chatMessages: []
          })
        }
        
        setLoading(false)
      } catch (err) {
        console.error('Failed to start analysis:', err)
        setError(err.message)
        setLoading(false)
      }
    }
    
    startAnalysis()
  }, [secWorkflowData, analysisData, selectionMetadata, uploadMetadata])
  
  const handleSendMessage = async () => {
    if (!userInput.trim() || !sessionId || sendingMessage) return
    
    const messageText = userInput.trim()
    setUserInput('')
    
    // Add user message to chat
    const userMessage = {
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString()
    }
    setChatMessages(prev => [...prev, userMessage])
    setSendingMessage(true)
    
    // Note: We'll update context after getting the assistant response
    
    try {
      // Call /api/chat
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sessionId: sessionId,
          userMessage: messageText
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      
      // Add assistant response to chat
      const assistantMessage = {
        role: 'assistant',
        content: data.assistantResponse,
        references: data.references || '',
        timestamp: new Date().toISOString()
      }
      
      // Update chat messages (user message was already added, now add assistant response)
      setChatMessages(prev => {
        const updated = [...prev, assistantMessage]
        
        // Update analysisData in context with new chat messages
        if (setAnalysisData) {
          setAnalysisData(prevData => {
            if (!prevData) return prevData
            return {
              ...prevData,
              chatMessages: updated
            }
          })
        }
        
        return updated
      })
    } catch (err) {
      console.error('Failed to send message:', err)
      // Add error message to chat
      const errorMessage = {
        role: 'assistant',
        content: `Error: ${err.message}`,
        isError: true,
        timestamp: new Date().toISOString()
      }
      setChatMessages(prev => [...prev, errorMessage])
    } finally {
      setSendingMessage(false)
    }
  }
  
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }
  
  const handleEndSessionClick = () => {
    if (!sessionId) return
    setShowEndSessionDialog(true)
  }
  
  const handleEndSessionConfirm = async () => {
    if (!sessionId) return
    
    setEndingSession(true)
    try {
      // Determine if this is an upload workflow
      const isUploadWorkflow = analysisData && analysisData.sourceType === 'upload'
      
      const response = await fetch('/api/end-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sessionId: sessionId
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
      }
      
      // Backend confirmed deletion - now clear frontend state
      
      // For upload workflow, clear upload-specific data
      if (isUploadWorkflow) {
        // Clear uploadAnalysisData and uploadMetadata from context
        if (setUploadAnalysisData) {
          setUploadAnalysisData(null)
        }
        if (setUploadMetadata) {
          setUploadMetadata(null)
        }
        
        // Clear upload data from localStorage
        localStorage.removeItem('finscope_upload_data')
        localStorage.removeItem('finscope_upload_meta')
      }
      
      // Clear all session data
      setSecWorkflowData(null)
      if (setAnalysisData) {
        setAnalysisData(null)
      }
      // Clear localStorage as well
      localStorage.removeItem('finscope_active_session')
      
      // Navigate to landing page
      navigate('/')
    } catch (err) {
      console.error('Failed to end session:', err)
      alert(`Failed to end session: ${err.message}`)
      setEndingSession(false)
      setShowEndSessionDialog(false)
    }
  }
  
  const handleEndSessionCancel = () => {
    setShowEndSessionDialog(false)
  }
  
  // Loading Screen
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-16 h-16 animate-spin mx-auto mb-6 text-primary-green" />
          <h2 className="text-2xl font-semibold mb-4 text-white">
            Preparing Your Analysis
          </h2>
          <p className="text-lg max-w-md mx-auto text-white opacity-80">
            {loadingTeasers[loadingTeaser]}
          </p>
          <div className="mt-4 flex justify-center gap-1">
            {loadingTeasers.map((_, index) => (
              <div
                key={index}
                className={`w-2 h-2 rounded-full transition-all ${
                  index === loadingTeaser ? 'w-8' : ''
                }`}
                style={{
                  backgroundColor: index === loadingTeaser ? '#347433' : 'rgba(255, 255, 255, 0.3)'
                }}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }
  
  // Error State
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="rounded-lg p-8 max-w-md shadow-md text-center border-2 border-alert-red" style={{ backgroundColor: '#B22222', color: '#FFFFFF' }}>
          <h2 className="text-2xl font-bold mb-4 text-white">
            Analysis Failed
          </h2>
          <p className="mb-6 text-white font-semibold">
            {error}
          </p>
          <button
            onClick={() => {
              if (secWorkflowData) {
                navigate('/company')
              } else {
                navigate('/upload')
              }
            }}
            className="px-6 py-2 rounded-lg font-semibold"
            style={{ backgroundColor: '#586f58', color: 'white' }}
          >
            Back
          </button>
        </div>
      </div>
    )
  }
  
  // Main Analysis Dashboard
  return (
    <div className="min-h-screen" style={{ backgroundColor: 'transparent' }}>
      {/* End Session Dialog */}
      {showEndSessionDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold mb-4" style={{ color: '#000000' }}>
              End Session
            </h2>
            <p className="mb-6" style={{ color: '#000000' }}>
              Are you sure you want to end this session? This will archive the conversation and clean up resources.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleEndSessionCancel}
                disabled={endingSession}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
              >
                Cancel
              </button>
              <button
                onClick={handleEndSessionConfirm}
                disabled={endingSession}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                style={{ backgroundColor: '#B22222', color: 'white' }}
              >
                {endingSession ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Ending...
                  </>
                ) : (
                  'Proceed'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="container mx-auto px-4 py-6 max-w-7xl space-y-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between gap-4 mb-4">
            <button
              onClick={() => {
                if (secWorkflowData) {
                  navigate('/company')
                } else {
                  navigate('/upload')
                }
              }}
              className="px-4 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 flex items-center gap-2"
              style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
            >
              <ArrowLeft className="w-5 h-5" />
              Back
            </button>
            <button
              onClick={handleEndSessionClick}
              disabled={!sessionId || endingSession}
              className="px-4 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              style={{ backgroundColor: '#B22222', color: 'white' }}
            >
              <X className="w-5 h-5" />
              End Session
            </button>
          </div>
          <div>
            <h1 className="text-3xl font-bold mb-2" style={{ color: '#586f58' }}>
              {companyInfo?.companyName}
              {companyInfo?.ticker && ` (${companyInfo.ticker})`}
            </h1>
            {companyInfo?.filing && (
              <p className="text-sm opacity-70" style={{ color: '#3a3a3a' }}>
                {companyInfo.filing.form_type} - {companyInfo.filing.filing_date}
              </p>
            )}
            {companyInfo?.docType && (
              <p className="text-sm opacity-70" style={{ color: '#3a3a3a' }}>
                {companyInfo.docType}
                {companyInfo.docTitle && ` - ${companyInfo.docTitle}`}
              </p>
            )}
          </div>
        </div>
        
        {/* Top Section: Chatbot */}
        <div className="glass-card rounded-lg mb-6" style={{ height: '500px', display: 'flex', flexDirection: 'column' }}>
          <div className="p-4 border-b flex items-center gap-2" style={{ borderColor: 'rgba(255, 255, 255, 0.2)' }}>
            <MessageSquare className="w-5 h-5" style={{ color: '#586f58' }} />
            <h2 className="text-xl font-semibold" style={{ color: '#586f58' }}>
              Personalised Chatbot
            </h2>
          </div>
          
          {/* Scrollable Chat History */}
          <div
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-4"
            style={{ backgroundColor: 'transparent' }}
          >
            {displayChatMessages.length === 0 && (
              <div className="text-center py-8 opacity-60" style={{ color: '#3a3a3a' }}>
                <MessageSquare className="w-12 h-12 mx-auto mb-2 opacity-40" />
                <p>Start a conversation by asking a question about the filing.</p>
              </div>
            )}
            
            {displayChatMessages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-4 ${
                    message.role === 'user'
                      ? 'rounded-br-none chat-bubble-user'
                      : 'rounded-bl-none chat-bubble-ai'
                  }`}
                  style={{
                    color: message.role === 'user' ? '#000000' : '#FFFFFF',
                    backgroundColor: message.role === 'user' ? 'rgba(218, 200, 160, 0.85)' : 'rgba(52, 116, 51, 0.3)'
                  }}
                >
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  {message.references && message.role === 'assistant' && (
                    <div className="mt-3">
                      <button
                        onClick={() => toggleReferences(index)}
                        className="flex items-center gap-2 text-sm font-semibold hover:opacity-80 transition-opacity w-full text-left"
                        style={{ color: '#586f58' }}
                      >
                        {expandedReferences.has(index) ? (
                          <>
                            <ChevronUp className="w-4 h-4" />
                            Hide References
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-4 h-4" />
                            See References
                          </>
                        )}
                      </button>
                      {expandedReferences.has(index) && (
                        <div className="mt-2 p-3 rounded-lg border text-sm glass-card" style={{ 
                          borderColor: 'rgba(255, 255, 255, 0.2)',
                          color: '#3a3a3a'
                        }}>
                          <div className="whitespace-pre-wrap opacity-90">{message.references}</div>
                        </div>
                      )}
                    </div>
                  )}
                  {message.isError && (
                    <div className="mt-2 text-sm font-semibold px-3 py-2 rounded border-2 border-alert-red" style={{ backgroundColor: '#B22222', color: '#FFFFFF' }}>Error occurred</div>
                  )}
                </div>
              </div>
            ))}
            
            {sendingMessage && (
              <div className="flex justify-start">
                <div className="chat-bubble-ai rounded-lg rounded-bl-none p-4">
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#FFFFFF' }} />
                </div>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>
          
          {/* Sticky Input Bar */}
          <div className="p-4 border-t" style={{ borderColor: 'rgba(255, 255, 255, 0.2)', backgroundColor: 'transparent' }}>
            <div className="flex gap-2">
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask a question about the filing..."
                className="glass-input flex-1 px-4 py-2 rounded-lg"
                style={{ color: '#3a3a3a' }}
                disabled={sendingMessage || !sessionId}
              />
              <button
                onClick={handleSendMessage}
                disabled={!userInput.trim() || sendingMessage || !sessionId}
                className="px-6 py-2 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 border-2 border-accent-amber"
                style={{ backgroundColor: '#FFC107', color: '#000000' }}
              >
                <Send className="w-5 h-5" />
                Send
              </button>
            </div>
          </div>
        </div>
        
        {/* Middle Section: Executive Summary */}
        {displayExecutiveSummary && (
          <div className="glass-card-enhanced rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2" style={{ color: '#586f58' }}>
              <FileText className="w-6 h-6" />
              Key Insights
            </h2>
            <div className="prose max-w-none" style={{ color: '#3a3a3a' }}>
              <p className="leading-relaxed whitespace-pre-wrap">{displayExecutiveSummary}</p>
            </div>
          </div>
        )}
        
        {/* Bottom Section: News Feed */}
        <div className="glass-card rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2" style={{ color: '#586f58' }}>
            <Newspaper className="w-6 h-6" />
            Market Context
          </h2>
          {displayNewsArticles.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {displayNewsArticles.map((article, index) => (
                <a
                  key={index}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="glass-card block p-4 rounded-lg hover:shadow-md transition-shadow"
                  style={{
                    color: '#3a3a3a'
                  }}
                >
                  <h3 className="font-semibold mb-2 line-clamp-2" style={{ color: '#3a3a3a' }}>
                    {article.title}
                  </h3>
                  {article.published_at && (
                    <p className="text-xs opacity-70 mb-2" style={{ color: '#3a3a3a' }}>
                      {new Date(article.published_at).toLocaleDateString()}
                    </p>
                  )}
                  <p className="text-xs opacity-60 truncate" style={{ color: '#3a3a3a' }}>
                    {article.url}
                  </p>
                </a>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 opacity-60" style={{ color: '#3a3a3a' }}>
              <Newspaper className="w-12 h-12 mx-auto mb-2 opacity-40" />
              <p>No news articles available at this time.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalysisPage

