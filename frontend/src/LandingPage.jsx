import { useState, useEffect, useMemo } from 'react'
import { Search, Bot, Newspaper, Clock, FileText, Upload, Calendar, Trash2, Loader2, Filter, ArrowUpDown } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

function LandingPage() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showOlder, setShowOlder] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [sessionToDelete, setSessionToDelete] = useState(null)
  
  // Filter and sort state
  const [sortOrder, setSortOrder] = useState('newest') // 'newest' or 'oldest'
  const [filterCompany, setFilterCompany] = useState('')
  const [filterType, setFilterType] = useState('all') // 'all', 'sec', 'upload'
  
  const navigate = useNavigate()
  
  // Filter and sort the history
  const filteredAndSortedHistory = useMemo(() => {
    let filtered = [...history]
    
    // Filter by company
    if (filterCompany) {
      filtered = filtered.filter(item => 
        item.company_name?.toLowerCase().includes(filterCompany.toLowerCase())
      )
    }
    
    // Filter by type
    if (filterType !== 'all') {
      filtered = filtered.filter(item => item.type === filterType)
    }
    
    // Sort by date
    filtered.sort((a, b) => {
      const dateA = a.timestamp ? new Date(a.timestamp).getTime() : 0
      const dateB = b.timestamp ? new Date(b.timestamp).getTime() : 0
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB
    })
    
    return filtered
  }, [history, filterCompany, filterType, sortOrder])
  
  // Show only last 5 chats by default, or all if showOlder is true
  const displayedHistory = showOlder ? filteredAndSortedHistory : filteredAndSortedHistory.slice(0, 5)
  const hasMoreChats = filteredAndSortedHistory.length > 5

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch('/api/history/recent')
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        const data = await response.json()
        setHistory(data)
      } catch (err) {
        console.error('Failed to fetch history:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchHistory()
  }, [])

  const handleDeleteClick = (sessionId, e) => {
    e.stopPropagation() // Prevent navigation when clicking delete
    setSessionToDelete(sessionId)
    setShowDeleteDialog(true)
  }

  const handleDeleteCancel = () => {
    setShowDeleteDialog(false)
    setSessionToDelete(null)
  }

  const handleDeleteConfirm = async () => {
    if (!sessionToDelete) return

    try {
      setDeletingId(sessionToDelete)
      const response = await fetch(`/api/history/chat/${sessionToDelete}`, {
        method: 'DELETE'
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete chat' }))
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
      }
      
      // Remove the deleted item from the history
      setHistory(prevHistory => prevHistory.filter(item => item.session_id !== sessionToDelete))
      setShowDeleteDialog(false)
      setSessionToDelete(null)
    } catch (err) {
      console.error('Failed to delete chat:', err)
      alert(`Failed to delete chat: ${err.message}`)
    } finally {
      setDeletingId(null)
    }
  }
  const features = [
    {
      icon: Search,
      title: 'SEC & File Upload',
      description: 'Primary data sourcing from SEC EDGAR API or local PDF/TXT documents.'
    },
    {
      icon: Bot,
      title: 'RAG Chatbot',
      description: 'Interactive chat using Gemini-powered Retrieval Augmented Generation.'
    },
    {
      icon: Newspaper,
      title: 'Market Context',
      description: 'Real-time financial news integration for broader market sentiment.'
    },
    {
      icon: Clock,
      title: 'Persistent History',
      description: 'Secure storage of past analyses for quick reference.'
    }
  ]

  return (
    <div className="min-h-screen">
      {/* Delete Confirmation Dialog */}
      {showDeleteDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-2xl font-semibold mb-4 text-brand-charcoal">
              Delete Chat History
            </h2>
            <p className="mb-6 text-brand-charcoal opacity-80">
              Are you sure you want to delete this chat history? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleDeleteCancel}
                disabled={deletingId !== null}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ backgroundColor: '#dad5c6', color: '#3a3a3a' }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={deletingId !== null}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                style={{ backgroundColor: '#dc2626', color: 'white' }}
              >
                {deletingId ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  'Delete'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="glass-card rounded-lg p-12 text-center">
          <h1 className="text-6xl font-extrabold text-brand-forest mb-4">
            FinScope
          </h1>
          <p className="text-2xl text-brand-charcoal opacity-80">
            Unified Investor Intelligence Platform
          </p>
        </div>
      </div>

      {/* 4-Feature Grid */}
      <div className="container mx-auto px-4 pb-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => {
            const IconComponent = feature.icon
            return (
              <div
                key={index}
                className="glass-card rounded-lg p-6 transition-all duration-300 hover:-translate-y-1"
              >
                <div className="flex items-center gap-3 mb-3">
                  <IconComponent className="w-10 h-10 text-brand-forest" />
                  <h3 className="text-lg font-semibold text-brand-charcoal">
                    {feature.title}
                  </h3>
                </div>
                <p className="text-sm text-brand-charcoal opacity-80">
                  {feature.description}
                </p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Workflow Selection Buttons */}
      <div className="container mx-auto px-4 pb-12">
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <Link
            to="/company"
            className="bg-brand-forest text-white px-8 py-4 rounded-lg font-semibold text-lg hover:opacity-90 transition-opacity w-full sm:w-auto text-center shadow-md hover:shadow-lg"
          >
            Analyse Companies (SEC)
          </Link>
          <Link
            to="/upload"
            className="bg-brand-forest text-white px-8 py-4 rounded-lg font-semibold text-lg hover:opacity-90 transition-opacity w-full sm:w-auto text-center shadow-md hover:shadow-lg"
          >
            Analyse Uploads (Local)
          </Link>
        </div>
      </div>

      {/* Recent Activity Section */}
      <div className="container mx-auto px-4 pb-16">
        <div className="glass-card rounded-lg p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-brand-charcoal">
              Recent Activity
            </h2>
          </div>
          
          {/* Filter and Sort Controls */}
          {!loading && !error && history.length > 0 && (
            <div className="mb-6 p-4 bg-primary-green/10 rounded-lg border border-primary-green/30">
              <div className="flex flex-col md:flex-row gap-4">
                {/* Company Filter */}
                <div className="flex-1">
                  <label className="block text-sm font-medium text-brand-charcoal mb-2">
                    <Search className="w-4 h-4 inline mr-1" />
                    Filter by Company
                  </label>
                  <input
                    type="text"
                    value={filterCompany}
                    onChange={(e) => setFilterCompany(e.target.value)}
                    placeholder="Search company name..."
                    className="w-full px-4 py-2 border border-brand-beige rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-forest text-brand-charcoal"
                  />
                </div>
                
                {/* Type Filter */}
                <div className="flex-1">
                  <label className="block text-sm font-medium text-brand-charcoal mb-2">
                    <Filter className="w-4 h-4 inline mr-1" />
                    Filter by Type
                  </label>
                  <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="w-full px-4 py-2 border border-brand-beige rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-forest text-brand-charcoal bg-white"
                  >
                    <option value="all">All Types</option>
                    <option value="sec">SEC</option>
                    <option value="upload">Upload</option>
                  </select>
                </div>
                
                {/* Sort Order */}
                <div className="flex-1">
                  <label className="block text-sm font-medium text-brand-charcoal mb-2">
                    <ArrowUpDown className="w-4 h-4 inline mr-1" />
                    Sort by Date
                  </label>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value)}
                    className="w-full px-4 py-2 border border-brand-beige rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-forest text-brand-charcoal bg-white"
                  >
                    <option value="newest">Newest First</option>
                    <option value="oldest">Oldest First</option>
                  </select>
                </div>
              </div>
              
              {/* Active Filters Summary */}
              {(filterCompany || filterType !== 'all') && (
                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-brand-charcoal opacity-70">Active filters:</span>
                  {filterCompany && (
                    <span className="px-2 py-1 bg-brand-sage text-brand-charcoal text-xs font-medium rounded">
                      Company: {filterCompany}
                    </span>
                  )}
                  {filterType !== 'all' && (
                    <span className="px-2 py-1 bg-brand-sage text-brand-charcoal text-xs font-medium rounded uppercase">
                      {filterType}
                    </span>
                  )}
                  <button
                    onClick={() => {
                      setFilterCompany('')
                      setFilterType('all')
                    }}
                    className="px-2 py-1 text-xs text-brand-forest hover:underline"
                  >
                    Clear all
                  </button>
                </div>
              )}
              
              {/* Results count */}
              <div className="mt-3 text-sm text-brand-charcoal opacity-70">
                Showing {displayedHistory.length} of {filteredAndSortedHistory.length} conversation{filteredAndSortedHistory.length !== 1 ? 's' : ''}
              </div>
            </div>
          )}
          
          {loading && (
            <div className="text-center py-8">
              <p className="text-brand-charcoal opacity-70">Loading past analyses...</p>
            </div>
          )}

          {error && (
            <div className="rounded-lg p-4 mb-4 border-2 border-alert-red" style={{ backgroundColor: '#B22222', color: '#FFFFFF' }}>
              <p className="font-bold">Error loading history: {error}</p>
            </div>
          )}

          {!loading && !error && history.length === 0 && (
            <div className="text-center py-8">
              <p className="text-brand-charcoal opacity-70">
                No past analyses found. Start by analyzing a company or uploading a document.
              </p>
            </div>
          )}

          {!loading && !error && history.length > 0 && filteredAndSortedHistory.length === 0 && (
            <div className="text-center py-8">
              <p className="text-brand-charcoal opacity-70">
                No conversations match your filters. Try adjusting your search criteria.
              </p>
            </div>
          )}

          {!loading && !error && history.length > 0 && filteredAndSortedHistory.length > 0 && (
            <div className="space-y-4">
              {displayedHistory.map((item) => {
                const date = item.timestamp 
                  ? new Date(item.timestamp).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : 'Unknown date'
                
                const messageCount = item.chats ? item.chats.length : 0
                const TypeIcon = item.type === 'sec' ? FileText : Upload

                return (
                  <div
                    key={item.session_id}
                    onClick={() => navigate(`/history/chat/${item.session_id}`)}
                    className="rounded-lg p-4 cursor-pointer relative hover:scale-[1.02] transition-transform border-2 border-primary-green"
                    style={{ backgroundColor: 'rgba(218, 200, 160, 0.3)', backdropFilter: 'blur(12px)' }}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2 flex-wrap">
                          <TypeIcon className="w-5 h-5 text-accent-amber" />
                          <h3 className="text-lg font-semibold text-white">
                            {item.company_name}
                          </h3>
                          {item.ticker && (
                            <span className="px-3 py-1 bg-accent-amber/90 text-white text-sm font-semibold rounded-md shadow-md">
                              {item.ticker}
                            </span>
                          )}
                          <span className="px-3 py-1 bg-accent-orange/90 text-white text-xs font-semibold rounded-md uppercase shadow-md">
                            {item.type}
                          </span>
                        </div>
                        
                        <div className="flex items-center gap-4 text-sm text-white/80 mb-2">
                          <div className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            <span>{date}</span>
                          </div>
                          {messageCount > 0 && (
                            <span>{messageCount} message{messageCount !== 1 ? 's' : ''}</span>
                          )}
                        </div>

                        {item.metadata && (
                          <div className="text-xs text-white/70">
                            {item.metadata.doc_type && (
                              <span>Document: {item.metadata.doc_type}</span>
                            )}
                            {item.metadata.filing_date && (
                              <span className="ml-3">Filed: {item.metadata.filing_date}</span>
                            )}
                            {item.metadata.year && (
                              <span className="ml-3">Year: {item.metadata.year}</span>
                            )}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={(e) => handleDeleteClick(item.session_id, e)}
                        disabled={deletingId === item.session_id}
                        className="p-2 text-alert-red hover:text-red-400 hover:bg-red-900/30 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Delete this chat history"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                )
              })}
              
              {/* View Older / Show Less Button */}
              {hasMoreChats && (
                <div className="flex justify-center pt-4">
                  <button
                    onClick={() => setShowOlder(!showOlder)}
                    className="px-6 py-2 bg-accent-amber/90 text-white rounded-lg font-semibold hover:bg-accent-amber transition-colors text-sm shadow-md"
                  >
                    {showOlder ? 'Show Less' : 'View Older'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default LandingPage

