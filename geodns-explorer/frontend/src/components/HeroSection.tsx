export default function HeroSection() {
  const handleBeginJourney = () => {
    document.getElementById('query-section')?.scrollIntoView({ behavior: 'smooth' });
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
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4"
      />

      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-black/40 z-[1]" />

      {/* Navbar */}
      <nav className="relative z-10 flex justify-between items-center px-8 py-6 max-w-7xl mx-auto">
        <div
          className="text-3xl tracking-tight text-white"
          style={{ fontFamily: "'Instrument Serif', serif" }}
        >
          Velorah<sup className="text-xs">®</sup>
        </div>

        <div className="hidden md:flex gap-8 items-center">
          <a href="#" className="text-white text-sm">Home</a>
          <a href="#" className="text-[var(--muted-foreground)] hover:text-white transition-colors text-sm">Studio</a>
          <a href="#" className="text-[var(--muted-foreground)] hover:text-white transition-colors text-sm">About</a>
          <a href="#" className="text-[var(--muted-foreground)] hover:text-white transition-colors text-sm">Journal</a>
          <a href="#" className="text-[var(--muted-foreground)] hover:text-white transition-colors text-sm">Reach Us</a>
        </div>

        <button
          onClick={handleBeginJourney}
          className="liquid-glass rounded-full px-6 py-2.5 text-sm text-white hover:scale-[1.03] transition-transform cursor-pointer"
        >
          Begin Journey
        </button>
      </nav>

      {/* Hero content */}
      <div className="relative z-10 flex flex-col items-center text-center px-6 pt-32 pb-40">
        <h1
          className="animate-fade-rise text-5xl sm:text-7xl md:text-8xl leading-[0.95] max-w-7xl font-normal"
          style={{ fontFamily: "'Instrument Serif', serif", letterSpacing: '-2.46px' }}
        >
          Where{' '}
          <em className="not-italic" style={{ color: 'var(--muted-foreground)' }}>
            dreams
          </em>{' '}
          rise{' '}
          <em className="not-italic" style={{ color: 'var(--muted-foreground)' }}>
            through the silence.
          </em>
        </h1>

        <p className="animate-fade-rise-delay text-[var(--muted-foreground)] text-base sm:text-lg max-w-2xl mt-8 leading-relaxed">
          We're designing tools for deep thinkers, bold creators, and quiet rebels.
          Amid the chaos, we build digital spaces for sharp focus and inspired work.
        </p>

        <button
          onClick={handleBeginJourney}
          className="animate-fade-rise-delay-2 liquid-glass rounded-full px-14 py-5 text-base text-white mt-12 hover:scale-[1.03] transition-transform cursor-pointer"
        >
          Begin Journey
        </button>
      </div>
    </section>
  );
}
