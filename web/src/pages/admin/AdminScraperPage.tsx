import { useState, useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { adminApi } from '../../api'
import { RefreshCw, Search, Trash2, CheckCircle, AlertCircle } from 'lucide-react'

type ToolStatus = 'idle' | 'running' | 'completed' | 'failed'

function useToolTimer(isPending: boolean) {
  const startRef = useRef<number | null>(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (isPending) {
      startRef.current = Date.now()
      setElapsed(0)
      const interval = setInterval(() => {
        if (startRef.current) {
          setElapsed(Math.floor((Date.now() - startRef.current) / 1000))
        }
      }, 1000)
      return () => clearInterval(interval)
    } else {
      startRef.current = null
    }
  }, [isPending])

  return elapsed
}

function formatElapsed(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

function ToolStatusBadge({ status, elapsed, result }: { status: ToolStatus; elapsed: number; result?: string }) {
  if (status === 'idle') return null
  return (
    <div className="mt-3">
      {status === 'running' && (
        <div className="flex items-center gap-2 text-sm text-blue-600">
          <RefreshCw size={14} className="animate-spin" />
          <span>Running... {formatElapsed(elapsed)}</span>
        </div>
      )}
      {status === 'completed' && (
        <div className="flex items-center gap-2 text-sm text-green-600">
          <CheckCircle size={14} />
          <span>{result || 'Completed'}</span>
        </div>
      )}
      {status === 'failed' && (
        <div className="flex items-center gap-2 text-sm text-red-600">
          <AlertCircle size={14} />
          <span>{result || 'Failed'}</span>
        </div>
      )}
    </div>
  )
}

export default function AdminScraperPage() {
  // Scraper state
  const [scraperCategories, setScraperCategories] = useState('')
  const [maxSources, setMaxSources] = useState(0)

  // Searcher state
  const [searchTerm, setSearchTerm] = useState('')
  const [searchLocation, setSearchLocation] = useState('')
  const [searchSites, setSearchSites] = useState('indeed,linkedin')
  const [resultsWanted, setResultsWanted] = useState(15)

  // Matcher state
  const [llmPass, setLlmPass] = useState(false)
  const [matcherLimit, setMatcherLimit] = useState(100)

  // Cleanup state
  const [daysOld, setDaysOld] = useState(30)
  const [checkUrls, setCheckUrls] = useState(false)

  // Tool statuses and results
  const [scraperStatus, setScraperStatus] = useState<ToolStatus>('idle')
  const [scraperResult, setScraperResult] = useState('')
  const [searcherStatus, setSearcherStatus] = useState<ToolStatus>('idle')
  const [searcherResult, setSearcherResult] = useState('')
  const [matcherStatus, setMatcherStatus] = useState<ToolStatus>('idle')
  const [matcherResult, setMatcherResult] = useState('')
  const [cleanupStatus, setCleanupStatus] = useState<ToolStatus>('idle')
  const [cleanupResult, setCleanupResult] = useState('')

  const scraperMutation = useMutation({
    mutationFn: () => adminApi.runScraper({
      categories: scraperCategories || undefined,
      max_sources: maxSources || undefined,
    }),
    onMutate: () => { setScraperStatus('running'); setScraperResult('') },
    onSuccess: (data) => { setScraperStatus('completed'); setScraperResult(data.message) },
    onError: () => { setScraperStatus('failed'); setScraperResult('Failed to start scraper') },
  })

  const searcherMutation = useMutation({
    mutationFn: () => adminApi.runSearcher({
      search_term: searchTerm,
      location: searchLocation || undefined,
      sites: searchSites,
      results_wanted: resultsWanted,
    }),
    onMutate: () => { setSearcherStatus('running'); setSearcherResult('') },
    onSuccess: (data) => { setSearcherStatus('completed'); setSearcherResult(data.message) },
    onError: () => { setSearcherStatus('failed'); setSearcherResult('Failed to start searcher') },
  })

  const matcherMutation = useMutation({
    mutationFn: () => adminApi.runMatcher({
      llm_pass: llmPass,
      limit: matcherLimit,
    }),
    onMutate: () => { setMatcherStatus('running'); setMatcherResult('') },
    onSuccess: (data) => { setMatcherStatus('completed'); setMatcherResult(data.message) },
    onError: () => { setMatcherStatus('failed'); setMatcherResult('Failed to start matcher') },
  })

  const cleanupMutation = useMutation({
    mutationFn: () => adminApi.runCleanup({
      days_old: daysOld,
      check_urls: checkUrls,
    }),
    onMutate: () => { setCleanupStatus('running'); setCleanupResult('') },
    onSuccess: (data) => { setCleanupStatus('completed'); setCleanupResult(data.message) },
    onError: () => { setCleanupStatus('failed'); setCleanupResult('Failed to start cleanup') },
  })

  const scraperElapsed = useToolTimer(scraperMutation.isPending)
  const searcherElapsed = useToolTimer(searcherMutation.isPending)
  const matcherElapsed = useToolTimer(matcherMutation.isPending)
  const cleanupElapsed = useToolTimer(cleanupMutation.isPending)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">System Operations</h1>
        <p className="text-gray-600 mt-1">
          Run scraper, searcher, matcher, and cleanup operations
        </p>
      </div>

      {/* Job Scraper */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <RefreshCw className="text-blue-600" size={24} />
          <h2 className="text-lg font-semibold">Job Scraper</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Scrape job listings from company career pages defined in JobOpeningsLink.md
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Categories (comma-separated)</label>
            <input
              type="text"
              value={scraperCategories}
              onChange={(e) => setScraperCategories(e.target.value)}
              className="input"
              placeholder="Leave empty for all"
            />
          </div>
          <div>
            <label className="label">Max Sources (0 for all)</label>
            <input
              type="number"
              value={maxSources}
              onChange={(e) => setMaxSources(parseInt(e.target.value) || 0)}
              className="input"
              min={0}
            />
          </div>
        </div>
        <button
          onClick={() => scraperMutation.mutate()}
          disabled={scraperMutation.isPending}
          className="btn btn-primary"
        >
          {scraperMutation.isPending ? 'Running...' : 'Run Scraper'}
        </button>
        <ToolStatusBadge status={scraperStatus} elapsed={scraperElapsed} result={scraperResult} />
      </div>

      {/* Job Searcher */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Search className="text-green-600" size={24} />
          <h2 className="text-lg font-semibold">Job Searcher</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Search job aggregators (Indeed, LinkedIn, Glassdoor, etc.) for listings
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Search Term *</label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input"
              placeholder="Software Engineer"
              required
            />
          </div>
          <div>
            <label className="label">Location</label>
            <input
              type="text"
              value={searchLocation}
              onChange={(e) => setSearchLocation(e.target.value)}
              className="input"
              placeholder="Seattle, WA"
            />
          </div>
          <div>
            <label className="label">Sites</label>
            <input
              type="text"
              value={searchSites}
              onChange={(e) => setSearchSites(e.target.value)}
              className="input"
              placeholder="indeed,linkedin,glassdoor"
            />
          </div>
          <div>
            <label className="label">Results Wanted</label>
            <input
              type="number"
              value={resultsWanted}
              onChange={(e) => setResultsWanted(parseInt(e.target.value) || 15)}
              className="input"
              min={1}
              max={50}
            />
          </div>
        </div>
        <button
          onClick={() => searcherMutation.mutate()}
          disabled={searcherMutation.isPending || !searchTerm.trim()}
          className="btn btn-primary"
        >
          {searcherMutation.isPending ? 'Running...' : 'Run Searcher'}
        </button>
        <ToolStatusBadge status={searcherStatus} elapsed={searcherElapsed} result={searcherResult} />
      </div>

      {/* Job Matcher */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <RefreshCw className="text-purple-600" size={24} />
          <h2 className="text-lg font-semibold">Job Matcher</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Analyze cached jobs against user profile using keyword and optional LLM matching
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Max Jobs to Match</label>
            <input
              type="number"
              value={matcherLimit}
              onChange={(e) => setMatcherLimit(parseInt(e.target.value) || 100)}
              className="input"
              min={1}
              max={500}
            />
          </div>
          <div className="flex items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={llmPass}
                onChange={(e) => setLlmPass(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span>Enable LLM Pass (slower but more accurate)</span>
            </label>
          </div>
        </div>
        <button
          onClick={() => matcherMutation.mutate()}
          disabled={matcherMutation.isPending}
          className="btn btn-primary"
        >
          {matcherMutation.isPending ? 'Running...' : 'Run Matcher'}
        </button>
        <ToolStatusBadge status={matcherStatus} elapsed={matcherElapsed} result={matcherResult} />
      </div>

      {/* Cleanup */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Trash2 className="text-red-600" size={24} />
          <h2 className="text-lg font-semibold">Cleanup</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Remove old or dead job listings from the cache
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Remove jobs older than (days)</label>
            <input
              type="number"
              value={daysOld}
              onChange={(e) => setDaysOld(parseInt(e.target.value) || 30)}
              className="input"
              min={1}
            />
          </div>
          <div className="flex items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={checkUrls}
                onChange={(e) => setCheckUrls(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span>Check if URLs are still valid (slow)</span>
            </label>
          </div>
        </div>
        <button
          onClick={() => cleanupMutation.mutate()}
          disabled={cleanupMutation.isPending}
          className="btn btn-danger"
        >
          {cleanupMutation.isPending ? 'Running...' : 'Run Cleanup'}
        </button>
        <ToolStatusBadge status={cleanupStatus} elapsed={cleanupElapsed} result={cleanupResult} />
      </div>
    </div>
  )
}
