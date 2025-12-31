import { createContext, useContext, useState, useEffect } from 'react'

const WorkflowContext = createContext()

const ACTIVE_SESSION_KEY = 'finscope_active_session'

export const useWorkflow = () => {
  const context = useContext(WorkflowContext)
  if (!context) {
    throw new Error('useWorkflow must be used within WorkflowProvider')
  }
  return context
}

export const WorkflowProvider = ({ children }) => {
  const [backendStatus, setBackendStatus] = useState('Offline')
  const [secWorkflowData, setSecWorkflowDataState] = useState(null)
  const [analysisData, setAnalysisData] = useState(null) // { sessionId, executiveSummary, newsArticles, chatMessages, sourceType }
  const [selectionMetadata, setSelectionMetadata] = useState(null) // { ticker, company_name, selected_filing }
  const [analysisLoading, setAnalysisLoading] = useState(false)
  
  // Upload flow state variables - initialize from localStorage for immediate form population
  const [uploadMetadata, setUploadMetadata] = useState(() => {
    try {
      const stored = localStorage.getItem('finscope_upload_meta')
      return stored ? JSON.parse(stored) : null
    } catch (error) {
      console.error('Failed to load upload metadata from localStorage:', error)
      return null
    }
  }) // { companyName, docTitle, docType, year }
  const [selectedUploadFile, setSelectedUploadFile] = useState(null) // file object/name
  const [uploadAnalysisData, setUploadAnalysisData] = useState(() => {
    try {
      const stored = localStorage.getItem('finscope_upload_data')
      return stored ? JSON.parse(stored) : null
    } catch (error) {
      console.error('Failed to load upload analysis data from localStorage:', error)
      return null
    }
  }) // backend response

  // Load active session from localStorage on initialization
  useEffect(() => {
    try {
      const stored = localStorage.getItem(ACTIVE_SESSION_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed.analysisData) {
          setAnalysisData(parsed.analysisData)
        }
        if (parsed.selectionMetadata) {
          setSelectionMetadata(parsed.selectionMetadata)
        }
        if (parsed.secWorkflowData) {
          setSecWorkflowData(parsed.secWorkflowData)
        }
      }
      // Note: uploadMetadata and uploadAnalysisData are initialized directly from localStorage
      // in their useState initializers for immediate form population
    } catch (error) {
      console.error('Failed to load active session from localStorage:', error)
    }
  }, [])

  // Save to localStorage whenever analysisData, selectionMetadata, or secWorkflowData changes
  useEffect(() => {
    try {
      const sessionData = {
        analysisData,
        selectionMetadata,
        secWorkflowData,
        timestamp: new Date().toISOString()
      }
      
      if (analysisData || selectionMetadata || secWorkflowData) {
        localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(sessionData))
      } else {
        // Clear localStorage if all data is null
        localStorage.removeItem(ACTIVE_SESSION_KEY)
      }
    } catch (error) {
      console.error('Failed to save active session to localStorage:', error)
    }
  }, [analysisData, selectionMetadata, secWorkflowData])

  // Save upload data to localStorage whenever uploadMetadata or uploadAnalysisData changes
  useEffect(() => {
    try {
      if (uploadMetadata) {
        localStorage.setItem('finscope_upload_meta', JSON.stringify(uploadMetadata))
      } else {
        localStorage.removeItem('finscope_upload_meta')
      }
      
      if (uploadAnalysisData) {
        localStorage.setItem('finscope_upload_data', JSON.stringify(uploadAnalysisData))
      } else {
        localStorage.removeItem('finscope_upload_data')
      }
    } catch (error) {
      console.error('Failed to save upload data to localStorage:', error)
    }
  }, [uploadMetadata, uploadAnalysisData])

  // Wrapper for setSecWorkflowData that also updates selectionMetadata
  const updateSecWorkflowData = (data) => {
    setSecWorkflowDataState(data)
    if (data) {
      setSelectionMetadata({
        ticker: data.ticker,
        company_name: data.company_name,
        selected_filing: data.selected_filing
      })
    } else {
      setSelectionMetadata(null)
    }
  }

  // Clear all session data
  const clearActiveSession = () => {
    setAnalysisData(null)
    setSelectionMetadata(null)
    setSecWorkflowData(null)
    localStorage.removeItem(ACTIVE_SESSION_KEY)
  }

  return (
    <WorkflowContext.Provider value={{ 
      backendStatus, 
      setBackendStatus,
      secWorkflowData,
      setSecWorkflowData: updateSecWorkflowData,
      analysisData,
      setAnalysisData,
      selectionMetadata,
      setSelectionMetadata,
      uploadMetadata,
      setUploadMetadata,
      selectedUploadFile,
      setSelectedUploadFile,
      uploadAnalysisData,
      setUploadAnalysisData,
      analysisLoading,
      setAnalysisLoading,
      clearActiveSession
    }}>
      {children}
    </WorkflowContext.Provider>
  )
}

