import { useState, useEffect } from 'react';
import type { LocateData } from '../App';
import type { QueryResult, AnchorInfo as Anchor } from '../api';
import ResultCard from './ResultCard';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export default function HeroSection({ locateData }: { locateData: LocateData }) {
  const [domain, setDomain] = useState('');
  const [recordType, setRecordType] = useState('A');
  const [anchorId, setAnchorId] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [anchors, setAnchors] = useState<Anchor[]>([]);
  const [anchorStatus, setAnchorStatus] = useState<{ total: number; live: number } | null>(null);

  // Fetch anchors on mount
  useEffect(() => {
    async function getAnchors() {
      try {
        const res = await fetch(`${API_BASE}/api/anchors`);
        if (res.ok) {
          const data = await res.json();
          setAnchors(data);
        }
      } catch (err) {
        console.error('Failed to fetch anchors:', err);
      }
    }
    getAnchors();
  }, []);

  // Poll anchor status
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
          const d = await res.json();
          setAnchorStatus({ total: d.anchor_count, live: d.anchor_count });
        }
      } catch (err) {
        console.error('Failed to fetch health:', err);
      }
    };
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  const handleResolve = async () => {
    if (!domain.trim() || loading) return;
    setLoading(true);

    const body: Record<string, string> = { domain: domain.trim(), record_type: recordType };
    if (anchorId) body.anchor_id = anchorId;

    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        console.error(`Query failed: ${res.status}`);
      }
      
      const data = await res.json();
      setResults(prev => [{ ...data, timestamp: Date.now() }, ...prev].slice(0, 5));
    } catch (err) {
      console.error('Resolve error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="relative min-h-screen overflow-hidden">
      {/* Fullscreen looping video background */}
      <video
        className="absolute inset-0 w-full h-full object-cover z-0"
        autoPlay
        loop
        muted
        playsInline
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260306_074215_04640ca7-042c-45d6-bb56-58b1e8a42489.mp4"
      />

      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-black/40 z-[1]" />

      {/* Navbar */}
      <nav style={{ position: 'relative', zIndex: 10 }} className="flex justify-between items-center px-8 py-6 max-w-7xl mx-auto">
        {/* Left: logo + IP pill */}
        <div className="flex items-center gap-3">
          <span style={{ fontFamily: "'Instrument Serif', serif" }} className="text-2xl tracking-tight text-white flex-shrink-0">
            GeoDNS <span className="text-[var(--muted-foreground)] font-light text-xl">by</span> AIORI
          </span>

          {(!locateData || (locateData && locateData.is_india !== false)) && (
            <div className="glass-pill px-3 py-1 text-xs text-[var(--muted-foreground)] ml-1 hidden md:flex items-center gap-2 whitespace-nowrap">
              {!locateData ? (
                'Detecting...'
              ) : (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse flex-shrink-0" />
                  {locateData.ip} · {locateData.city}, {locateData.region}
                </>
              )}
            </div>
          )}
        </div>

        {/* Center: absolutely positioned */}
        <div style={{
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)',
        }}>
          <button
            className="text-sm font-medium transition-all"
            style={{
              fontFamily: 'var(--font-body)',
              color: 'rgba(255,255,255,0.9)',
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: '999px',
              padding: '0.35rem 1.1rem',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
              cursor: 'default',
            }}>
            Home
          </button>
        </div>

        {/* Right: anchor status */}
        <div className="glass-pill px-4 py-2 text-sm text-white flex items-center gap-2 whitespace-nowrap">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse flex-shrink-0" />
          {anchorStatus ? `${anchorStatus.live} / ${anchorStatus.total} anchors` : 'Connecting...'}
        </div>
      </nav>

      {/* Hero content */}
      <div className="relative z-10 flex flex-col items-center px-6 pt-20 pb-40">
        
        {/* H1 */}
        <h1 className="animate-fade-rise text-center w-full max-w-3xl"
          style={{
            fontFamily: "'Instrument Serif', serif",
            fontSize: 'clamp(2.8rem, 6vw, 5rem)',
            lineHeight: '1.05',
            letterSpacing: '-0.03em',
            fontWeight: 400,
            color: 'white',
            marginBottom: '1rem',
          }}>
          DNS doesn't lie.{' '}
          <em className="not-italic"
            style={{ color: 'var(--muted-foreground)' }}>
            Geography does.
          </em>
        </h1>

        {/* Subtitle */}
        <p className="animate-fade-rise-delay text-center w-full max-w-xl"
          style={{
            color: 'var(--muted-foreground)',
            fontSize: '1rem',
            lineHeight: '1.6',
            marginBottom: '2.5rem',
          }}>
          Resolve any domain from anchor nodes across India.
          See what your ISP actually returns.
        </p>

        {/* Main query bar — dark glass horizontal pill */}
        <div className="animate-fade-rise-delay-2 glass p-1 w-full max-w-3xl flex items-center gap-1" style={{ borderRadius: '20px' }}>
          {/* Domain input */}
          <input
            type="text"
            placeholder="e.g. google.com"
            value={domain}
            onChange={e => setDomain(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleResolve()}
            className="flex-1 glass-input text-base px-5 py-3 min-w-0"
          />

          {/* Record type selector */}
          <select
            value={recordType}
            onChange={e => setRecordType(e.target.value)}
            className="glass-input text-sm px-4 py-3 appearance-none cursor-pointer"
          >
            {['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {/* Anchor selector */}
          <select
            value={anchorId}
            onChange={e => setAnchorId(e.target.value)}
            className="glass-input text-sm px-4 py-3 appearance-none cursor-pointer hidden sm:block w-36"
          >
            <option value="">Auto · nearest</option>
            {anchors.map(a => (
              <option key={a.id} value={a.id}>{a.city}</option>
            ))}
          </select>

          {/* Resolve button */}
          <button
            onClick={handleResolve}
            disabled={!domain.trim() || loading}
            className="glass-btn px-6 py-3 text-sm flex items-center justify-center gap-2 whitespace-nowrap min-w-[110px]"
          >
            {loading ? <span className="w-3 h-3 border border-white/40 border-t-white rounded-full animate-spin flex-shrink-0" /> : <span style={{fontSize: '1.2rem', marginTop: '-1px'}}>⌕</span>}
            {loading ? 'Resolving...' : 'Resolve'}
          </button>
        </div>

        {/* Results log */}
        {results.length > 0 && (
          <div className="animate-fade-rise w-full max-w-3xl space-y-3 mt-4">
            {results.map((r, idx) => (
              <ResultCard key={idx} result={r} isLatest={idx === 0} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
