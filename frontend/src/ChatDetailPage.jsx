import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, User, Bot, Calendar, FileText, Upload, ChevronDown, Loader2 } from 'lucide-react'

// Utility function to parse message content and extract references
function parseMessageContent(content) {
  if (!content || typeof content !== 'string') {
    return { answer: content || '', references: [] }
  }

  // Check if content contains references separator (handle variations)
  const referenceSeparatorRegex = /---\s*References?\s*---/i
  if (referenceSeparatorRegex.test(content)) {
    const parts = content.split(referenceSeparatorRegex)
    const answer = parts[0].trim()
    const referencesText = parts[1] ? parts[1].trim() : ''
    
    // Parse references - they're typically in format: "a. "quoted text" [Line X]"
    const references = []
    if (referencesText) {
      // Split by newlines and parse each reference
      const lines = referencesText.split('\n').filter(line => line.trim())
      lines.forEach((line, index) => {
        const trimmedLine = line.trim()
        
        // Match pattern: letter/number. "quoted text" [Line X] or similar formats
        // More flexible regex to handle various formats
        const quotedTextMatch = trimmedLine.match(/"([^"]+)"/)
        const locationMatch = trimmedLine.match(/\[([^\]]+)\]/)
        
        if (quotedTextMatch) {
          references.push({
            id: index,
            quotedText: quotedTextMatch[1],
            location: locationMatch ? locationMatch[1] : ''
          })
        } else if (trimmedLine) {
          // Fallback: if no quoted text found, store the line as-is
          references.push({
            id: index,
            quotedText: trimmedLine,
            location: locationMatch ? locationMatch[1] : ''
          })
        }
      })
    }
    
    return { answer, references }
  }
  
  return { answer: content, references: [] }
}

