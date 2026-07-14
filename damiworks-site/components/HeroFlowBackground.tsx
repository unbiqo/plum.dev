export default function HeroFlowBackground() {
  return (
    <div className="hero-flow-background" aria-hidden="true">
      <div className="hero-flow-glow hero-flow-glow-one" />
      <div className="hero-flow-glow hero-flow-glow-two" />

      <svg viewBox="0 0 1440 760" preserveAspectRatio="none" role="presentation">
        <defs>
          <linearGradient id="flowLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#D77855" stopOpacity="0" />
            <stop offset="0.42" stopColor="#D77855" stopOpacity="0.16" />
            <stop offset="1" stopColor="#D77855" stopOpacity="0.02" />
          </linearGradient>
          <filter id="packetGlow" x="-200%" y="-200%" width="400%" height="400%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g className="hero-flow-lines">
          <path d="M-80 570 C 260 570, 350 420, 710 420 S 1080 310, 1520 310" />
          <path d="M-60 260 C 260 260, 390 350, 710 350 S 1090 430, 1510 430" />
          <path d="M180 800 C 330 610, 520 500, 730 500 S 1080 380, 1510 380" />
        </g>

        <g className="hero-flow-packets" filter="url(#packetGlow)">
          <circle r="3.5">
            <animateMotion dur="15s" repeatCount="indefinite" begin="-2s" path="M-80 570 C 260 570, 350 420, 710 420 S 1080 310, 1520 310" />
          </circle>
          <circle r="3">
            <animateMotion dur="18s" repeatCount="indefinite" begin="-11s" path="M-60 260 C 260 260, 390 350, 710 350 S 1090 430, 1510 430" />
          </circle>
          <circle r="3.5">
            <animateMotion dur="17s" repeatCount="indefinite" begin="-7s" path="M180 800 C 330 610, 520 500, 730 500 S 1080 380, 1510 380" />
          </circle>
        </g>

        <g className="hero-flow-nodes">
          <circle cx="710" cy="420" r="4" />
          <circle cx="710" cy="350" r="4" />
          <circle cx="730" cy="500" r="4" />
        </g>
      </svg>
    </div>
  )
}
