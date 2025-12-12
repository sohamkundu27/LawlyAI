'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Scale, ChevronDown, ChevronUp, Mail, MapPin, Briefcase, ArrowLeft, Phone } from 'lucide-react'
import Link from 'next/link'
import { usePolling } from '@/hooks/use-polling'
import { fetchLawyers, fetchLawyerConversation, fetchStats, startLawyerSearch, fetchPhoneCallRequests, fetchRankedLawyers } from '@/lib/api'

// Hardcoded lawyer emails (matching backend)
const LAWYER_EMAILS = [
  "sohamkundu2704@gmail.com",
  "womovo6376@bablace.com",
  "arnavmohanty123@gmail.com"
]

export default function SearchPage() {
  const [situation, setSituation] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [expandedLawyer, setExpandedLawyer] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [searchStarted, setSearchStarted] = useState(false)
  const [lawyerThreads, setLawyerThreads] = useState({})
  const [error, setError] = useState(null)
  const [phoneCallRequests, setPhoneCallRequests] = useState([])
  const [rankedLawyers, setRankedLawyers] = useState(null)

  // Memoize fetch functions to prevent unnecessary re-renders
  const fetchLawyersFn = useCallback(async () => {
    try {
      const response = await fetchLawyers()
      return response
    } catch (err) {
      console.error('Error fetching lawyers:', err)
      return { lawyers: [], count: 0 }
    }
  }, [])

  const fetchStatsFn = useCallback(async () => {
    try {
      const response = await fetchStats()
      return response
    } catch (err) {
      console.error('Error fetching stats:', err)
      return {
        lawyers_contacted: 0,
        lawyers_responded: 0,
        quotes_received: 0,
        deals_finalized: 0
      }
    }
  }, [])

  // Poll for lawyer updates every 10 seconds when search is active
  const { data: lawyersData, isLoading: lawyersLoading, lastUpdate: lawyersLastUpdate } = usePolling(
    fetchLawyersFn,
    {
      interval: 10000, // 10 seconds instead of 5
      maxInterval: 60000, // 60 seconds max
      enabled: showResults && searchStarted, // Only poll when results are shown and search started
      onUpdate: (newData) => {
        console.log('Lawyers updated!', newData)
      }
    }
  )

  // Poll for stats updates every 10 seconds
  const { data: statsData, isLoading: statsLoading } = usePolling(
    fetchStatsFn,
    {
      interval: 10000, // 10 seconds instead of 5
      maxInterval: 60000, // 60 seconds max
      enabled: showResults && searchStarted
    }
  )

  // Fetch ranked lawyers
  const fetchRankedLawyersFn = useCallback(async () => {
    try {
      const response = await fetchRankedLawyers()
      return response
    } catch (err) {
      console.error('Error fetching ranked lawyers:', err)
      return { lawyers: [], count: 0 }
    }
  }, [])

  // Poll for ranked lawyers every 10 seconds
  const { data: rankedLawyersData, isLoading: rankedLoading } = usePolling(
    fetchRankedLawyersFn,
    {
      interval: 10000,
      maxInterval: 60000,
      enabled: showResults && searchStarted
    }
  )

  // Update ranked lawyers state
  useEffect(() => {
    if (rankedLawyersData) {
      setRankedLawyers(rankedLawyersData)
    }
  }, [rankedLawyersData])

  // Fetch conversation thread when a lawyer is expanded
  useEffect(() => {
    if (!expandedLawyer || !lawyersData?.lawyers) return

    const lawyer = lawyersData.lawyers.find(l => l.lawyer_email === expandedLawyer)
    if (!lawyer) return

    const fetchThread = async () => {
      try {
        const threadData = await fetchLawyerConversation(expandedLawyer)
        console.log('Fetched thread data for', expandedLawyer, ':', threadData)
        setLawyerThreads(prev => ({
          ...prev,
          [expandedLawyer]: threadData
        }))
      } catch (error) {
        console.error('Error fetching thread:', error)
      }
    }

    fetchThread()
    
    // Poll for thread updates every 10 seconds while expanded (reduced from 3s to reduce spam)
    const interval = setInterval(fetchThread, 10000)
    return () => clearInterval(interval)
  }, [expandedLawyer, lawyersData])

  // Poll for phone call requests
  useEffect(() => {
    if (!showResults || !searchStarted) return

    const fetchPhoneCalls = async () => {
      try {
        const data = await fetchPhoneCallRequests()
        setPhoneCallRequests(data.phone_call_requests || [])
      } catch (error) {
        console.error('Error fetching phone call requests:', error)
      }
    }

    fetchPhoneCalls()
    const interval = setInterval(fetchPhoneCalls, 10000)
    return () => clearInterval(interval)
  }, [showResults, searchStarted])

  const handleSearch = async () => {
    if (!situation.trim()) return

    setIsSearching(true)
    setError(null)

    try {
      // Start the lawyer search
      const result = await startLawyerSearch(situation, LAWYER_EMAILS)
      console.log('Search started:', result)
      
      setSearchStarted(true)
      setShowResults(true)
    } catch (err) {
      console.error('Error starting search:', err)
      setError(err.message || 'Failed to start lawyer search. Please try again.')
    } finally {
      setIsSearching(false)
    }
  }

  const toggleExpand = (lawyerEmail) => {
    setExpandedLawyer(expandedLawyer === lawyerEmail ? null : lawyerEmail)
  }

  const handleNewSearch = () => {
    setShowResults(false)
    setSearchStarted(false)
    setExpandedLawyer(null)
    setLawyerThreads({})
    setSituation('')
    setError(null)
    setPhoneCallRequests([])
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="border-b border-gray-200">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <ArrowLeft className="w-5 h-5 text-gray-600" />
            <Scale className="w-8 h-8 text-[#8B9D7F]" />
            <span className="text-2xl font-bold text-black">LawlyAI</span>
          </Link>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-12">
        {/* Search Section */}
        {!showResults && (
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold text-black mb-4">
                Describe Your Legal Situation
              </h1>
              <p className="text-lg text-gray-600">
                Tell us about your case and we'll find the best lawyers for you.
              </p>
            </div>

            <Card className="border-[#8B9D7F] border-2">
              <CardContent className="pt-6">
                <Textarea
                  placeholder="Example: I was in a car accident last week and suffered injuries. The other driver ran a red light and their insurance company is refusing to cover my medical expenses..."
                  className="min-h-[200px] text-base mb-4 focus:ring-[#8B9D7F] focus:border-[#8B9D7F]"
                  value={situation}
                  onChange={(e) => setSituation(e.target.value)}
                />
                <Button
                  onClick={handleSearch}
                  disabled={!situation.trim() || isSearching}
                  className="w-full bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white text-lg py-6"
                >
                  {isSearching ? 'Finding Lawyers...' : 'Find My Lawyer'}
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="max-w-3xl mx-auto mb-4">
            <Card className="border-red-500 border-2">
              <CardContent className="pt-6">
                <p className="text-red-600">{error}</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Results Section */}
        {showResults && (
          <div>
            <div className="mb-8">
              <Button
                onClick={handleNewSearch}
                variant="outline"
                className="mb-4"
              >
                <ArrowLeft className="w-4 h-4 mr-2" /> New Search
              </Button>
              
              {/* Phone Call Notifications */}
              {phoneCallRequests.length > 0 && (
                <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6 rounded">
                  <div className="flex items-center">
                    <Phone className="w-5 h-5 text-yellow-600 mr-2" />
                    <h3 className="font-bold text-yellow-800">Phone Call Requested!</h3>
                  </div>
                  <p className="text-yellow-700 mt-2">
                    {phoneCallRequests.length} lawyer{phoneCallRequests.length > 1 ? 's have' : ' has'} requested a phone call.
                    Check the conversation threads below.
                  </p>
                </div>
              )}

              {/* Quick Snapshot */}
              <div className="bg-[#F5F7F3] rounded-lg p-6 mb-8">
                <h2 className="text-2xl font-bold text-black mb-4">Quick Snapshot</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-white rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-[#8B9D7F] mb-1">
                      {statsData?.lawyers_contacted || 0}
                    </div>
                    <div className="text-sm text-gray-600">Lawyers Contacted</div>
                  </div>
                  <div className="bg-white rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-[#8B9D7F] mb-1">
                      {statsData?.quotes_received || 0}
                    </div>
                    <div className="text-sm text-gray-600">Quotes Received</div>
                  </div>
                  <div className="bg-white rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-[#8B9D7F] mb-1">
                      {statsData?.active_conversations || 0}
                    </div>
                    <div className="text-sm text-gray-600">Active Conversations</div>
                  </div>
                  <div className="bg-white rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-[#8B9D7F] mb-1">
                      {statsData?.deals_finalized || 0}
                    </div>
                    <div className="text-sm text-gray-600">Deals Finalized</div>
                  </div>
                </div>
                {lawyersLastUpdate && (
                  <p className="text-sm text-gray-500 mt-4 text-center">
                    Last updated: {new Date(lawyersLastUpdate).toLocaleTimeString()}
                  </p>
                )}
              </div>

              {/* Ranked Lawyers Section */}
              {rankedLawyers && rankedLawyers.lawyers && rankedLawyers.lawyers.length > 0 && (
                <div className="bg-gradient-to-r from-[#8B9D7F] to-[#7A8C6E] rounded-lg p-6 mb-8 text-white">
                  <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                    <Scale className="w-6 h-6" />
                    Top Ranked Lawyers
                  </h2>
                  <p className="text-white/90 mb-4">
                    Ranked by quote, experience, and location match
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {rankedLawyers.lawyers.slice(0, 3).map((lawyer, index) => (
                      <Card key={lawyer.lawyer_email} className="bg-white/95 border-0">
                        <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-lg font-bold text-black">
                              #{index + 1} {lawyer.lawyer_name || lawyer.lawyer_email.split('@')[0]}
                            </CardTitle>
                            {lawyer.ranking && (
                              <Badge className="bg-[#8B9D7F] text-white">
                                Score: {(lawyer.ranking.total_score * 100).toFixed(0)}%
                              </Badge>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          {lawyer.firm_name && (
                            <p className="text-sm text-gray-600">{lawyer.firm_name}</p>
                          )}
                          {lawyer.location && (
                            <div className="flex items-center gap-1 text-sm text-gray-600">
                              <MapPin className="w-4 h-4" />
                              {lawyer.location}
                            </div>
                          )}
                          {lawyer.experience_years && (
                            <div className="flex items-center gap-1 text-sm text-gray-600">
                              <Briefcase className="w-4 h-4" />
                              {lawyer.experience_years} years experience
                            </div>
                          )}
                          <div className="pt-2 border-t border-gray-200 space-y-1">
                            {lawyer.flat_fee && (
                              <p className="text-sm font-semibold text-[#8B9D7F]">
                                Flat Fee: ${lawyer.flat_fee.toLocaleString()}
                              </p>
                            )}
                            {lawyer.hourly_rate && (
                              <p className="text-sm text-gray-600">
                                Hourly: ${lawyer.hourly_rate}/hr
                              </p>
                            )}
                            {lawyer.estimated_total && (
                              <p className="text-sm text-gray-600">
                                Est. Total: ${lawyer.estimated_total.toLocaleString()}
                              </p>
                            )}
                            {lawyer.retainer_amount && (
                              <p className="text-sm text-gray-600">
                                Retainer: ${lawyer.retainer_amount.toLocaleString()}
                              </p>
                            )}
                            {lawyer.contingency_rate && (
                              <p className="text-sm text-gray-600">
                                Contingency: {lawyer.contingency_rate}%
                              </p>
                            )}
                          </div>
                          {lawyer.ranking && (
                            <div className="pt-2 border-t border-gray-200 space-y-1">
                              <div className="flex justify-between text-xs">
                                <span className="text-gray-600">Price:</span>
                                <span className="font-semibold">{(lawyer.ranking.price_score * 100).toFixed(0)}%</span>
                              </div>
                              <div className="flex justify-between text-xs">
                                <span className="text-gray-600">Experience:</span>
                                <span className="font-semibold">{(lawyer.ranking.experience_score * 100).toFixed(0)}%</span>
                              </div>
                              <div className="flex justify-between text-xs">
                                <span className="text-gray-600">Location:</span>
                                <span className="font-semibold">{(lawyer.ranking.location_score * 100).toFixed(0)}%</span>
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
              
              <h1 className="text-4xl font-bold text-black mb-2">
                Best Lawyers for Your Case
              </h1>
              <p className="text-lg text-gray-600">
                We've contacted these lawyers on your behalf. Here are their responses.
              </p>
            </div>

            {/* Loading State - Only show on first load */}
            {lawyersLoading && !lawyersData && (
              <div className="text-center py-12">
                <p className="text-gray-600">Loading lawyers...</p>
              </div>
            )}

            {/* No Lawyers Yet - Show when search started but no lawyers yet */}
            {searchStarted && (!lawyersData?.lawyers || lawyersData.lawyers.length === 0) && (
              <div className="text-center py-12">
                <p className="text-gray-600 mb-2">Waiting for lawyer responses...</p>
                <p className="text-sm text-gray-500">
                  Emails have been sent to {LAWYER_EMAILS.length} lawyers. They should appear here once they respond.
                </p>
                {lawyersLastUpdate && (
                  <p className="text-xs text-gray-400 mt-2">
                    Last checked: {new Date(lawyersLastUpdate).toLocaleTimeString()}
                  </p>
                )}
              </div>
            )}

            {/* Lawyer Cards */}
            <div className="max-w-5xl mx-auto space-y-6">
              {lawyersData?.lawyers?.map((lawyer) => {
                const thread = lawyerThreads[lawyer.lawyer_email]
                const emails = thread?.threads?.[0]?.emails || []
                
                // Debug logging
                if (expandedLawyer === lawyer.lawyer_email) {
                  console.log('Thread for', lawyer.lawyer_email, ':', thread)
                  console.log('Emails:', emails)
                }

                return (
                  <Card key={lawyer.lawyer_email} className="border-2 border-[#8B9D7F] shadow-md">
                    <CardHeader>
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <CardTitle className="text-2xl text-black">
                              {lawyer.lawyer_name || lawyer.lawyer_email}
                            </CardTitle>
                            {phoneCallRequests.some(req => req.lawyer_email === lawyer.lawyer_email) && (
                              <Badge className="bg-yellow-500 text-white flex items-center gap-1">
                                <Phone className="w-3 h-3" />
                                Call Requested
                              </Badge>
                            )}
                          </div>
                          {lawyer.firm_name && (
                            <p className="text-[#8B9D7F] font-semibold text-lg mb-3">
                              {lawyer.firm_name}
                            </p>
                          )}
                          <div className="flex flex-wrap gap-3 mb-3">
                            {lawyer.location && (
                              <Badge variant="secondary" className="flex items-center gap-1">
                                <MapPin className="w-4 h-4" />
                                {lawyer.location}
                              </Badge>
                            )}
                            {lawyer.experience_years && (
                              <Badge variant="secondary" className="flex items-center gap-1">
                                <Briefcase className="w-4 h-4" />
                                {lawyer.experience_years} years experience
                              </Badge>
                            )}
                            <Badge variant="secondary" className="flex items-center gap-1">
                              <Mail className="w-4 h-4" />
                              {lawyer.lawyer_email}
                            </Badge>
                          </div>
                          
                          {/* Pricing Information */}
                          {(lawyer.flat_fee || lawyer.hourly_rate || lawyer.estimated_total || lawyer.retainer_amount || lawyer.contingency_rate) && (
                            <div className="mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <p className="text-sm font-semibold text-gray-700 mb-2">Pricing:</p>
                              <div className="flex flex-wrap gap-2">
                                {lawyer.flat_fee && (
                                  <Badge className="bg-[#8B9D7F] text-white">
                                    Flat Fee: ${lawyer.flat_fee.toLocaleString()}
                                  </Badge>
                                )}
                                {lawyer.hourly_rate && (
                                  <Badge className="bg-[#8B9D7F] text-white">
                                    ${lawyer.hourly_rate}/hr
                                  </Badge>
                                )}
                                {lawyer.estimated_total && (
                                  <Badge className="bg-[#8B9D7F] text-white">
                                    Est. Total: ${lawyer.estimated_total.toLocaleString()}
                                  </Badge>
                                )}
                                {lawyer.retainer_amount && (
                                  <Badge className="bg-[#8B9D7F] text-white">
                                    Retainer: ${lawyer.retainer_amount.toLocaleString()}
                                  </Badge>
                                )}
                                {lawyer.contingency_rate && (
                                  <Badge className="bg-[#8B9D7F] text-white">
                                    {lawyer.contingency_rate}% contingency
                                  </Badge>
                                )}
                              </div>
                            </div>
                          )}
                          {lawyer.case_types && lawyer.case_types.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-3">
                              {lawyer.case_types.map((type, idx) => (
                                <Badge key={idx} variant="outline">{type}</Badge>
                              ))}
                            </div>
                          )}
                          <div className="text-sm text-gray-600 space-y-1">
                            <p>Emails exchanged: {lawyer.email_count || 0}</p>
                            {lawyer.last_contact_date && (
                              <p>Last contact: {new Date(lawyer.last_contact_date).toLocaleString()}</p>
                            )}
                            {!lawyer.location && !lawyer.experience_years && !lawyer.flat_fee && !lawyer.hourly_rate && !lawyer.estimated_total && (
                              <p className="text-xs text-gray-400 italic">Waiting for lawyer to provide details...</p>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <Button
                        onClick={() => toggleExpand(lawyer.lawyer_email)}
                        className="w-full bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white"
                      >
                        <Mail className="w-4 h-4 mr-2" />
                        {expandedLawyer === lawyer.lawyer_email ? 'Hide' : 'View'} Email Thread
                        {expandedLawyer === lawyer.lawyer_email ? (
                          <ChevronUp className="w-4 h-4 ml-2" />
                        ) : (
                          <ChevronDown className="w-4 h-4 ml-2" />
                        )}
                      </Button>

                      {/* Email Thread - Chat Format */}
                      {expandedLawyer === lawyer.lawyer_email && (
                        <div className="mt-6">
                          <h3 className="text-xl font-bold text-black mb-4">
                            Conversation
                          </h3>
                          {emails.length === 0 ? (
                            <p className="text-gray-600">No messages yet. Waiting for response...</p>
                          ) : (
                            <div className="space-y-3 max-h-96 overflow-y-auto">
                              {emails.map((email, index) => {
                                // Determine if message is from LawlyAI (us) or lawyer (them)
                                // If email.to matches the lawyer's email, we sent it to them (so it's from us)
                                // If email.from matches the lawyer's email, they sent it to us
                                const lawyerEmailLower = lawyer.lawyer_email.toLowerCase()
                                const emailToLower = (email.to || '').toLowerCase()
                                const emailFromLower = (email.from || '').toLowerCase()
                                
                                const isFromLawlyAI = 
                                  emailToLower === lawyerEmailLower || // We sent it to the lawyer
                                  emailFromLower.includes('lawlyai') || 
                                  emailFromLower.includes('agent') ||
                                  emailFromLower.includes('lawyerfinder')
                                
                                // Extract sender name
                                const senderName = isFromLawlyAI 
                                  ? 'LawlyAI' 
                                  : (lawyer.lawyer_name || email.from.split('@')[0] || 'Lawyer')
                                
                                // Clean up email body - remove quoted replies
                                let cleanBody = email.body || ''
                                
                                // Find where quoted reply section starts
                                // Look for common email reply markers
                                const replyMarkers = [
                                  /\r?\n\s*On\s+[^<]*<[^>]+>\s+wrote:\s*$/i,  // "On [date] <email> wrote:"
                                  /\r?\n\s*On\s+.*?wrote:\s*$/i,              // "On [date] wrote:"
                                  /\r?\n\s*From:\s+.*$/i,                     // "From:"
                                  /\r?\n\s*-\s*Original\s+Message.*$/i,       // "- Original Message"
                                ]
                                
                                // Find the first reply marker
                                let replyStartIndex = -1
                                for (const marker of replyMarkers) {
                                  const match = cleanBody.match(marker)
                                  if (match && match.index !== undefined) {
                                    // Make sure there's content before the marker
                                    const beforeMarker = cleanBody.substring(0, match.index).trim()
                                    if (beforeMarker.length > 0) {
                                      replyStartIndex = match.index
                                      break
                                    }
                                  }
                                }
                                
                                // Cut off everything from the reply marker onwards
                                if (replyStartIndex > 0) {
                                  cleanBody = cleanBody.substring(0, replyStartIndex).trim()
                                }
                                
                                // Also remove any standalone quoted lines (starting with >)
                                // but be careful - only remove if they're clearly part of a quoted block
                                const lines = cleanBody.split(/\r?\n/)
                                const cleanedLines = []
                                let consecutiveQuotedLines = 0
                                
                                for (let i = 0; i < lines.length; i++) {
                                  const line = lines[i]
                                  const isQuoted = /^\s*>\s*/.test(line)
                                  
                                  if (isQuoted) {
                                    consecutiveQuotedLines++
                                    // If we have 2+ consecutive quoted lines, skip them all
                                    if (consecutiveQuotedLines >= 2) {
                                      continue
                                    }
                                  } else {
                                    consecutiveQuotedLines = 0
                                    cleanedLines.push(line)
                                  }
                                }
                                
                                cleanBody = cleanedLines.join('\n').trim()
                                
                                // Final fallback: if cleaning removed too much, use original
                                // But still try to remove obvious quoted sections
                                if (!cleanBody || cleanBody.length < 5) {
                                  // Use original but remove the most obvious quoted section
                                  const original = email.body || ''
                                  const onWroteMatch = original.match(/\r?\n\s*On\s+.*?wrote:.*$/s)
                                  if (onWroteMatch && onWroteMatch.index > 10) {
                                    cleanBody = original.substring(0, onWroteMatch.index).trim()
                                  } else {
                                    cleanBody = original.trim()
                                  }
                                }
                                
                                // Format timestamp
                                const timestamp = new Date(email.timestamp || email.date)
                                const timeStr = timestamp.toLocaleTimeString('en-US', { 
                                  hour: 'numeric', 
                                  minute: '2-digit',
                                  hour12: true 
                                })
                                const dateStr = timestamp.toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric'
                                })
                                const isToday = timestamp.toDateString() === new Date().toDateString()
                                
                                return (
                                  <div
                                    key={index}
                                    className={`flex ${isFromLawlyAI ? 'justify-end' : 'justify-start'}`}
                                  >
                                    <div className={`max-w-[75%] ${isFromLawlyAI ? 'order-2' : 'order-1'}`}>
                                      <div className={`rounded-2xl px-4 py-2 ${
                                        isFromLawlyAI
                                          ? 'bg-[#8B9D7F] text-white rounded-br-sm'
                                          : 'bg-gray-200 text-gray-900 rounded-bl-sm'
                                      }`}>
                                        {/* Sender name for lawyer messages */}
                                        {!isFromLawlyAI && (
                                          <p className="text-xs font-semibold mb-1 opacity-80">
                                            {senderName}
                                          </p>
                                        )}
                                        
                                        {/* Message content */}
                                        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                                          {cleanBody}
                                        </div>
                                        
                                        {/* Timestamp */}
                                        <p className={`text-xs mt-1 ${
                                          isFromLawlyAI ? 'text-white/70' : 'text-gray-600'
                                        }`}>
                                          {isToday ? timeStr : `${dateStr} ${timeStr}`}
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          )}

                          {/* Phone Call Alert */}
                          {thread?.threads?.[0] && thread.threads[0].phone_call_requested && (
                            <div className="mt-6 border-t pt-4">
                              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded">
                                <div className="flex items-center">
                                  <Phone className="w-5 h-5 text-yellow-600 mr-2" />
                                  <div>
                                    <p className="font-semibold text-yellow-800">Phone Call Requested</p>
                                    <p className="text-sm text-yellow-700">The lawyer has requested a phone call to discuss further.</p>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}