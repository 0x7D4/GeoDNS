import type { QueryResult } from '../api';

export default function ResultCard({ result: r, isLatest }: { result: QueryResult; isLatest: boolean }) {
  const isBlocked = r.status === 'BLOCKED';
  const isNxDomain = r.status === 'NXDOMAIN';
  const isResolved = r.status === 'RESOLVED' || r.status === 'OK';
  const isError = r.status === 'ERROR';
  
  const statusColor = isResolved ? '#4ade80' : isNxDomain ? '#facc15' : isBlocked ? '#f87171' : 'rgba(255,255,255,0.4)';
  const statusBg = isResolved ? 'rgba(34,197,94,0.15)' : isNxDomain ? 'rgba(234,179,8,0.15)' : isBlocked ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.08)';

  return (
    <div
      className="glass p-5 rounded-2xl w-full text-left"
      style={{
        borderLeft: isLatest ? '2px solid rgba(255,255,255,0.3)' : '1px solid rgba(255, 255, 255, 0.08)'
      }}
    >
      {/* Top row */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <code className="text-white font-mono text-sm font-medium">
          {r.domain}
        </code>
        {/* Record type badge */}
        <span className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.6)' }}
        >
          {r.record_type}
        </span>
        {/* Anchor badge */}
        <span className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)' }}
        >
          via {r.anchor_used?.city}
        </span>
        {/* Query time badge */}
        {r.query_time_ms != null && (
          <span className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.4)' }}
          >
            {r.query_time_ms}ms
          </span>
        )}
        {/* Status badge — colored */}
        <span className={`ml-auto text-xs px-2.5 py-0.5 rounded-full font-medium tracking-wide`}
          style={{ background: statusBg, color: statusColor }}
        >
          {r.status}
        </span>
        {/* Selection method badge */}
        <span className="text-xs px-2 py-0.5 rounded-full"
          style={{
            background: r.selection_method === 'auto' ? 'rgba(59,130,246,0.15)' : 'rgba(168,85,247,0.15)',
            color: r.selection_method === 'auto' ? '#60a5fa' : '#c084fc',
          }}
        >
          {r.selection_method === 'auto' ? 'AUTO' : 'MANUAL'}
        </span>
      </div>

      {/* Anchor detail row */}
      <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.7rem', marginBottom: '0.75rem' }}>
        Anchor: {r.anchor_used?.id}
        {r.resolver_used ? ` · Resolver: ${r.resolver_used}` : ''}
      </p>

      {/* Answers */}
      {r.answers && r.answers.length > 0 ? (
        <div className="space-y-1.5">
          {r.answers.map((ans, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg px-3 py-2"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              <code className="text-sm font-mono break-all" style={{ color: 'rgba(255,255,255,0.85)' }}>
                {ans}
              </code>
              <button
                onClick={() => navigator.clipboard.writeText(ans)}
                className="text-xs transition-colors ml-4 whitespace-nowrap"
                style={{ color: 'rgba(255,255,255,0.3)' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
              >
                copy
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg px-3 py-2.5 flex items-start gap-2"
          style={{
            background: isBlocked ? 'rgba(239,68,68,0.08)' : isNxDomain ? 'rgba(234,179,8,0.08)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${isBlocked ? 'rgba(239,68,68,0.2)' : isNxDomain ? 'rgba(234,179,8,0.2)' : 'rgba(255,255,255,0.08)'}`,
          }}
        >
          <span style={{ fontSize: '0.75rem' }}>
            {isBlocked ? '🚫' : isNxDomain ? '❓' : '⚠️'}
          </span>
          <div>
            <p className="text-xs font-medium"
              style={{ color: isBlocked ? '#f87171' : isNxDomain ? '#facc15' : 'rgba(255,255,255,0.5)' }}
            >
              {isBlocked
                ? 'Domain appears blocked at ISP level from this anchor'
                : isNxDomain
                ? 'Domain does not exist (NXDOMAIN)'
                : `Anchor ${r.anchor_used?.id ?? 'Unknown'} is unreachable`}
            </p>
            {r.error && (
              <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                {r.error === 'anchor_unreachable' ? `Timeout after 10s connecting to ${r.anchor_used?.id}` : r.error}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Raw output collapsible */}
      {r.raw_output && (
        <details className="mt-3">
          <summary className="text-xs cursor-pointer transition-colors"
            style={{ color: 'rgba(255,255,255,0.3)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
          >
            ▸ Raw dig output
          </summary>
          <pre className="mt-2 text-xs font-mono whitespace-pre-wrap break-all rounded-lg p-3"
            style={{
              color: 'rgba(255,255,255,0.35)',
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            {r.raw_output}
          </pre>
        </details>
      )}

      {/* Timestamp */}
      {r.timestamp && (
        <p className="mt-2 text-right" style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.2)' }}>
          {new Date(r.timestamp).toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}
