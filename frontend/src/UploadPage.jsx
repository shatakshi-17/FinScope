import { useState, useRef, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Upload, FileText, X, ArrowRight, Loader2 } from 'lucide-react'
import { useWorkflow } from './WorkflowContext'
import ActionModal from './ActionModal'

function UploadPage() {
  const navigate = useNavigate()
  const { 
    uploadMetadata, 
    setUploadMetadata, 
    selectedUploadFile, 
    setSelectedUploadFile, 
    uploadAnalysisData, 
    setUploadAnalysisData,
    analysisData,
    setAnalysisData,
    setAnalysisLoading
  } = useWorkflow()
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)
  const [submittedMetadata, setSubmittedMetadata] = useState(null)
  const [submittedFileName, setSubmittedFileName] = useState(null)
  const [showReplaceModal, setShowReplaceModal] = useState(false)
  const [showBackWarningModal, setShowBackWarningModal] = useState(false)
  const [fileError, setFileError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [loadingTeaser, setLoadingTeaser] = useState(0)
  
  // Loading teasers for upload flow
  const uploadLoadingTeasers = [
    'Processing your local document...',
    'Gemini is reading your PDF/TXT...',
    'RAG Initialization: Building a searchable vector index of the document...',
    'AI Synthesis: Gemini is generating your executive summary...',
    'Market Context: Gathering real-time news for broader perspective...'
  ]
  
  // Rotate loading teasers
  useEffect(() => {
    if (!isLoading) return
    
    const interval = setInterval(() => {
      setLoadingTeaser((prev) => (prev + 1) % uploadLoadingTeasers.length)
    }, 5000)
    
    return () => clearInterval(interval)
  }, [isLoading, uploadLoadingTeasers.length])

  // Clear metadata when component mounts if there's no active analysis (remove past suggestions)
  useEffect(() => {
    const hasActiveAnalysis = uploadAnalysisData && uploadAnalysisData.sessionId
    const isUploadWorkflow = analysisData && analysisData.sourceType === 'upload'
    
    if (!hasActiveAnalysis || !isUploadWorkflow) {
      // Clear metadata to remove suggestions from past uploads
      setUploadMetadata(null)
      setSelectedUploadFile(null)
      setSubmittedMetadata(null)
      setSubmittedFileName(null)
    }
  }, []) // Only run on mount

  // Store submitted metadata when analysis is created
  useEffect(() => {
    const hasActiveAnalysis = uploadAnalysisData && uploadAnalysisData.sessionId
    const isUploadWorkflow = analysisData && analysisData.sourceType === 'upload'
    
    if (hasActiveAnalysis && isUploadWorkflow) {
      // If we have submitted metadata in uploadAnalysisData, use it
      if (uploadAnalysisData.submittedMetadata) {
        setSubmittedMetadata(uploadAnalysisData.submittedMetadata)
        setSubmittedFileName(uploadAnalysisData.submittedFileName || '')
      } else if (uploadMetadata && !submittedMetadata) {
        // Otherwise, store current metadata as submitted (first time we see an analysis)
        setSubmittedMetadata({ ...uploadMetadata })
        setSubmittedFileName(selectedUploadFile?.name || '')
      }
    } else {
      // Clear submitted metadata if no active analysis
      setSubmittedMetadata(null)
      setSubmittedFileName(null)
    }
  }, [uploadAnalysisData, analysisData, uploadMetadata, selectedUploadFile, submittedMetadata])

  // Compare current form inputs with active analysis metadata to determine if form is dirty
  const isDirty = useMemo(() => {
    // If there's no active analysis, form is not dirty (nothing to compare against)
    const hasActiveAnalysis = uploadAnalysisData && uploadAnalysisData.sessionId
    const isUploadWorkflow = analysisData && analysisData.sourceType === 'upload'
    
    if (!hasActiveAnalysis || !isUploadWorkflow) {
      return false
    }

    // If we don't have submitted metadata stored yet, form is not dirty (can't compare)
    if (!submittedMetadata) {
      return false
    }

    // Get the current form values
    const currentMetadata = {
      companyName: (uploadMetadata?.companyName || '').trim(),
      docTitle: (uploadMetadata?.docTitle || '').trim(),
      docType: (uploadMetadata?.docType || '').trim(),
      year: uploadMetadata?.year || ''
    }
    const currentFileName = selectedUploadFile?.name || ''

    // Compare current values with submitted values
    const metadataMatches = 
      (currentMetadata.companyName === (submittedMetadata?.companyName || '').trim()) &&
      (currentMetadata.docTitle === (submittedMetadata?.docTitle || '').trim()) &&
      (currentMetadata.docType === (submittedMetadata?.docType || '').trim()) &&
      (String(currentMetadata.year) === String(submittedMetadata?.year || ''))
    
    const fileNameMatches = currentFileName === (submittedFileName || '')

    // Form is dirty if any field doesn't match
    return !(metadataMatches && fileNameMatches)
  }, [uploadMetadata, selectedUploadFile, uploadAnalysisData, analysisData, submittedMetadata, submittedFileName])

  // Determine button text based on analysis state
  const buttonText = useMemo(() => {
    const hasActiveAnalysis = uploadAnalysisData && uploadAnalysisData.sessionId
    
    if (hasActiveAnalysis) {
      return isDirty ? 'Start New Analysis' : 'Resume Analysis'
    }
    return 'Start Analysis'
  }, [uploadAnalysisData, isDirty])

  const handleInputChange = (field, value) => {
    setUploadMetadata(prev => ({
      ...(prev || {}),
      [field]: value
    }))
  }

  const handleFileSelect = (file) => {
    if (!file) {
      return
    }

    // Clear previous error
    setFileError(null)

    // Validate file type
    const allowedExtensions = ['.pdf', '.txt' ]
    const fileName = file.name.toLowerCase()
    const fileExtension = fileName.substring(fileName.lastIndexOf('.'))
    
    if (!allowedExtensions.includes(fileExtension)) {
      setFileError(`Invalid file type. Please select a PDF or TXT file.`)
      setSelectedUploadFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }

    // Validate file size (10MB = 10 * 1024 * 1024 bytes)
    const maxSize = 10 * 1024 * 1024 // 10MB in bytes
    if (file.size > maxSize) {
      const fileSizeMB = (file.size / 1024 / 1024).toFixed(2)
      setFileError(`File size (${fileSizeMB} MB) exceeds the 10MB limit. Please select a smaller file.`)
      setSelectedUploadFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }

    // File is valid
    setSelectedUploadFile(file)
  }

  const handleDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleFileInputChange = (e) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleRemoveFile = () => {
    setSelectedUploadFile(null)
    setFileError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // Check if there's an active upload session or metadata
  const hasActiveSession = () => {
    const hasAnalysis = uploadAnalysisData && uploadAnalysisData.sessionId
    const hasMetadata = uploadMetadata && (
      uploadMetadata.companyName || 
      uploadMetadata.docTitle || 
      uploadMetadata.docType || 
      uploadMetadata.year
    )
    const hasFile = selectedUploadFile !== null
    
    return hasAnalysis || hasMetadata || hasFile
  }

  const handleBackClick = () => {
    if (hasActiveSession()) {
      // Show warning modal
      setShowBackWarningModal(true)
    } else {
      // No active session, navigate directly
      navigate('/')
    }
  }

  const handleBackCancel = () => {
    setShowBackWarningModal(false)
  }

  const handleBackProceed = () => {
    // Clear all upload-related data
    setUploadAnalysisData(null)
    setUploadMetadata(null)
    setSelectedUploadFile(null)
    setSubmittedMetadata(null)
    setSubmittedFileName(null)
    
    // Clear upload data from localStorage
    localStorage.removeItem('finscope_upload_data')
    localStorage.removeItem('finscope_upload_meta')
    
    // Clear analysisData if it's from upload workflow
    if (analysisData && analysisData.sourceType === 'upload') {
      setAnalysisData(null)
    }
    
    // Close modal and navigate
    setShowBackWarningModal(false)
    navigate('/')
  }

  const handleButtonClick = () => {
    if (buttonText === 'Resume Analysis') {
      // Simply navigate to analysis page without any state
      // This will make AnalysisPage treat it as a resume and skip loading screen
      navigate('/analysis')
    } else if (buttonText === 'Start New Analysis') {
      // Show confirmation modal
      setShowReplaceModal(true)
    } else {
      // For "Start Analysis", handle the submission
      handleStartAnalysis()
    }
  }

  const handleResumeCurrent = () => {
    setShowReplaceModal(false)
    navigate('/analysis')
  }

  const handleStartAnalysis = async () => {
    // Validate required fields
    if (!selectedUploadFile) {
      setFileError('Please select a file to upload.')
      return
    }
    
    const companyName = (uploadMetadata?.companyName || '').trim()
    if (!companyName) {
      // Show error - company name is required
      alert('Please enter a company name.')
      return
    }
    
    // Create FormData object
    const formData = new FormData()
    
    // Append the selected file (required)
    formData.append('file', selectedUploadFile)
    
    // Append required companyName
    formData.append('companyName', companyName)
    
    // Append optional metadata fields
    if (uploadMetadata) {
      if (uploadMetadata.docTitle) {
        formData.append('docTitle', uploadMetadata.docTitle)
      }
      if (uploadMetadata.docType) {
        formData.append('docType', uploadMetadata.docType)
      }
      if (uploadMetadata.year) {
        formData.append('year', String(uploadMetadata.year))
      }
    }
    
    // Set loading state
    setIsLoading(true)
    setAnalysisLoading(true)

    try {
      // POST to /api/upload-analysis
      const response = await fetch('/api/upload-analysis', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`)
      }

      // Parse JSON response
      const data = await response.json()

      // Save the entire response to uploadAnalysisData
      // Include submitted metadata for isDirty tracking
      const responseWithMetadata = {
        ...data,
        submittedMetadata: { ...uploadMetadata },
        submittedFileName: selectedUploadFile?.name || ''
      }
      setUploadAnalysisData(responseWithMetadata)

      // Also update analysisData with the proper structure for AnalysisPage
      setAnalysisData({
        sessionId: data.sessionId,
        executiveSummary: data.executiveSummary || '',
        newsArticles: data.newsArticles || [],
        chatMessages: [],
        sourceType: 'upload'
      })

      // Store submitted metadata for isDirty tracking
      setSubmittedMetadata({ ...uploadMetadata })
      setSubmittedFileName(selectedUploadFile?.name || '')

      // Navigate to analysis page with state indicating it's a fresh upload
      navigate('/analysis', { state: { isUpload: true } })
    } catch (error) {
      console.error('Failed to start upload analysis:', error)
      // TODO: Show error message to user
      setIsLoading(false)
    } finally {
      setAnalysisLoading(false)
    }
  }

  const handleProceedWithNew = () => {
    // Clear upload-specific data from context
    setUploadAnalysisData(null)
    setSelectedUploadFile(null)
    
    // Clear upload analysis data from localStorage
    localStorage.removeItem('finscope_upload_data')
    
    // Clear analysisData if it's from upload workflow
    if (analysisData && analysisData.sourceType === 'upload') {
      setAnalysisData(null)
    }
    
    // Clear submitted metadata state
    setSubmittedMetadata(null)
    setSubmittedFileName(null)
    
    // Close modal
    setShowReplaceModal(false)
    
    // Start new upload flow
    handleStartAnalysis()
  }

  // Loading Screen
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-16 h-16 animate-spin mx-auto mb-6 text-primary-green" />
          <h2 className="text-2xl font-semibold mb-4 text-white">
            Preparing Your Analysis
          </h2>
          <p className="text-lg max-w-md mx-auto text-white opacity-80">
            {uploadLoadingTeasers[loadingTeaser]}
          </p>
          <div className="mt-4 flex justify-center gap-1">
            {uploadLoadingTeasers.map((_, index) => (
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

  return (
    <div className="min-h-screen">
      {/* Replace Session Modal */}
      <ActionModal
        isOpen={showReplaceModal}
        title="Replace Session"
        message="This will replace your current session and delete existing temporary files. Proceed?"
        primaryLabel="Proceed"
        secondaryLabel="Resume Current"
        onPrimary={handleProceedWithNew}
        onSecondary={handleResumeCurrent}
        onClose={() => setShowReplaceModal(false)}
        primaryColor="#B22222"
      />

      {/* Back Warning Modal */}
      <ActionModal
        isOpen={showBackWarningModal}
        title="End Session"
        message="Leaving this page will end your current session. Do you want to proceed?"
        primaryLabel="Proceed"
        secondaryLabel="Cancel"
        onPrimary={handleBackProceed}
        onSecondary={handleBackCancel}
        onClose={handleBackCancel}
        primaryColor="#B22222"
      />

      <div className="container mx-auto px-4 py-6 max-w-4xl">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={handleBackClick}
            className="px-4 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 flex items-center gap-2 mb-4"
            style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
          >
            <ArrowLeft className="w-5 h-5" />
            Back
          </button>
          <h1 className="text-3xl font-bold text-white">
            Upload Document
          </h1>
        </div>

        {/* Main Container */}
        <div className="glass-card rounded-lg p-6 mb-6">
        {/* Drag and Drop Zone */}
        <div className="mb-6">
          {selectedUploadFile ? (
            <div className="rounded-lg p-6 border-2 border-primary-green" style={{ backgroundColor: 'rgba(52, 116, 51, 0.4)', backdropFilter: 'blur(12px)' }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-accent-amber" />
                  <div>
                    <p className="font-semibold text-white">
                      {selectedUploadFile.name}
                    </p>
                    <p className="text-sm opacity-70 text-white">
                      {(selectedUploadFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleRemoveFile}
                  className="p-2 rounded-lg transition-opacity hover:opacity-90"
                  style={{ backgroundColor: '#B22222', color: 'white' }}
                  title="Remove file"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
          ) : (
            <div
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`glass-input rounded-lg p-12 border-2 border-dashed cursor-pointer transition-all ${
                isDragging ? 'opacity-70' : ''
              }`}
              style={{
                borderColor: isDragging ? 'rgba(169, 187, 169, 0.5)' : 'rgba(255, 255, 255, 0.2)',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileInputChange}
                accept=".pdf,.txt"
              />
              <div className="text-center">
                <Upload className="w-12 h-12 mx-auto mb-4 text-primary-green" />
                <p className="text-lg font-semibold mb-2 text-white">
                  {isDragging ? 'Drop file here' : 'Drag and drop a file here'}
                </p>
                <p className="text-sm opacity-70 text-white">
                  or click to browse
                </p>
                <p className="text-xs mt-2 opacity-50 text-white">
                  Supported formats: PDF, TXT 
                </p>
              </div>
            </div>
          )}
          {/* Error Message */}
          {fileError && (
            <div className="mt-3 px-4 py-3 rounded-lg border-2 border-alert-red" style={{ backgroundColor: '#B22222', color: '#FFFFFF' }}>
              <p className="text-sm font-bold">
                {fileError}
              </p>
            </div>
          )}
        </div>

        {/* Form */}
        <form className="space-y-6">
          {/* Company Name */}
          <div>
            <label htmlFor="companyName" className="block text-sm font-semibold mb-2 text-white">
              Company Name
            </label>
            <input
              type="text"
              id="companyName"
              value={uploadMetadata?.companyName || ''}
              onChange={(e) => handleInputChange('companyName', e.target.value)}
              className="glass-input w-full px-4 py-2 rounded-lg"
              style={{ color: '#FFFFFF' }}
              placeholder="Enter company name"
            />
          </div>

          {/* Document Title */}
          <div>
            <label htmlFor="docTitle" className="block text-sm font-semibold mb-2 text-white">
              Document Title
            </label>
            <input
              type="text"
              id="docTitle"
              value={uploadMetadata?.docTitle || ''}
              onChange={(e) => handleInputChange('docTitle', e.target.value)}
              className="glass-input w-full px-4 py-2 rounded-lg"
              style={{ color: '#FFFFFF' }}
              placeholder="Enter document title"
            />
          </div>

          {/* Document Type */}
          <div>
            <label htmlFor="docType" className="block text-sm font-semibold mb-2 text-white">
              Document Type
            </label>
            <select
              id="docType"
              value={uploadMetadata?.docType || ''}
              onChange={(e) => handleInputChange('docType', e.target.value)}
              className="glass-input w-full px-4 py-2 rounded-lg opacity-50 text-white"
              style={{ color: (!uploadMetadata?.docType || uploadMetadata?.docType === '') ? 'rgba(255, 255, 255, 0.6)' : '#FFFFFF' }}
            >
              <option value="" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Select document type</option>
              <option value="10-K">10-K</option>
              <option value="10-Q">10-Q</option>
              <option value="8-K">8-K</option>
              <option value="Annual Report">Annual Report</option>
              <option value="Quarterly Report">Quarterly Report</option>
              <option value="Other">Other</option>
            </select>
          </div>

          {/* Year */}
          <div>
            <label htmlFor="year" className="block text-sm font-semibold mb-2 text-white">
              Year
            </label>
            <input
              type="number"
              id="year"
              value={uploadMetadata?.year || ''}
              onChange={(e) => handleInputChange('year', e.target.value ? parseInt(e.target.value) : '')}
              className="glass-input w-full px-4 py-2 rounded-lg"
              style={{ color: '#FFFFFF' }}
              placeholder="Enter year (e.g., 2024)"
              min="1900"
              max="2100"
            />
          </div>
        </form>
        </div>

        {/* Action Button */}
        <div className="mt-6 flex justify-center">
          <button
            onClick={handleButtonClick}
            className="px-8 py-3 rounded-lg font-semibold text-lg flex items-center gap-2 border-2 border-accent-amber"
            style={{ backgroundColor: buttonText === 'Resume Analysis' ? '#FFC107' : '#FFC107', color: '#000000' }}
          >
            {buttonText}
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default UploadPage
