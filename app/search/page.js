'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Scale, ChevronDown, ChevronUp, Mail, Star, MapPin, Briefcase, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

// Mock lawyer data with email threads
const mockLawyers = [
  {
    id: 1,
    name: 'Sarah Martinez',
    specialty: 'Personal Injury Law',
    email: 'smartinez@martinezlaw.com',
    fee: '$350/hour',
    experience: '15 years',
    location: 'New York, NY',
    bio: 'Specializes in personal injury cases with a focus on automotive accidents and workplace injuries.',
    emailThread: [
      {
        from: 'LawlyAI Agent',
        to: 'Sarah Martinez',
        date: '2025-06-10 09:30 AM',
        subject: 'New Client Inquiry - Personal Injury Case',
        body: 'Hello Ms. Martinez, I am reaching out on behalf of a client who has been involved in an automotive accident. They are seeking legal representation for their personal injury claim. Would you be available for a consultation?'
      },
      {
        from: 'Sarah Martinez',
        to: 'LawlyAI Agent',
        date: '2025-06-10 11:45 AM',
        subject: 'Re: New Client Inquiry - Personal Injury Case',
        body: 'Thank you for reaching out. Yes, I would be happy to take on this case. I have extensive experience with automotive accident claims and have successfully represented over 200 clients. I can offer a free initial consultation this week. Please provide more details about the incident.'
      },
      {
        from: 'LawlyAI Agent',
        to: 'Sarah Martinez',
        date: '2025-06-10 02:15 PM',
        subject: 'Re: New Client Inquiry - Personal Injury Case',
        body: 'Excellent! The client was rear-ended at a traffic light, resulting in back injuries. They have medical documentation and police reports. What would be your availability for a consultation?'
      },
      {
        from: 'Sarah Martinez',
        to: 'LawlyAI Agent',
        date: '2025-06-10 03:30 PM',
        subject: 'Re: New Client Inquiry - Personal Injury Case',
        body: 'I can meet this Thursday at 2 PM or Friday at 10 AM. My consultation fee is waived for the first meeting. I will need to review all medical records and the police report. This sounds like a strong case.'
      }
    ]
  },
  {
    id: 2,
    name: 'Michael Chen',
    specialty: 'Family Law',
    rating: 4.8,
    experience: '12 years',
    location: 'Los Angeles, CA',
    availability: 'Available',
    bio: 'Expert in divorce proceedings, child custody, and family mediation with a compassionate approach.',
    emailThread: [
      {
        from: 'LawlyAI Agent',
        to: 'Michael Chen',
        date: '2025-06-10 10:00 AM',
        subject: 'Client Seeking Family Law Representation',
        body: 'Dear Mr. Chen, I am contacting you regarding a client who needs assistance with a family law matter. They are looking for experienced representation. Are you currently accepting new clients?'
      },
      {
        from: 'Michael Chen',
        to: 'LawlyAI Agent',
        date: '2025-06-10 01:20 PM',
        subject: 'Re: Client Seeking Family Law Representation',
        body: 'Hello, yes I am accepting new clients. I specialize in family law matters including divorce, custody arrangements, and mediation. Could you provide more details about the specific situation? I offer a confidential consultation to discuss options.'
      }
    ]
  },
  {
    id: 3,
    name: 'Jennifer Wallace',
    specialty: 'Criminal Defense',
    rating: 4.9,
    experience: '18 years',
    location: 'Chicago, IL',
    availability: 'Limited',
    bio: 'Former prosecutor with deep understanding of criminal law. Aggressive defense for serious charges.',
    emailThread: [
      {
        from: 'LawlyAI Agent',
        to: 'Jennifer Wallace',
        date: '2025-06-10 09:15 AM',
        subject: 'Urgent - Criminal Defense Inquiry',
        body: 'Ms. Wallace, I am reaching out on behalf of someone who needs criminal defense representation. This is a time-sensitive matter. Are you available to discuss taking on a new case?'
      },
      {
        from: 'Jennifer Wallace',
        to: 'LawlyAI Agent',
        date: '2025-06-10 04:45 PM',
        subject: 'Re: Urgent - Criminal Defense Inquiry',
        body: 'I received your message. I have limited availability but can make room for urgent cases. What are the charges? I will need details about the situation, timeline, and any evidence. My schedule is tight but I can arrange a call tomorrow morning if needed.'
      }
    ]
  }
]

