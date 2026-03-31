import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Copy, ChevronDown, Trash2, Search, AlertTriangle } from 'lucide-react';
import type { LocateResponse, AnchorInfo, QueryResult } from '../api';
import { fetchLocate, fetchAnchors, fetchQuery } from '../api';

const RECORD_TYPES = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA'] as const;
const MAX_HISTORY = 10;

/* ─── Status badge colors ──────────────────────────────────── */
function statusColor(status?: string) {
  switch (status?.toUpperCase()) {
    case 'OK': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    case 'NXDOMAIN': return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    case 'BLOCKED': return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'TIMEOUT':
    case 'UNREACHABLE': return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
    default: return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
  }
}

function statusLabel(result: QueryResult) {
  if (result.error === 'anchor_unreachable') return 'UNREACHABLE';
  return result.status?.toUpperCase() || 'UNKNOWN';
}

/* ─── Location Banner ──────────────────────────────────────── */
function LocationBanner({
  locate,
  loading,
  error,
}: {
  locate: LocateResponse | null;
  loading: boolean;
  error: string | null;
}) {
  if (error) {
    return (
      <div className="liquid-glass rounded-xl p-4 mb-6 flex items-center gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
        <span className="text-sm text-amber-400">{error}</span>
      </div>
    );
  }

  if (loading || !locate) {
    return (
      <div className="liquid-glass rounded-xl p-4 mb-6 flex items-center gap-4">
        <div className="skeleton-pulse h-5 w-5 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="skeleton-pulse h-4 w-48" />
          <div className="skeleton-pulse h-3 w-32" />
        </div>
      </div>
    );
  }

  const { location, nearest_anchor } = locate;
  const isIndia = location.is_india;

  return (
    <div className="liquid-glass rounded-xl p-4 mb-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="text-lg">🇮🇳</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-white font-medium truncate">
            {location.city}, {location.region}
            <span className="text-[var(--muted-foreground)] ml-2">• {location.isp}</span>
          </p>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
            Nearest anchor: <span className="text-white">{nearest_anchor.city}</span>
            <span className="text-[var(--muted-foreground)] ml-1">({nearest_anchor.id})</span>
          </p>
        </div>
        {location.source === 'mock-local' && (
          <span className="text-xs text-amber-400/80 bg-amber-400/10 px-2 py-0.5 rounded-full">
            Local dev mode
          </span>
        )}
      </div>
      {!isIndia && (
        <p className="text-xs text-amber-400 mt-2 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5" />
          Location outside India — using center of India as fallback
        </p>
      )}
    </div>
  );
}

