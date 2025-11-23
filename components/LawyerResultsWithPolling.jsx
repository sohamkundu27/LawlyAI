'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Mail, MapPin, Briefcase, ChevronDown, ChevronUp } from 'lucide-react'
import { usePolling } from '@/hooks/use-polling'
import { fetchLawyers, fetchLawyerConversation } from '@/lib/api'

/**
 * Component that displays lawyer results with automatic polling for updates
 */
export default function LawyerResultsWithPolling() {
  const [expandedLawyer, setExpandedLawyer] = useState(null)
  const [lawyerThreads, setLawyerThreads] = useState({})

  // Poll for lawyer updates every 5 seconds
  const { data: lawyersData, isLoading, lastUpdate } = usePolling(
    async () => {
      const response = await fetchLawyers()
      return response
    },
    {
      interval: 5000, // Poll every 5 seconds
      maxInterval: 30000, // Max 30 seconds if no updates
      enabled: true, // Always enabled when component is mounted
      onUpdate: (newData, oldData) => {
        console.log('Lawyers updated!', newData)
        // You could show a toast notification here
      }
    }
  )

  // When a lawyer is expanded, poll for their conversation thread
  useEffect(() => {
    if (!expandedLawyer || !lawyersData?.lawyers) return

    const lawyer = lawyersData.lawyers.find(l => l.lawyer_email === expandedLawyer)
    if (!lawyer) return

    // Fetch conversation thread for this lawyer
    const fetchThread = async () => {
      try {
        const threadData = await fetchLawyerConversation(expandedLawyer)
        setLawyerThreads(prev => ({
          ...prev,
          [expandedLawyer]: threadData
        }))
      } catch (error) {
        console.error('Error fetching thread:', error)
      }
    }

    fetchThread()
    
    // Poll for thread updates every 3 seconds while expanded
    const interval = setInterval(fetchThread, 3000)
    return () => clearInterval(interval)
  }, [expandedLawyer, lawyersData])

  const toggleExpand = (lawyerEmail) => {
    setExpandedLawyer(expandedLawyer === lawyerEmail ? null : lawyerEmail)
  }

  if (isLoading && !lawyersData) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Loading lawyers...</p>
      </div>
    )
  }

  if (!lawyersData?.lawyers || lawyersData.lawyers.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">No lawyers found yet. Waiting for responses...</p>
        {lastUpdate && (
          <p className="text-sm text-gray-500 mt-2">
            Last updated: {new Date(lastUpdate).toLocaleTimeString()}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Status indicator */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-gray-600">
          {lastUpdate && (
            <span>Last updated: {new Date(lastUpdate).toLocaleTimeString()}</span>
          )}
        </div>
        <Badge variant="secondary">
          {lawyersData.count} lawyer{lawyersData.count !== 1 ? 's' : ''} found
        </Badge>
      </div>

      {/* Lawyer cards */}
      {lawyersData.lawyers.map((lawyer) => {
        const thread = lawyerThreads[lawyer.lawyer_email]
        const emails = thread?.threads?.[0]?.emails || []
        const mailtoLink = lawyer.lawyer_email ? `mailto:${lawyer.lawyer_email}` : null
        const priceText = lawyer.price_text
          || (lawyer.flat_fee ? `$${lawyer.flat_fee.toLocaleString()} flat fee`
            : lawyer.hourly_rate ? `$${lawyer.hourly_rate}/hr`
            : lawyer.contingency_rate ? `${lawyer.contingency_rate}% contingency`
            : 'N/A')
        const yearsExperience = lawyer.years_experience ?? lawyer.experience_years
        const experienceLabel = yearsExperience ? `${yearsExperience} years` : 'N/A'
        const locationLabel = lawyer.location_text || lawyer.location || 'N/A'

        return (
          <Card key={lawyer.lawyer_email} className="border-2 border-[#8B9D7F] shadow-md">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <CardTitle className="text-2xl text-black mb-2">
                    {lawyer.lawyer_name || lawyer.lawyer_email}
                  </CardTitle>
                  {lawyer.lawyer_email && (
                    <div className="flex items-center gap-2 text-sm text-gray-600 mb-3">
                      <Mail className="w-4 h-4" />
                      <a
                        href={mailtoLink}
                        className="underline break-all"
                        rel="noreferrer"
                      >
                        {lawyer.lawyer_email}
                      </a>
                    </div>
                  )}
                  {lawyer.firm_name && (
                    <p className="text-[#8B9D7F] font-semibold text-lg mb-3">
                      {lawyer.firm_name}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-3 mb-3">
                    {(lawyer.rank_score || 0) > 0 && (
                      <Badge variant="outline" className="border-green-200 bg-green-50 text-green-700">
                        Score: {lawyer.rank_score}%
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
                    <div className="flex flex-wrap gap-2 mb-2">
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

              {/* Email Thread */}
              {expandedLawyer === lawyer.lawyer_email && (
                <div className="mt-6 space-y-4">
                  <h3 className="text-xl font-bold text-black mb-4">
                    Email Conversation
                  </h3>
                  {emails.length === 0 ? (
                    <p className="text-gray-600">Loading conversation...</p>
                  ) : (
                    emails.map((email, index) => (
                      <div
                        key={index}
                        className={`p-4 rounded-lg ${
                          email.from.toLowerCase().includes('lawlyai') || 
                          email.from.toLowerCase().includes('agent')
                            ? 'bg-[#F5F7F3] border-l-4 border-[#8B9D7F]'
                            : 'bg-gray-50 border-l-4 border-gray-400'
                        }`}
                      >
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <p className="font-semibold text-black">
                              From: {email.from}
                            </p>
                            <p className="text-sm text-gray-600">
                              To: {email.to}
                            </p>
                          </div>
                          <p className="text-sm text-gray-500">
                            {new Date(email.timestamp || email.date).toLocaleString()}
                          </p>
                        </div>
                        <p className="font-semibold text-black mb-2">
                          Subject: {email.subject}
                        </p>
                        <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                          {email.body}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

