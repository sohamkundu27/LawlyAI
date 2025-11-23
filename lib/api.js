/**
 * API utility functions for communicating with the backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Fetch all conversations
 */
export async function fetchConversations() {
  const response = await fetch(`${API_BASE_URL}/api/conversations`)
  if (!response.ok) {
    throw new Error(`Failed to fetch conversations: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Fetch conversation for a specific lawyer
 */
export async function fetchLawyerConversation(lawyerEmail) {
  const response = await fetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(lawyerEmail)}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch lawyer conversation: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Fetch all lawyers
 */
export async function fetchLawyers() {
  const response = await fetch(`${API_BASE_URL}/api/lawyers`)
  if (!response.ok) {
    throw new Error(`Failed to fetch lawyers: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Fetch ranked lawyers based on quote, experience, and location
 */
export async function fetchRankedLawyers(caseType = null, maxPrice = null, userLocation = null) {
  const params = new URLSearchParams()
  if (caseType) params.append('case_type', caseType)
  if (maxPrice) params.append('max_price', maxPrice.toString())
  if (userLocation) params.append('user_location', userLocation)
  
  const url = `${API_BASE_URL}/api/lawyers/ranked${params.toString() ? '?' + params.toString() : ''}`
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch ranked lawyers: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Fetch conversations updated since a timestamp
 */
export async function fetchConversationsSince(timestamp) {
  const response = await fetch(`${API_BASE_URL}/api/conversations/updated-since/${encodeURIComponent(timestamp)}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch updated conversations: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Fetch statistics
 */
export async function fetchStats() {
  const response = await fetch(`${API_BASE_URL}/api/stats`)
  if (!response.ok) {
    throw new Error(`Failed to fetch stats: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Start a new lawyer search (initiate email outreach)
 * Note: lawyer_emails parameter is optional - backend uses hardcoded emails
 */
export async function startLawyerSearch(situation, lawyerEmails = null) {
  const response = await fetch(`${API_BASE_URL}/api/search/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      situation,
      lawyer_emails: lawyerEmails // Backend will use hardcoded emails anyway
    })
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(errorData.detail || `Failed to start search: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Get all threads where lawyers have requested phone calls
 */
export async function fetchPhoneCallRequests() {
  const response = await fetch(`${API_BASE_URL}/api/phone-call-requests`)
  if (!response.ok) {
    throw new Error(`Failed to fetch phone call requests: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Search for legal cases and get enriched lawyer results
 * @param {string} query - The user's legal situation description
 */
export async function searchLegal(query) {
  const response = await fetch(`${API_BASE_URL}/search-legal`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query })
  })
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(errorData.detail || `Failed to search: ${response.statusText}`)
  }
  
  return response.json()
}