export default function SearchPage() {
  const [situation, setSituation] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [expandedLawyer, setExpandedLawyer] = useState(null)
  const [isSearching, setIsSearching] = useState(false)

  const handleSearch = () => {
    if (situation.trim()) {
      setIsSearching(true)
      // Simulate search delay
      setTimeout(() => {
        setIsSearching(false)
        setShowResults(true)
      }, 1500)
    }
  }

  const toggleExpand = (lawyerId) => {
    setExpandedLawyer(expandedLawyer === lawyerId ? null : lawyerId)
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

        {/* Results Section */}
        {showResults && (
          <div>
            <div className="mb-8">
              <Button
                onClick={() => setShowResults(false)}
                variant="outline"
                className="mb-4"
              >
                <ArrowLeft className="w-4 h-4 mr-2" /> New Search
              </Button>
              <h1 className="text-4xl font-bold text-black mb-2">
                Best Lawyers for Your Case
              </h1>
              <p className="text-lg text-gray-600">
                We've contacted these lawyers on your behalf. Here are their responses.
              </p>
            </div>

            <div className="max-w-5xl mx-auto space-y-6">
              {mockLawyers.map((lawyer) => (
                <Card key={lawyer.id} className="border-2 border-[#8B9D7F] shadow-md">
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <CardTitle className="text-2xl text-black mb-2">
                          {lawyer.name}
                        </CardTitle>
                        <p className="text-[#8B9D7F] font-semibold text-lg mb-3">
                          {lawyer.specialty}
                        </p>
                        <div className="flex flex-wrap gap-3 mb-3">
                          <Badge variant="secondary" className="flex items-center gap-1">
                            <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                            {lawyer.rating}
                          </Badge>
                          <Badge variant="secondary" className="flex items-center gap-1">
                            <Briefcase className="w-4 h-4" />
                            {lawyer.experience}
                          </Badge>
                          <Badge variant="secondary" className="flex items-center gap-1">
                            <MapPin className="w-4 h-4" />
                            {lawyer.location}
                          </Badge>
                          <Badge
                            className={lawyer.availability === 'Available' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}
                          >
                            {lawyer.availability}
                          </Badge>
                        </div>
                        <p className="text-gray-600">{lawyer.bio}</p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Button
                      onClick={() => toggleExpand(lawyer.id)}
                      className="w-full bg-[#8B9D7F] hover:bg-[#7A8C6E] text-white"
                    >
                      <Mail className="w-4 h-4 mr-2" />
                      {expandedLawyer === lawyer.id ? 'Hide' : 'View'} Email Thread
                      {expandedLawyer === lawyer.id ? (
                        <ChevronUp className="w-4 h-4 ml-2" />
                      ) : (
                        <ChevronDown className="w-4 h-4 ml-2" />
                      )}
                    </Button>

                    {/* Email Thread */}
                    {expandedLawyer === lawyer.id && (
                      <div className="mt-6 space-y-4">
                        <h3 className="text-xl font-bold text-black mb-4">
                          Email Conversation
                        </h3>
                        {lawyer.emailThread.map((email, index) => (
                          <div
                            key={index}
                            className={`p-4 rounded-lg ${
                              email.from === 'LawlyAI Agent'
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
                              <p className="text-sm text-gray-500">{email.date}</p>
                            </div>
                            <p className="font-semibold text-black mb-2">
                              Subject: {email.subject}
                            </p>
                            <p className="text-gray-700 leading-relaxed">
                              {email.body}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}