function ChatDetailPage() {
  const { sessionId } = useParams()
  const [chatDetails, setChatDetails] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedReferences, setExpandedReferences] = useState({}) // Track which message's references are expanded

  useEffect(() => {
    const fetchChatDetails = async () => {
      if (!sessionId) {
        setError('No session ID provided')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        
        const url = `/api/history/chat/${sessionId}`
        
        const response = await fetch(url)
        
        if (!response.ok) {
          const errorText = await response.text()
          
          if (response.status === 404) {
            setLoading(false)
            setChatDetails(null)
            setError(null) // Clear error to show "not found" message
            return
          }
          throw new Error(`HTTP error! status: ${response.status} - ${errorText}`)
        }
        
        const contentType = response.headers.get('content-type')
        
        if (!contentType || !contentType.includes('application/json')) {
          const text = await response.text()
          throw new Error('Response is not JSON')
        }
        
        const data = await response.json()
        
        if (!data) {
          setChatDetails(null)
        } else {
          setChatDetails(data)
        }
      } catch (err) {
        console.error('Failed to fetch chat details:', err)
        setError(err.message)
        setChatDetails(null)
      } finally {
        setLoading(false)
      }
    }

    if (sessionId) {
      fetchChatDetails()
    } else {
      setLoading(false)
    }
  }, [sessionId])

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16">
          <div className="text-center">
            <Loader2 className="w-16 h-16 animate-spin mx-auto mb-6 text-primary-green" />
            <p className="text-white text-lg">Loading chat details...</p>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16">
          <div className="glass-card rounded-lg p-8 max-w-2xl mx-auto">
            <div className="rounded-lg p-4 mb-4 border-2 border-alert-red" style={{ backgroundColor: '#B22222', color: '#FFFFFF' }}>
              <p className="font-bold">Error: {error}</p>
            </div>
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-white hover:underline"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Not found state - only show after loading is complete and no error
  if (!loading && !error && !chatDetails) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16">
          <div className="glass-card rounded-lg p-8 max-w-2xl mx-auto">
            <div className="text-center mb-4">
              <p className="text-white opacity-70">Chat session not found</p>
              <p className="text-sm text-white opacity-50 mt-2">Session ID: {sessionId}</p>
            </div>
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-white hover:underline"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // If we get here, chatDetails should exist
  if (!chatDetails) {
    return null
  }

  const metadata = chatDetails.metadata || {}
  const messages = chatDetails.messages || []
  const workflowType = chatDetails.workflow_type || 'UNKNOWN'
  const type = workflowType.toLowerCase() === 'sec' ? 'sec' : 'upload'
  const TypeIcon = type === 'sec' ? FileText : Upload

  const companyName = metadata.company || 'Unknown Company'
  const ticker = metadata.ticker || null
  const createdDate = chatDetails.created_at
    ? new Date(chatDetails.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    : 'Unknown date'

  return (
    <div className="min-h-screen">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-white hover:underline mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
          
          <div className="glass-card rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <TypeIcon className="w-6 h-6 text-primary-green" />
              <h1 className="text-2xl font-bold text-white">
                {companyName}
              </h1>
              {ticker && (
                <span className="px-3 py-1 bg-accent-amber/90 text-white text-sm font-semibold rounded-md shadow-md">
                  {ticker}
                </span>
              )}
              <span className="px-3 py-1 bg-accent-orange/90 text-white text-xs font-semibold rounded-md uppercase shadow-md">
                {type}
              </span>
            </div>
            
            <div className="flex items-center gap-4 text-sm text-white opacity-70">
              <div className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                <span>{createdDate}</span>
              </div>
              <span>{messages.length} message{messages.length !== 1 ? 's' : ''}</span>
            </div>

            {metadata && (
              <div className="mt-4 pt-4 border-t border-primary-green/30 text-xs text-white opacity-60">
                {metadata.doc_type && (
                  <span>Document: {metadata.doc_type}</span>
                )}
                {metadata.filing_date && (
                  <span className="ml-4">Filed: {metadata.filing_date}</span>
                )}
                {metadata.year && (
                  <span className="ml-4">Year: {metadata.year}</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Chat Messages */}
        <div className="glass-card rounded-lg p-6">
          <h2 className="text-xl font-bold text-white mb-6">Conversation</h2>
          
          {messages.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-white opacity-70">No messages in this conversation.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => {
                const isUser = message.role === 'user'
                const messageDate = message.timestamp
                  ? new Date(message.timestamp).toLocaleString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : null

                // Parse message content to extract answer and references
                const { answer, references } = isUser 
                  ? { answer: message.content, references: [] }
                  : parseMessageContent(message.content)
                
                const hasReferences = references && references.length > 0
                const isExpanded = expandedReferences[index] || false

                return (
                  <div
                    key={index}
                    className={`flex gap-4 ${
                      isUser ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-3xl rounded-lg p-4 ${
                        isUser
                          ? 'chat-bubble-user'
                          : 'chat-bubble-ai'
                      }`}
                      style={{
                        color: isUser ? '#000000' : '#FFFFFF',
                        backgroundColor: isUser ? 'rgba(218, 200, 160, 0.85)' : 'rgba(52, 116, 51, 0.3)'
                      }}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {isUser ? (
                          <User className="w-4 h-4" style={{ color: '#000000' }} />
                        ) : (
                          <Bot className="w-4 h-4" style={{ color: '#FFFFFF' }} />
                        )}
                        <span className={`text-xs font-semibold opacity-80 ${isUser ? 'text-black' : 'text-white'}`}>
                          {isUser ? 'You' : 'Assistant'}
                        </span>
                        {messageDate && (
                          <span className={`text-xs opacity-70 ml-auto ${isUser ? 'text-black' : 'text-white'}`}>
                            {messageDate}
                          </span>
                        )}
                      </div>
                      <div className="whitespace-pre-wrap break-words" style={{ color: isUser ? '#000000' : '#FFFFFF' }}>
                        {answer}
                      </div>
                      
                      {/* References Section */}
                      {hasReferences && (
                        <div className="mt-3">
                          <button
                            onClick={() => setExpandedReferences(prev => ({
                              ...prev,
                              [index]: !prev[index]
                            }))}
                            className="flex items-center gap-2 text-sm border border-primary-green rounded px-3 py-1.5 hover:bg-primary-green/20 transition-colors"
                            style={{ color: isUser ? '#000000' : '#FFFFFF', borderColor: 'rgba(52, 116, 51, 0.5)' }}
                          >
                            <span>View References</span>
                            <ChevronDown 
                              className={`w-4 h-4 transition-transform duration-200 ${
                                isExpanded ? 'transform rotate-180' : ''
                              }`}
                            />
                          </button>
                          
                          {/* Expandable References Subcard */}
                          <div
                            className={`overflow-hidden transition-all duration-300 ease-in-out ${
                              isExpanded ? 'max-h-[2000px] opacity-100 mt-3' : 'max-h-0 opacity-0'
                            }`}
                          >
                            <div 
                              className="rounded-lg p-4 border border-primary-green/30"
                              style={{ backgroundColor: 'rgba(52, 116, 51, 0.2)' }}
                            >
                              <h4 className="text-sm font-semibold mb-3 text-white">
                                References
                              </h4>
                              <div className="space-y-3">
                                {references.map((ref) => (
                                  <div 
                                    key={ref.id}
                                    className="border-l-2 border-primary-green pl-3 py-2"
                                  >
                                    {ref.location && (
                                      <div className="text-xs font-medium mb-1 text-white opacity-80">
                                        {ref.location}
                                      </div>
                                    )}
                                    <div 
                                      className="text-sm italic text-white"
                                    >
                                      "{ref.quotedText}"
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ChatDetailPage

