import { useState, useEffect, useRef } from 'react'

/**
 * Custom hook for smart polling with optimizations:
 * - Only polls when page is visible
 * - Exponential backoff when no updates
 * - Configurable intervals
 * - Automatic cleanup
 * 
 * @param {Function} fetchFn - Function that returns a Promise with the data
 * @param {Object} options - Configuration options
 * @param {number} options.interval - Base polling interval in ms (default: 5000)
 * @param {number} options.maxInterval - Maximum interval in ms (default: 30000)
 * @param {boolean} options.enabled - Whether polling is enabled (default: true)
 * @param {Function} options.onUpdate - Callback when data changes
 * @param {Function} options.shouldContinue - Function to determine if polling should continue
 * 
 * @returns {Object} { data, error, isLoading, lastUpdate }
 */
export function usePolling(fetchFn, options = {}) {
  const {
    interval = 5000, // 5 seconds default
    maxInterval = 30000, // 30 seconds max
    enabled = true,
    onUpdate = null,
    shouldContinue = () => true
  } = options

  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)

  const intervalRef = useRef(null)
  const currentIntervalRef = useRef(interval)
  const timeoutRef = useRef(null)
  const isMountedRef = useRef(true)

  // Check if page is visible
  const isPageVisible = () => {
    if (typeof document === 'undefined') return true
    return !document.hidden
  }

  const fetchData = async () => {
    if (!enabled || !shouldContinue() || !isPageVisible()) {
      return
    }

    try {
      setIsLoading(true)
      const result = await fetchFn()
      
      if (!isMountedRef.current) return

      // Check if data actually changed
      const dataChanged = JSON.stringify(data) !== JSON.stringify(result)
      
      if (dataChanged) {
        setData(result)
        setLastUpdate(new Date())
        setError(null)
        
        // Reset to base interval when we get new data
        currentIntervalRef.current = interval
        
        // Call update callback if provided
        if (onUpdate) {
          onUpdate(result, data)
        }
      } else {
        // No changes - increase interval (exponential backoff)
        currentIntervalRef.current = Math.min(
          currentIntervalRef.current * 1.5,
          maxInterval
        )
      }
    } catch (err) {
      if (!isMountedRef.current) return
      setError(err)
      console.error('Polling error:', err)
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }

  useEffect(() => {
    isMountedRef.current = true

    // Don't proceed if not enabled
    if (!enabled) {
      return
    }

    // Initial fetch
    fetchData()

    // Set up polling
    const scheduleNext = () => {
      if (!isMountedRef.current || !enabled) {
        return
      }

      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        if (!isMountedRef.current || !enabled) {
          return
        }

        if (shouldContinue() && isPageVisible()) {
          fetchData().then(() => {
            if (isMountedRef.current && enabled) {
              scheduleNext()
            }
          })
        } else if (enabled) {
          // Still schedule next even if we skipped this one
          scheduleNext()
        }
      }, currentIntervalRef.current)
    }

    scheduleNext()

    // Handle page visibility changes
    const handleVisibilityChange = () => {
      if (isPageVisible() && enabled && isMountedRef.current) {
        // Immediately fetch when page becomes visible
        fetchData()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    // Cleanup
    return () => {
      isMountedRef.current = false
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [enabled]) // Only re-run when enabled changes, not fetchFn

  return {
    data,
    error,
    isLoading,
    lastUpdate,
    // Manual refresh function
    refresh: () => {
      currentIntervalRef.current = interval
      return fetchData()
    }
  }
}

