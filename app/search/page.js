'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Scale, ChevronDown, ChevronUp, Mail, MapPin, Briefcase, ArrowLeft, Phone } from 'lucide-react'
import Link from 'next/link'
import { usePolling } from '@/hooks/use-polling'
import { fetchLawyers, fetchLawyerConversation, fetchStats, startLawyerSearch, fetchPhoneCallRequests, searchLegal } from '@/lib/api'

// Hardcoded demo lawyer emails (matching backend)
const DEMO_LAWYER_EMAILS = [
  "sohamkundu2704@gmail.com",
  "jaybalu06@gmail.com",
  "arnavmohanty123@gmail.com"
]

const DEMO_EMAILS_SET = new Set(DEMO_LAWYER_EMAILS.map(email => email.toLowerCase()))

export default function SearchPage() {
  const [situation, setSituation] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [expandedLawyer, setExpandedLawyer] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [searchStarted, setSearchStarted] = useState(false)
  const [lawyerThreads, setLawyerThreads] = useState({})
  const [error, setError] = useState(null)
  const [phoneCallRequests, setPhoneCallRequests] = useState([])
  const [foundLawyers, setFoundLawyers] = useState([])

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
      // Call the new search-legal endpoint
      const results = await searchLegal(situation)
      console.log('Search results:', results)
      
      // Extract and map lawyers from the search results
      const extracted = results.flatMap(r => r.extracted_lawyers || [])
      
      // Map backend fields to frontend expectations
      const mapped = extracted.map(l => {
        const rawScore = typeof l.match_score === 'number'
          ? l.match_score
          : Number.parseInt(l.match_score ?? 0, 10) || 0
        return {
          lawyer_name: l.name,
          lawyer_email: l.email,
          firm_name: l.firm_or_affiliation,
          location: l.location, // if available
          email_source: l.email_source,
          side: l.side,
          role: l.role,
          specialty: (l.specialty || '').toString().trim(),
          match_score: Math.max(0, Math.min(100, rawScore)),
          // Preserve other potential fields
          case_title: l.case_title,
          citation: l.citation
        }
      })

      // Remove duplicates by email
      const uniqueLawyers = Array.from(new Map(mapped.map(item => [item.lawyer_email, item])).values())

      // Sort by match_score descending
      const ranked = [...uniqueLawyers].sort((a, b) => (b.match_score || 0) - (a.match_score || 0))

      // Set state
      setFoundLawyers(ranked)
      setSearchStarted(true)
      setShowResults(true)
    } catch (err) {
      console.error('Error starting search:', err)
      setError(err.message || 'Failed to find lawyers. Please try again.')
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
    setFoundLawyers([])
  }

  // Derived ranking data
  const backendLawyersRaw = lawyersData?.lawyers || []
  const backendDemoLawyers = backendLawyersRaw.filter(
    (lawyer) => DEMO_EMAILS_SET.has((lawyer.lawyer_email || '').toLowerCase())
  )
  const backendNonDemoLawyers = backendLawyersRaw.filter(
    (lawyer) => !DEMO_EMAILS_SET.has((lawyer.lawyer_email || '').toLowerCase())
  )
  const filteredFoundLawyers = foundLawyers.filter(
    (lawyer) => !DEMO_EMAILS_SET.has((lawyer.lawyer_email || '').toLowerCase())
  )
  const factEnrichedLawyers = backendNonDemoLawyers.filter((lawyer) => (lawyer.rank_score || 0) > 0)
  const foundLawyerMap = new Map(filteredFoundLawyers.map((lawyer) => [lawyer.lawyer_email, lawyer]))
  const backendFallbackForRanking = backendNonDemoLawyers
    .filter((lawyer) => (lawyer.rank_score || 0) === 0)
    .filter((lawyer) => !foundLawyerMap.has(lawyer.lawyer_email))
    .map((lawyer) => ({
      lawyer_name: lawyer.lawyer_name || '',
      lawyer_email: lawyer.lawyer_email,
      firm_name: lawyer.firm_name,
      specialty: '',
      match_score: 0,
      case_title: '',
      citation: '',
      location: lawyer.location_text || lawyer.location,
      price_text: lawyer.price_text || 'N/A',
      years_experience: lawyer.years_experience,
      fallbackBackend: true
    }))

  const fallbackRankingPool = [
    ...filteredFoundLawyers.map((lawyer) => ({ source: 'gemini', lawyer })),
    ...backendFallbackForRanking.map((lawyer) => ({ source: 'backend-fallback', lawyer }))
  ].sort((a, b) => (b.lawyer.match_score || 0) - (a.lawyer.match_score || 0))

  const displayLawyers = filteredFoundLawyers.length > 0
    ? filteredFoundLawyers
    : backendNonDemoLawyers
  const hasDemoLawyers = backendDemoLawyers.length > 0

  let topRankedEntries = []
  if (factEnrichedLawyers.length > 0) {
    const sortedFact = [...factEnrichedLawyers].sort((a, b) => (b.rank_score || 0) - (a.rank_score || 0))
    const backendTop = sortedFact.slice(0, 3).map((lawyer) => ({ source: 'backend', lawyer }))
    const needed = Math.max(0, 3 - backendTop.length)
    if (needed > 0) {
      const fallbackForTop = fallbackRankingPool
        .filter((entry) => !backendTop.some((backendEntry) => backendEntry.lawyer.lawyer_email === entry.lawyer.lawyer_email))
        .slice(0, needed)
      topRankedEntries = [...backendTop, ...fallbackForTop]
    } else {
      topRankedEntries = backendTop
    }
  } else {
    topRankedEntries = fallbackRankingPool.slice(0, 3)
  }

  const rankingSubtitle = factEnrichedLawyers.length > 0
    ? 'Ranked by live price + experience data extracted from lawyer emails'
    : 'Ranked by Gemini match score until lawyers reply with more details'

  const renderLawyerCard = (lawyer, options = {}) => {
    const { isDemo = false } = options
    const lawyerEmail = lawyer.lawyer_email || lawyer.email || ''
    const fallbackKey = `${lawyer.lawyer_name || 'lawyer'}-${lawyer.firm_name || 'firm'}`
    const cardKey = lawyerEmail || fallbackKey
    const thread = lawyerEmail ? lawyerThreads[lawyerEmail] : null
    const emails = thread?.threads?.[0]?.emails || []
    const matchScoreRaw = typeof lawyer.match_score === 'number'
      ? lawyer.match_score
      : Number.parseInt(lawyer.match_score ?? 0, 10)
    const normalizedMatchScore = Number.isFinite(matchScoreRaw)
      ? Math.max(0, Math.min(100, matchScoreRaw))
      : null
    const mailtoLink = lawyerEmail ? `mailto:${lawyerEmail}` : null
    const priceText = lawyer.price_text
      || (lawyer.flat_fee ? `$${lawyer.flat_fee.toLocaleString()} flat fee`
        : lawyer.hourly_rate ? `$${lawyer.hourly_rate}/hr`
        : lawyer.contingency_rate ? `${lawyer.contingency_rate}% contingency`
        : 'N/A')
    const yearsExperience = lawyer.years_experience ?? lawyer.experience_years
    const experienceLabel = yearsExperience ? `${yearsExperience} years` : 'N/A'
    const locationLabel = lawyer.location_text || lawyer.location || 'N/A'
    const hasPhoneCallRequest = phoneCallRequests.some(
      (req) => req.lawyer_email === lawyer.lawyer_email
    )

    return (
      <Card key={cardKey} className="border-2 border-[#8B9D7F] shadow-md">
        <CardHeader>
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <CardTitle className="text-2xl text-black">
                  {lawyer.lawyer_name || lawyerEmail || 'Lawyer'}
                </CardTitle>
                {isDemo && (
                  <Badge className="bg-blue-500 text-white">Demo Lawyer</Badge>
                )}
                {hasPhoneCallRequest && (
                  <Badge className="bg-yellow-500 text-white flex items-center gap-1">
                    <Phone className="w-3 h-3" />
                    Call Requested
                  </Badge>
                )}
              </div>
              {lawyerEmail && (
                <div className="flex items-center gap-2 text-sm text-gray-600 mb-3">
                  <Mail className="w-4 h-4" />
                  <a
                    href={mailtoLink}
                    className="underline break-all"
                    rel="noreferrer"
                  >
                    {lawyerEmail}
                  </a>
                </div>
              )}
              {lawyer.firm_name && (
                <p className="text-[#8B9D7F] font-semibold text-lg mb-3">
                  {lawyer.firm_name}
                </p>
              )}
              {(lawyer.case_title || lawyer.citation) && (
                <div className="mb-3 text-sm bg-gray-50 p-2 rounded border border-gray-100">
                  {lawyer.case_title && <p className="font-medium text-gray-800 mb-1">Case: {lawyer.case_title}</p>}
                  {lawyer.citation && <p className="text-gray-500 italic">Citation: {lawyer.citation}</p>}
                </div>
              )}
              <div className="flex flex-wrap gap-3 mb-3">
                {lawyer.specialty && (
                  <Badge className="bg-[#8B9D7F] text-white">
                    {lawyer.specialty}
                  </Badge>
                )}
                {(lawyer.rank_score || 0) > 0 && (
                  <Badge variant="outline" className="border-green-200 bg-green-50 text-green-700">
                    Score: {lawyer.rank_score}%
                  </Badge>
                )}
                {normalizedMatchScore !== null && (
                  <Badge variant="outline" className="border-green-200 bg-green-50 text-green-700">
                    Match: {Math.round(normalizedMatchScore)}%
                  </Badge>
                )}
                {lawyer.side && (
                  <Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700">
                    {lawyer.side}
                  </Badge>
                )}
                {lawyer.role && (
                  <Badge variant="outline" className="border-purple-200 bg-purple-50 text-purple-700">
                    {lawyer.role}
                  </Badge>
                )}
                {lawyer.experience_years && (
                  <Badge variant="secondary" className="flex items-center gap-1">
                    <Briefcase className="w-4 h-4" />
                    {lawyer.experience_years} years
                  </Badge>
                )}
                {lawyer.flat_fee && (
                  <Badge className="bg-[#8B9D7F] text-white">
                    ${lawyer.flat_fee.toLocaleString()} flat fee
                  </Badge>
                )}
                {lawyer.hourly_rate && (
                  <Badge className="bg-[#8B9D7F] text-white">
                    ${lawyer.hourly_rate}/hr
                  </Badge>
                )}
                {lawyer.contingency_rate && (
                  <Badge className="bg-[#8B9D7F] text-white">
                    {lawyer.contingency_rate}% contingency
                  </Badge>
                )}
              </div>
              {lawyer.case_types && lawyer.case_types.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {lawyer.case_types.map((type, idx) => (
                    <Badge key={idx} variant="outline">{type}</Badge>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm text-gray-600 mb-3">
                <div>
                  <span className="font-semibold text-black">Price:</span> {priceText || 'N/A'}
                </div>
                <div>
                  <span className="font-semibold text-black">Experience:</span> {experienceLabel}
                </div>
                <div className="flex items-center gap-1">
                  <MapPin className="w-4 h-4" />
                  <span>{locationLabel || 'N/A'}</span>
                </div>
              </div>
              <div className="text-sm text-gray-600">
                <p>Emails exchanged: {lawyer.email_count || 0}</p>
                {lawyer.last_contact_date && (
                  <p>Last contact: {new Date(lawyer.last_contact_date).toLocaleString()}</p>
                )}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {lawyerEmail && (
            <Button
              onClick={() => toggleExpand(lawyerEmail)}
              className="w-full bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white"
            >
              <Mail className="w-4 h-4 mr-2" />
              {expandedLawyer === lawyerEmail ? 'Hide' : 'View'} Email Thread
              {expandedLawyer === lawyerEmail ? (
                <ChevronUp className="w-4 h-4 ml-2" />
              ) : (
                <ChevronDown className="w-4 h-4 ml-2" />
              )}
            </Button>
          )}

          {/* Email Thread - Chat Format */}
          {lawyerEmail && expandedLawyer === lawyerEmail && (
            <div className="mt-6">
              <h3 className="text-xl font-bold text-black mb-4">
                Conversation
              </h3>
              {emails.length === 0 ? (
                <p className="text-gray-600">No messages yet. Waiting for response...</p>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {emails.map((email, index) => {
                    const lawyerEmailLower = lawyerEmail.toLowerCase()
                    const emailToLower = (email.to || '').toLowerCase()
                    const emailFromLower = (email.from || '').toLowerCase()
                    
                    const isFromLawlyAI = 
                      emailToLower === lawyerEmailLower ||
                      emailFromLower.includes('lawlyai') || 
                      emailFromLower.includes('agent') ||
                      emailFromLower.includes('lawyerfinder')
                    
                    const senderName = isFromLawlyAI 
                      ? 'LawlyAI' 
                      : (lawyer.lawyer_name || (email.from || '').split('@')[0] || 'Lawyer')
                    
                    let cleanBody = email.body || ''
                    
                    const replyMarkers = [
                      /\r?\n\s*On\s+[^<]*<[^>]+>\s+wrote:\s*$/i,
                      /\r?\n\s*On\s+.*?wrote:\s*$/i,
                      /\r?\n\s*From:\s+.*$/i,
                      /\r?\n\s*-\s*Original\s+Message.*$/i,
                    ]
                    
                    let replyStartIndex = -1
                    for (const marker of replyMarkers) {
                      const match = cleanBody.match(marker)
                      if (match && match.index !== undefined) {
                        const beforeMarker = cleanBody.substring(0, match.index).trim()
                        if (beforeMarker.length > 0) {
                          replyStartIndex = match.index
                          break
                        }
                      }
                    }
                    
                    if (replyStartIndex > 0) {
                      cleanBody = cleanBody.substring(0, replyStartIndex).trim()
                    }
                    
                    const lines = cleanBody.split(/\r?\n/)
                    const cleanedLines = []
                    let consecutiveQuotedLines = 0
                    
                    for (let i = 0; i < lines.length; i++) {
                      const line = lines[i]
                      const isQuoted = /^\s*>\s*/.test(line)
                      
                      if (isQuoted) {
                        consecutiveQuotedLines++
                        if (consecutiveQuotedLines >= 2) {
                          continue
                        }
                      } else {
                        consecutiveQuotedLines = 0
                        cleanedLines.push(line)
                      }
                    }
                    
                    cleanBody = cleanedLines.join('\n').trim()
                    
                    if (!cleanBody || cleanBody.length < 5) {
                      const original = email.body || ''
                      const onWroteMatch = original.match(/\r?\n\s*On\s+.*?wrote:.*$/s)
                      if (onWroteMatch && onWroteMatch.index > 10) {
                        cleanBody = original.substring(0, onWroteMatch.index).trim()
                      } else {
                        cleanBody = original.trim()
                      }
                    }
                    
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
                            {!isFromLawlyAI && (
                              <p className="text-xs font-semibold mb-1 opacity-80">
                                {senderName}
                              </p>
                            )}
                            
                            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                              {cleanBody}
                            </div>
                            
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
              {topRankedEntries.length > 0 && (
                <div className="bg-gradient-to-r from-[#8B9D7F] to-[#7A8C6E] rounded-lg p-6 mb-8 text-white">
                  <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                    <Scale className="w-6 h-6" />
                    Top Ranked Lawyers
                  </h2>
                  <p className="text-white/90 mb-4">
                    {rankingSubtitle}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {topRankedEntries.map((entry, index) => {
                      const lawyer = entry.lawyer
                      const isBackend = entry.source === 'backend' || entry.source === 'backend-fallback'
                      const email = lawyer.lawyer_email || lawyer.email
                      const priceText = isBackend ? (lawyer.price_text || 'N/A') : 'N/A'
                      const yearsExp = isBackend ? lawyer.years_experience : null
                      const locationLabel = isBackend
                        ? (lawyer.location_text || lawyer.location || 'N/A')
                        : (lawyer.location || 'N/A')
                      let scoreLabel = 'Match: N/A'
                      if (entry.source === 'backend') {
                        scoreLabel = `Score: ${lawyer.rank_score || 0}%`
                      } else if (entry.source === 'backend-fallback') {
                        scoreLabel = 'Score: Pending'
                      } else {
                        scoreLabel = `Match: ${Math.round(lawyer.match_score || 0)}%`
                      }
                      return (
                        <Card key={`${entry.source}-${email || index}`} className="bg-white/95 border-0">
                          <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-lg font-bold text-black">
                              #{index + 1} {lawyer.lawyer_name || (email ? email.split('@')[0] : 'Lawyer')}
                            </CardTitle>
                            <Badge className="bg-[#8B9D7F] text-white">
                              {scoreLabel}
                            </Badge>
                          </div>
                          {email && (
                            <a
                              href={`mailto:${email}`}
                              className="text-sm text-[#8B9D7F] underline break-all"
                            >
                              {email}
                            </a>
                          )}
                          </CardHeader>
                          <CardContent className="space-y-2">
                          {lawyer.specialty && !isBackend && (
                            <div className="font-medium text-[#8B9D7F]">
                              Specialty: {lawyer.specialty}
                            </div>
                          )}
                          {lawyer.firm_name && (
                            <p className="text-sm text-gray-600">{lawyer.firm_name}</p>
                          )}
                          <div className="text-sm text-gray-600">
                            <span className="font-semibold text-black">Price:</span> {priceText}
                          </div>
                          <div className="text-sm text-gray-600">
                            <span className="font-semibold text-black">Experience:</span>{' '}
                            {yearsExp ? `${yearsExp} years` : 'N/A'}
                          </div>
                          <div className="flex items-center gap-1 text-sm text-gray-600">
                            <MapPin className="w-4 h-4" />
                            {locationLabel || 'N/A'}
                          </div>
                          {(lawyer.experience_years && !yearsExp) && (
                            <div className="flex items-center gap-1 text-sm text-gray-600">
                              <Briefcase className="w-4 h-4" />
                              {lawyer.experience_years} years experience
                            </div>
                          )}
                          </CardContent>
                        </Card>
                      )
                    })}
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
            {searchStarted && foundLawyers.length === 0 && (!lawyersData?.lawyers || lawyersData.lawyers.length === 0) && (
              <div className="text-center py-12">
                <p className="text-gray-600 mb-2">Finding the best lawyers for you...</p>
                <p className="text-sm text-gray-500">
                  Scanning case database and matching with legal experts.
                </p>
              </div>
            )}

            {/* Lawyer Cards */}
            <div className="max-w-5xl mx-auto space-y-6">
              {displayLawyers.length > 0
                ? displayLawyers.map((lawyer) => renderLawyerCard(lawyer))
                : (
                  <p className="text-center text-gray-600">
                    Waiting for lawyers to reply...
                  </p>
                )}
            </div>

            {hasDemoLawyers && (
              <div className="max-w-5xl mx-auto space-y-6 mt-12">
                <div>
                  <h2 className="text-3xl font-bold text-black mb-2">
                    Demo Lawyers (Live Email Test)
                  </h2>
                  <p className="text-gray-600">
                    These demo inboxes show the exact email our agent just sent so you can preview the full experience.
                  </p>
                </div>
                {backendDemoLawyers.map((lawyer) => renderLawyerCard(lawyer, { isDemo: true }))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}