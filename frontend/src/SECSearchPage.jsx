import { useState, useEffect, useRef } from 'react'
import { Search, CheckCircle2, FileText, ArrowRight, X, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useWorkflow } from './WorkflowContext'

function SECSearchPage() {
  const navigate = useNavigate()
  const { 
    secWorkflowData, 
    setSecWorkflowData, 
    analysisData, 
    setAnalysisData,
    selectionMetadata 
  } = useWorkflow()
  const hasInitializedRef = useRef(false)
  const hasRestoredFromContextRef = useRef(false)
  
  // Step 1: Company Search
  const [searchQuery, setSearchQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const debounceTimerRef = useRef(null)
  const searchInputRef = useRef(null)
  const suggestionsRef = useRef(null)

  // Step 2: Filing Selection
  const [filings, setFilings] = useState([])
  const [loadingFilings, setLoadingFilings] = useState(false)
  const [selectedFiling, setSelectedFiling] = useState(null)

  // Conflict dialog state
  const [showConflictDialog, setShowConflictDialog] = useState(false)
  const [conflictData, setConflictData] = useState(null) // { existingTicker, currentTicker, currentFilingId }

  // Back button warning dialog state
  const [showBackWarningDialog, setShowBackWarningDialog] = useState(false)

  // Helper function to fetch filings (extracted for reuse)
  const handleFetchFilingsForCompany = async (ticker, restoreFiling = null) => {
    if (!ticker) return

    setLoadingFilings(true)
    try {
      const response = await fetch(`/api/get-filings?ticker=${encodeURIComponent(ticker)}`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setFilings(data)
      
      // If we have a filing to restore, select it
      if (restoreFiling) {
        const filingToSelect = data.find(
          f => f.accession_number === restoreFiling.accession_number
        )
        if (filingToSelect) {
          setSelectedFiling(filingToSelect)
        } else {
          // Filing not found in list, but we still want to keep it selected
          setSelectedFiling(restoreFiling)
        }
      }
    } catch (error) {
      console.error('Failed to fetch filings:', error)
      alert(`Failed to fetch filings: ${error.message}`)
    } finally {
      setLoadingFilings(false)
    }
  }

  // Restore selections from WorkflowContext on mount
  useEffect(() => {
    if (!hasRestoredFromContextRef.current && secWorkflowData) {
      hasRestoredFromContextRef.current = true
      
      // Restore company selection
      if (secWorkflowData.company_name && secWorkflowData.ticker) {
        const restoredCompany = {
          company_name: secWorkflowData.company_name,
          ticker: secWorkflowData.ticker
        }
        setSelectedCompany(restoredCompany)
        setSearchQuery(`${secWorkflowData.company_name} (${secWorkflowData.ticker})`)
        
        // Auto-fetch filings and restore filing selection if available
        if (secWorkflowData.selected_filing) {
          handleFetchFilingsForCompany(secWorkflowData.ticker, secWorkflowData.selected_filing)
        } else {
          // Still fetch filings even if no filing was selected
          handleFetchFilingsForCompany(secWorkflowData.ticker)
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secWorkflowData])

  // Hard refresh detection: Only clear if no context data exists
  useEffect(() => {
    if (!hasInitializedRef.current) {
      hasInitializedRef.current = true
      // Only clear on hard refresh if there's no context data to restore
      if (!secWorkflowData && !selectionMetadata) {
        setSelectedCompany(null)
        setSearchQuery('')
        setFilings([])
        setSelectedFiling(null)
      }
    }
  }, [])

  // Debounced search function
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    if (!searchQuery.trim()) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }

    if (selectedCompany) {
      // Don't search if a company is already selected
      return
    }

    debounceTimerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        // Call Master Controller endpoint (proxied through vite)
        const response = await fetch(`/api/search-company?query=${encodeURIComponent(searchQuery)}`)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        const data = await response.json()
        setSuggestions(data)
        setShowSuggestions(true)
      } catch (error) {
        console.error('Failed to search companies:', error)
        setSuggestions([])
        setShowSuggestions(false)
      } finally {
        setLoading(false)
      }
    }, 1000) // 1 second debounce

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [searchQuery, selectedCompany])

  // Handle click outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target) &&
        searchInputRef.current &&
        !searchInputRef.current.contains(event.target)
      ) {
        setShowSuggestions(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const handleCompanySelect = (company) => {
    setSelectedCompany(company)
    setSearchQuery(`${company.company_name} (${company.ticker})`)
    setShowSuggestions(false)
    setSuggestions([])
  }

  const handleClearSelection = () => {
    setSelectedCompany(null)
    setSearchQuery('')
    setFilings([])
    setSelectedFiling(null)
  }

  const handleFetchFilings = async () => {
    if (!selectedCompany) return
    await handleFetchFilingsForCompany(selectedCompany.ticker, null)
  }

  const handleStartAnalysis = () => {
    if (!selectedCompany || !selectedFiling) return

    // Check for conflict: existing analysis for different ticker/filing
    const currentTicker = selectedCompany.ticker
    const currentFilingId = selectedFiling.accession_number
    
    if (analysisData && selectionMetadata) {
      const existingTicker = selectionMetadata.ticker
      const existingFilingId = selectionMetadata.selected_filing?.accession_number
      
      // Conflict detected if ticker or filing is different
      if (existingTicker !== currentTicker || existingFilingId !== currentFilingId) {
        // Store conflict data and show dialog
        setConflictData({
          existingTicker: existingTicker || 'another company',
          currentTicker,
          currentFilingId
        })
        setShowConflictDialog(true)
        return
      }
    }

    // No conflict - proceed directly
    proceedWithNewAnalysis()
  }

  const proceedWithNewAnalysis = async () => {
    if (!selectedCompany || !selectedFiling) return

    // End the old session if there's an existing sessionId
    if (analysisData?.sessionId) {
      try {
        const response = await fetch('/api/end-session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            sessionId: analysisData.sessionId
          })
        })
        
        if (!response.ok) {
          console.error('Failed to end session:', await response.json())
          // Continue anyway - don't block the user
        }
      } catch (err) {
        console.error('Error ending session:', err)
        // Continue anyway - don't block the user
      }
    }

    // Clear old data
    if (setAnalysisData) {
      setAnalysisData(null)
    }
    // Clear secWorkflowData which will also clear selectionMetadata
    if (setSecWorkflowData) {
      setSecWorkflowData(null)
    }
    // Clear localStorage
    localStorage.removeItem('finscope_active_session')

    // Store in WorkflowContext
    const workflowData = {
      ticker: selectedCompany.ticker,
      company_name: selectedCompany.company_name,
      selected_filing: selectedFiling
    }
    
    if (setSecWorkflowData) {
      setSecWorkflowData(workflowData)
    }

    // Close dialog if open
    setShowConflictDialog(false)
    setConflictData(null)

    // Navigate to analysis page
    navigate('/analysis')
  }

  const handleResumeExistingAnalysis = () => {
    // Close dialog
    setShowConflictDialog(false)
    setConflictData(null)
    
    // Navigate to existing analysis
    navigate('/analysis')
  }

  const handleResumeAnalysis = () => {
    // Simply navigate to analysis page - it will use cached data
    navigate('/analysis')
  }

  // Check if we have analysis data for the current selection
  const hasAnalysisForCurrentSelection = () => {
    if (!analysisData || !selectionMetadata || !selectedFiling) return false
    
    const currentTicker = selectedCompany?.ticker
    const currentFilingId = selectedFiling.accession_number
    const storedTicker = selectionMetadata.ticker
    const storedFilingId = selectionMetadata.selected_filing?.accession_number
    
    return currentTicker === storedTicker && currentFilingId === storedFilingId
  }

  const handleBackClick = () => {
    // Check if there's an active session (selection or analysis data)
    const hasActiveSession = 
      (selectedCompany || selectedFiling) || 
      analysisData || 
      secWorkflowData || 
      selectionMetadata

    if (hasActiveSession) {
      // Show custom warning dialog
      setShowBackWarningDialog(true)
    } else {
      // No active session - navigate directly
      navigate('/')
    }
  }

  const handleBackConfirm = async () => {
    // End the session if there's an existing sessionId
    if (analysisData?.sessionId) {
      try {
        const response = await fetch('/api/end-session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            sessionId: analysisData.sessionId
          })
        })
        
        if (!response.ok) {
          console.error('Failed to end session:', await response.json())
          // Continue anyway - don't block the user
        }
      } catch (err) {
        console.error('Error ending session:', err)
        // Continue anyway - don't block the user
      }
    }

    // User confirmed - clear everything
    setSelectedCompany(null)
    setSearchQuery('')
    setFilings([])
    setSelectedFiling(null)
    
    // Clear WorkflowContext
    if (setSecWorkflowData) {
      setSecWorkflowData(null)
    }
    if (setAnalysisData) {
      setAnalysisData(null)
    }
    
    // Clear localStorage
    localStorage.removeItem('finscope_active_session')
    
    // Close dialog
    setShowBackWarningDialog(false)
    
    // Navigate to landing page
    navigate('/')
  }

  const handleBackCancel = () => {
    // User cancelled - stay on the page
    setShowBackWarningDialog(false)
  }

  return (
    <div className="min-h-screen">
      {/* Back Button Warning Dialog */}
      {showBackWarningDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold mb-4" style={{ color: '#000000' }}>
              End Session
            </h2>
            <p className="mb-6" style={{ color: '#000000' }}>
              Leaving this page will end your current session. Do you want to proceed?
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleBackCancel}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
              >
                Cancel
              </button>
              <button
                onClick={handleBackConfirm}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: '#B22222', color: 'white' }}
              >
                Proceed
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Conflict Dialog */}
      {showConflictDialog && conflictData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-2xl font-semibold mb-4" style={{ color: '#586f58' }}>
              Analysis Conflict
            </h2>
            <p className="mb-6" style={{ color: '#3a3a3a' }}>
              You have an active analysis for <strong>{conflictData.existingTicker}</strong>. Starting a new one will replace it. Continue?
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleResumeExistingAnalysis}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
              >
                Resume Existing
              </button>
              <button
                onClick={proceedWithNewAnalysis}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 flex items-center gap-2"
                style={{ backgroundColor: '#586f58', color: 'white' }}
              >
                Start New
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
      
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={handleBackClick}
            className="px-4 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 flex items-center gap-2"
            style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
          >
            <ArrowLeft className="w-5 h-5" />
            Back
          </button>
          <h1 className="text-4xl font-bold" style={{ color: '#3a3a3a' }}>
            SEC Filing Analysis
          </h1>
        </div>

        {/* Step 1: Company Search */}
        <div className="glass-card rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4" style={{ color: '#3a3a3a' }}>
            Step 1: Search for Company
          </h2>
          
          <div className="relative">
            <div className="flex items-center gap-2">
              <Search className="w-5 h-5 text-primary-green" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  if (selectedCompany) {
                    handleClearSelection()
                  }
                }}
                placeholder="Type company name or ticker..."
                className="company-search-input flex-1 px-4 py-2 rounded-lg border-2 border-primary-green/30 focus:border-accent-amber focus:ring-4 focus:ring-accent-amber/30 focus:outline-none transition-all"
                style={{ 
                  backgroundColor: '#347433',
                  color: '#FFC107',
                  caretColor: '#FFC107'
                }}
                disabled={!!selectedCompany}
              />
              {selectedCompany && (
                <button
                  onClick={handleClearSelection}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="Clear selection"
                >
                  <X className="w-5 h-5" style={{ color: '#3a3a3a' }} />
                </button>
              )}
            </div>

            {/* Loading indicator */}
            {loading && (
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2" style={{ borderColor: '#586f58' }}></div>
              </div>
            )}

            {/* Suggestions dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute z-10 w-full mt-2 border-2 border-primary-green rounded-lg shadow-lg max-h-60 overflow-y-auto"
                style={{ backgroundColor: 'rgba(52, 116, 51, 0.95)' }}
              >
                {suggestions.map((company, index) => {
                  const isEven = index % 2 === 0
                  const baseBg = isEven ? 'rgba(52, 116, 51, 0.95)' : 'rgba(34, 92, 33, 0.95)'
                  
                  return (
                    <div
                      key={index}
                      onClick={() => handleCompanySelect(company)}
                      className="px-4 py-3 cursor-pointer transition-all border-b border-primary-green/50 last:border-b-0 hover:scale-[1.02] hover:shadow-lg hover:z-10 hover:border-primary-green"
                      style={{ 
                        backgroundColor: baseBg,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = isEven ? 'rgba(52, 116, 51, 1)' : 'rgba(34, 92, 33, 1)'
                        e.currentTarget.style.boxShadow = '0 4px 12px rgba(52, 116, 51, 0.5)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = baseBg
                        e.currentTarget.style.boxShadow = 'none'
                      }}
                    >
                      <div className="font-semibold text-white">
                        {company.company_name}
                      </div>
                      <div className="text-sm font-medium text-white opacity-90">
                        {company.ticker}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Selected Company Display */}
            {selectedCompany && (
              <div className="mt-4 p-4 rounded-lg border-2 border-primary-green" style={{ backgroundColor: 'rgba(52, 116, 51, 0.4)', color: '#FFFFFF' }}>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-accent-amber" />
                  <div>
                    <div className="font-bold text-white">
                      Selected: {selectedCompany.company_name}
                    </div>
                    <div className="text-sm font-semibold text-white">
                      Ticker: {selectedCompany.ticker}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Fetch Filings Button */}
            {selectedCompany && (
              <button
                onClick={handleFetchFilings}
                disabled={loadingFilings}
                className="glossy-button mt-4 px-6 py-2 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed border-2 border-accent-amber"
                style={{ color: 'white' }}
              >
                {loadingFilings ? 'Fetching...' : 'Fetch Filings'}
              </button>
            )}
          </div>
        </div>

        {/* Step 2: Filing Selection */}
        {filings.length > 0 && (
          <div className="glass-card rounded-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4" style={{ color: '#3a3a3a' }}>
              Step 2: Select Filing
            </h2>

            <div className="space-y-2 max-h-96 overflow-y-auto">
              {filings.map((filing, index) => (
                <label
                  key={index}
                  className={`flex items-center gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    selectedFiling?.accession_number === filing.accession_number
                      ? 'border-brand-forest bg-opacity-20'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  style={{
                    backgroundColor:
                      selectedFiling?.accession_number === filing.accession_number
                        ? 'rgba(88, 111, 88, 0.1)'
                        : 'transparent',
                    borderColor:
                      selectedFiling?.accession_number === filing.accession_number
                        ? '#586f58'
                        : '#e5e7eb'
                  }}
                >
                  <input
                    type="radio"
                    name="filing"
                    checked={selectedFiling?.accession_number === filing.accession_number}
                    onChange={() => setSelectedFiling(filing)}
                    className="w-5 h-5"
                    style={{ accentColor: '#586f58' }}
                  />
                  <FileText className="w-5 h-5" style={{ color: '#586f58' }} />
                  <div className="flex-1">
                    <div className="font-semibold" style={{ color: '#3a3a3a' }}>
                      {filing.form_type}
                    </div>
                    <div className="text-sm opacity-70" style={{ color: '#3a3a3a' }}>
                      Filed: {filing.filing_date}
                    </div>
                    <div className="text-xs opacity-50 mt-1" style={{ color: '#3a3a3a' }}>
                      {filing.accession_number}
                    </div>
                  </div>
                </label>
              ))}
            </div>

            {/* Action Buttons */}
            {selectedFiling && (
              <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center items-center">
                {/* Resume Analysis Button - only show if analysis exists for current selection */}
                {hasAnalysisForCurrentSelection() ? (
                  <button
                    onClick={handleResumeAnalysis}
                    className="px-8 py-3 rounded-lg font-semibold text-lg flex items-center gap-2 border-2 border-accent-amber"
                    style={{ backgroundColor: '#FFC107', color: '#000000' }}
                  >
                    Resume Analysis
                    <ArrowRight className="w-5 h-5" />
                  </button>
                ) : (
                  /* Start Analysis Button - only show if selection changed or no analysis exists */
                  <button
                    onClick={handleStartAnalysis}
                    className="px-8 py-3 rounded-lg font-semibold text-lg flex items-center gap-2 border-2 border-accent-amber"
                    style={{ backgroundColor: '#FFC107', color: '#000000' }}
                  >
                    Start Analysis
                    <ArrowRight className="w-5 h-5" />
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3 indicator */}
        {selectedFiling && (
          <div className="glass-card rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4" style={{ color: '#3a3a3a' }}>
              Step 3: Ready to Analyze
            </h2>
            <div className="p-4 rounded-lg border-2 border-primary-green" style={{ backgroundColor: 'rgba(52, 116, 51, 0.4)', color: '#FFFFFF' }}>
              <div className="text-sm font-semibold">
                <div className="mb-2 text-white">
                  <strong>Company:</strong> {selectedCompany.company_name} ({selectedCompany.ticker})
                </div>
                <div className="mb-2 text-white">
                  <strong>Filing:</strong> {selectedFiling.form_type} - {selectedFiling.filing_date}
                </div>
                <div className="text-white">
                  <strong>Accession:</strong> {selectedFiling.accession_number}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SECSearchPage