/* ─── Query Form ───────────────────────────────────────────── */
function QueryForm({
  anchors,
  onSubmit,
  isQuerying,
}: {
  anchors: AnchorInfo[];
  onSubmit: (domain: string, recordType: string, anchorId?: string) => void;
  isQuerying: boolean;
}) {
  const [domain, setDomain] = useState('');
  const [recordType, setRecordType] = useState<string>('A');
  const [selectedAnchor, setSelectedAnchor] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = domain.trim();
    if (!trimmed) {
      toast.error('Please enter a domain name');
      return;
    }
    onSubmit(trimmed, recordType, selectedAnchor || undefined);
  };

  return (
    <form onSubmit={handleSubmit} className="liquid-glass rounded-xl p-6 mb-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Domain input */}
        <div className="sm:col-span-2 lg:col-span-1">
          <label className="block text-xs text-[var(--muted-foreground)] mb-1.5 uppercase tracking-wider">
            Domain
          </label>
          <input
            id="domain-input"
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="e.g. google.com"
            className="w-full bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-white/20 transition"
          />
        </div>

        {/* Record type */}
        <div>
          <label className="block text-xs text-[var(--muted-foreground)] mb-1.5 uppercase tracking-wider">
            Record Type
          </label>
          <div className="relative">
            <select
              id="record-type-select"
              value={recordType}
              onChange={(e) => setRecordType(e.target.value)}
              className="w-full bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-white text-sm appearance-none focus:outline-none focus:ring-1 focus:ring-white/20 transition cursor-pointer"
            >
              {RECORD_TYPES.map((rt) => (
                <option key={rt} value={rt}>{rt}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)] pointer-events-none" />
          </div>
        </div>

        {/* Anchor override */}
        <div>
          <label className="block text-xs text-[var(--muted-foreground)] mb-1.5 uppercase tracking-wider">
            Anchor
          </label>
          <div className="relative">
            <select
              id="anchor-select"
              value={selectedAnchor}
              onChange={(e) => setSelectedAnchor(e.target.value)}
              className="w-full bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-white text-sm appearance-none focus:outline-none focus:ring-1 focus:ring-white/20 transition cursor-pointer"
            >
              <option value="">Auto (nearest)</option>
              {anchors.map((a) => (
                <option key={a.id} value={a.id}>{a.city}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)] pointer-events-none" />
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-end">
          <button
            id="resolve-button"
            type="submit"
            disabled={isQuerying}
            className="w-full liquid-glass rounded-lg px-6 py-2.5 text-sm text-white font-medium hover:scale-[1.02] active:scale-[0.98] transition-transform cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isQuerying ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Resolving…
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Resolve →
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}

/* ─── Result Card ──────────────────────────────────────────── */
function ResultCard({ result, index }: { result: QueryResult; index: number }) {
  const status = statusLabel(result);
  const isUnreachable = result.error === 'anchor_unreachable';
  const isBlocked = status === 'BLOCKED';

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  return (
    <div
      className="liquid-glass rounded-xl p-5 animate-fade-rise"
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <code className="text-white font-medium text-sm bg-white/5 px-2 py-0.5 rounded">
          {result.domain}
        </code>
        <span className="text-xs text-[var(--muted-foreground)] bg-white/5 px-2 py-0.5 rounded">
          {result.record_type || result.anchor_used?.id}
        </span>
        {result.anchor_used && (
          <span className="text-xs text-[var(--muted-foreground)]">
            via <span className="text-white">{result.anchor_used.city}</span>
          </span>
        )}
        <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColor(status)}`}>
          {status}
        </span>
        {result.selection_method && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              result.selection_method === 'auto'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'bg-blue-500/15 text-blue-400'
            }`}
          >
            {result.selection_method.toUpperCase()}
          </span>
        )}
        {result.query_time_ms != null && (
          <span className="text-xs text-[var(--muted-foreground)] ml-auto">
            {result.query_time_ms}ms
          </span>
        )}
      </div>

      {/* Answers */}
      {isUnreachable ? (
        <div className="bg-zinc-900/60 rounded-lg p-3 text-sm">
          <p className="text-zinc-400">
            ⚠ Anchor <code className="text-white">{result.anchor_id}</code> is unreachable
          </p>
          {result.error_detail && (
            <p className="text-xs text-zinc-500 mt-1">{result.error_detail}</p>
          )}
        </div>
      ) : (
        <>
          {result.answers && result.answers.length > 0 ? (
            <div className="space-y-1.5">
              {result.answers.map((ans, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between bg-zinc-900/60 rounded-lg px-3 py-2 group"
                >
                  <code className="text-sm text-emerald-400 font-mono">{ans}</code>
                  <button
                    onClick={() => handleCopy(ans)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-white/10 rounded"
                    title="Copy"
                  >
                    <Copy className="w-3.5 h-3.5 text-zinc-400" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-500 italic">No answers returned</p>
          )}

          {/* BLOCKED explanation */}
          {isBlocked && (
            <div className="mt-3 bg-red-500/5 border border-red-500/10 rounded-lg p-3">
              <p className="text-xs text-red-400">
                ⛔ This domain appears blocked at the ISP level from this anchor.
                {result.resolver_used && result.resolver_used !== 'system default' && (
                  <> Resolver used: <code className="text-red-300">{result.resolver_used}</code></>
                )}
              </p>
            </div>
          )}

          {/* Raw output collapsible */}
          {result.raw_output && (
            <details className="mt-3">
              <summary className="text-xs text-[var(--muted-foreground)] cursor-pointer hover:text-white transition-colors">
                Raw dig output
              </summary>
              <pre className="mt-2 text-xs text-zinc-400 bg-zinc-900/60 rounded-lg p-3 overflow-x-auto font-mono whitespace-pre-wrap">
                {result.raw_output}
              </pre>
            </details>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Results Panel ────────────────────────────────────────── */
function ResultsPanel({
  results,
  onClear,
}: {
  results: QueryResult[];
  onClear: () => void;
}) {
  if (results.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm text-[var(--muted-foreground)] uppercase tracking-wider">
          Results ({results.length})
        </h3>
        <button
          onClick={onClear}
          className="text-xs text-zinc-500 hover:text-red-400 transition-colors flex items-center gap-1 cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Clear
        </button>
      </div>
      <div className="space-y-4">
        {results.map((r, i) => (
          <ResultCard key={`${r.domain}-${r.anchor_used?.id}-${i}`} result={r} index={i} />
        ))}
      </div>
    </div>
  );
}

/* ─── Main Query Section ───────────────────────────────────── */
export default function QuerySection() {
  const [locate, setLocate] = useState<LocateResponse | null>(null);
  const [locLoading, setLocLoading] = useState(true);
  const [locError, setLocError] = useState<string | null>(null);
  const [anchors, setAnchors] = useState<AnchorInfo[]>([]);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);

  // Auto-detect location on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [loc, anch] = await Promise.all([fetchLocate(), fetchAnchors()]);
        if (!cancelled) {
          setLocate(loc);
          setAnchors(anch);
        }
      } catch (err) {
        if (!cancelled) {
          setLocError('Could not detect location. Is the backend running?');
          console.error('Location fetch error:', err);
        }
      } finally {
        if (!cancelled) setLocLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleQuery = useCallback(
    async (domain: string, recordType: string, anchorId?: string) => {
      setIsQuerying(true);
      try {
        const result = await fetchQuery(domain, recordType, anchorId);
        setResults((prev) => [result, ...prev].slice(0, MAX_HISTORY));
      } catch (err) {
        toast.error('Network error — could not reach backend');
        console.error('Query error:', err);
      } finally {
        setIsQuerying(false);
      }
    },
    []
  );

  return (
    <section
      id="query-section"
      className="min-h-screen px-6 py-24"
      style={{ background: 'var(--background)' }}
    >
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="mb-10">
          <h2
            className="text-3xl sm:text-4xl text-white mb-3"
            style={{ fontFamily: "'Instrument Serif', serif" }}
          >
            DNS Explorer
          </h2>
          <p className="text-[var(--muted-foreground)] text-sm max-w-2xl">
            Resolve domains from anchor nodes across India to visualize how DNS behaves differently by geography and ISP.
          </p>
        </div>

        <LocationBanner locate={locate} loading={locLoading} error={locError} />
        <QueryForm anchors={anchors} onSubmit={handleQuery} isQuerying={isQuerying} />
        <ResultsPanel results={results} onClear={() => setResults([])} />
      </div>
    </section>
  );
}
