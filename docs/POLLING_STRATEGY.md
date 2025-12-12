# Email Thread Polling Strategy

## Overview

The frontend uses **smart polling** to keep email threads and lawyer data up-to-date without requiring WebSockets or complex real-time infrastructure.

## How It Works

### 1. **Backend API Endpoints** (`backend/api_service.py`)

The FastAPI backend exposes several endpoints:

- `GET /api/conversations` - Get all email conversations
- `GET /api/conversations/{lawyer_email}` - Get conversations for a specific lawyer
- `GET /api/lawyers` - Get all tracked lawyers with their offers
- `GET /api/conversations/updated-since/{timestamp}` - Get only conversations updated since a timestamp (efficient for polling)
- `GET /api/stats` - Get overall statistics

### 2. **Frontend Polling Hook** (`hooks/use-polling.js`)

A custom React hook that implements smart polling with optimizations:

#### Features:
- ✅ **Page Visibility Detection** - Only polls when the page is visible (saves resources)
- ✅ **Exponential Backoff** - Increases interval when no updates are found (reduces server load)
- ✅ **Change Detection** - Only triggers updates when data actually changes
- ✅ **Configurable Intervals** - Base interval (5s) and max interval (30s)
- ✅ **Automatic Cleanup** - Cleans up timers on unmount

#### Usage Example:
```javascript
const { data, isLoading, lastUpdate } = usePolling(
  async () => await fetchLawyers(),
  {
    interval: 5000,        // Poll every 5 seconds
    maxInterval: 30000,    // Max 30 seconds if no updates
    enabled: true,
    onUpdate: (newData) => {
      // Called when data changes
      console.log('New data!', newData)
    }
  }
)
```

### 3. **Polling Strategy**

#### Initial Load:
- Frontend immediately fetches data when component mounts
- Shows loading state while fetching

#### Active Polling:
- Polls every **5 seconds** when data is changing
- If no changes detected, interval increases (5s → 7.5s → 11.25s → ... up to 30s max)
- When new data arrives, interval resets to 5 seconds

#### Page Visibility:
- Stops polling when user switches tabs (page hidden)
- Immediately polls when user returns to the page
- Saves bandwidth and server resources

#### Thread-Specific Polling:
- When a user expands a lawyer's email thread, that specific thread is polled every **3 seconds**
- Only the expanded thread is polled (not all threads)
- Stops polling when thread is collapsed

## Data Flow

```
┌─────────────────┐
│  Email Listener │  (Runs in background, processes emails)
│  (Backend)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Conversation    │  (Stores in email_conversations.json)
│ Manager        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI        │  (Exposes REST endpoints)
│  /api/*         │
└────────┬────────┘
         │
         │  Polling (every 5s)
         │
         ▼
┌─────────────────┐
│  Frontend       │  (usePolling hook)
│  React Hook     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  UI Updates     │  (Re-renders with new data)
│  Components     │
└─────────────────┘
```

## Performance Considerations

### Optimizations:

1. **Timestamp-Based Polling** (`/api/conversations/updated-since/{timestamp}`)
   - Only returns conversations that changed since last check
   - Reduces payload size significantly
   - Can be used for even more efficient polling

2. **Exponential Backoff**
   - Reduces server load when no activity
   - Automatically increases polling interval when idle
   - Resets to fast polling when activity resumes

3. **Page Visibility API**
   - Doesn't poll when user isn't looking
   - Saves bandwidth and battery on mobile devices

4. **Selective Thread Polling**
   - Only polls expanded threads at higher frequency
   - Other threads poll at normal interval

## Alternative Approaches (Future)

### WebSockets (Real-time)
- **Pros**: True real-time, no polling overhead
- **Cons**: More complex, requires WebSocket server, connection management
- **When to use**: If you need instant updates (< 1 second latency)

### Server-Sent Events (SSE)
- **Pros**: Simpler than WebSockets, one-way real-time updates
- **Cons**: Still requires server infrastructure changes
- **When to use**: If you only need server-to-client updates

### Long Polling
- **Pros**: Reduces number of requests
- **Cons**: Ties up server connections, more complex
- **When to use**: If you want to reduce request count but keep it simple

## Current Implementation Status

✅ Backend API endpoints created
✅ Polling hook implemented
✅ Example component created
⏳ Integration with search page (pending)
⏳ Start search endpoint (pending)

## Next Steps

1. Integrate `LawyerResultsWithPolling` component into `app/search/page.js`
2. Add endpoint to start lawyer search (`POST /api/search/start`)
3. Replace mock data with real API calls
4. Add error handling and retry logic
5. Add loading states and skeleton screens



