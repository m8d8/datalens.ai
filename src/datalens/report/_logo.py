"""Embedded Datalens logos — packaged so reports stay self-contained.

Source of truth: ``assets/logo.svg`` / ``assets/logo-dark.svg`` (repo root).
The ICON_* variants are the lens mark with the wordmark stripped and the
viewBox cropped; the header renders the "Datalens / Schema Analysis" wordmark
as HTML text beside the icon. Regenerate via the snippet in this file's PR.
"""

from __future__ import annotations

LOGO_LIGHT_SVG = r'''<svg viewBox="0 0 500 170" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif">
  <defs>
    <!-- Lens glass gradient -->
    <radialGradient id="lensGrad" cx="38%" cy="32%" r="65%">
      <stop offset="0%"   stop-color="#f0f9ff" stop-opacity="0.95"/>
      <stop offset="55%"  stop-color="#bae6fd" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0.25"/>
    </radialGradient>
    <!-- Rim gradient -->
    <linearGradient id="rimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
    <!-- Focal glow -->
    <radialGradient id="focalGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="#38bdf8" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
    </radialGradient>
    <!-- Clip to lens shape -->
    <clipPath id="lensClip">
      <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"/>
    </clipPath>
    <!-- Soft blur for glow effects -->
    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="focalFilter" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- ── LEFT DATA STREAMS (raw, fanning into lens) ───────────────────── -->
  <!-- 7 lines, diverging on left, converging toward lens entry at x≈65 -->
  <!-- Colors: warm→cool spectrum top to bottom -->
  <line x1="0"  y1="24"  x2="63"  y2="52"  stroke="#f43f5e" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="0"  y1="42"  x2="63"  y2="63"  stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="0"  y1="62"  x2="63"  y2="74"  stroke="#facc15" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="0"  y1="85"  x2="63"  y2="85"  stroke="#34d399" stroke-width="3.0" stroke-linecap="round" opacity="0.95"/>
  <line x1="0"  y1="108" x2="63"  y2="96"  stroke="#38bdf8" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="0"  y1="128" x2="63"  y2="107" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="0"  y1="146" x2="63"  y2="118" stroke="#c084fc" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>

  <!-- ── LENS BODY ─────────────────────────────────────────────────────── -->
  <!-- Biconvex lens: two Q-beziers meeting at left (65,85) and right (165,85) -->
  <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"
        fill="url(#lensGrad)"
        stroke="url(#rimGrad)"
        stroke-width="2.8"/>

  <!-- Inner glass highlight (top-left arc) -->
  <path d="M 78,63 Q 103,42 132,52"
        fill="none" stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.65"/>
  <!-- Secondary subtle highlight -->
  <path d="M 82,73 Q 100,60 116,64"
        fill="none" stroke="white" stroke-width="1.2" stroke-linecap="round" opacity="0.40"/>

  <!-- Data streams visible inside the lens (clipped, desaturated tint) -->
  <g clip-path="url(#lensClip)" opacity="0.35">
    <line x1="0" y1="24"  x2="200" y2="85" stroke="#f43f5e" stroke-width="2.2"/>
    <line x1="0" y1="42"  x2="200" y2="85" stroke="#fb923c" stroke-width="2.2"/>
    <line x1="0" y1="62"  x2="200" y2="85" stroke="#facc15" stroke-width="2.4"/>
    <line x1="0" y1="85"  x2="200" y2="85" stroke="#34d399" stroke-width="3.0"/>
    <line x1="0" y1="108" x2="200" y2="85" stroke="#38bdf8" stroke-width="2.4"/>
    <line x1="0" y1="128" x2="200" y2="85" stroke="#818cf8" stroke-width="2.2"/>
    <line x1="0" y1="146" x2="200" y2="85" stroke="#c084fc" stroke-width="2.2"/>
  </g>

  <!-- ── RIGHT DATA STREAMS (converging to focal point) ───────────────── -->
  <line x1="167" y1="52"  x2="205" y2="85" stroke="#f43f5e" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="167" y1="63"  x2="205" y2="85" stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="167" y1="74"  x2="205" y2="85" stroke="#facc15" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="167" y1="85"  x2="205" y2="85" stroke="#34d399" stroke-width="3.0" stroke-linecap="round" opacity="0.95"/>
  <line x1="167" y1="96"  x2="205" y2="85" stroke="#38bdf8" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="167" y1="107" x2="205" y2="85" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="167" y1="118" x2="205" y2="85" stroke="#c084fc" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>

  <!-- ── FOCAL POINT ───────────────────────────────────────────────────── -->
  <!-- Glow halo -->
  <circle cx="205" cy="85" r="14" fill="url(#focalGlow)" filter="url(#focalFilter)"/>
  <!-- Core dot -->
  <circle cx="205" cy="85" r="5"  fill="#0ea5e9" filter="url(#softGlow)"/>
  <circle cx="205" cy="85" r="2.5" fill="white"/>

  <!-- ── WORDMARK ───────────────────────────────────────────────────────── -->
  <text x="228" y="76" font-size="40" font-weight="800" letter-spacing="-1.5">
    <tspan fill="#0ea5e9">Data</tspan><tspan fill="#1e293b">lens</tspan>
  </text>
  <text x="230" y="104" font-size="13.5" font-weight="500" fill="#64748b" letter-spacing="3.5">SCHEMA ANALYSIS</text>

  <!-- ── TAGLINE SEPARATOR ─────────────────────────────────────────────── -->
  <line x1="230" y1="112" x2="498" y2="112" stroke="#e2e8f0" stroke-width="1"/>
</svg>
'''

LOGO_DARK_SVG = r'''<svg viewBox="0 0 500 170" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif">
  <defs>
    <!-- Dark lens gradient — deep ocean glass -->
    <radialGradient id="lensGradDark" cx="38%" cy="32%" r="65%">
      <stop offset="0%"   stop-color="#e0f2fe" stop-opacity="0.12"/>
      <stop offset="50%"  stop-color="#0369a1" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#0c4a6e" stop-opacity="0.35"/>
    </radialGradient>
    <!-- Rim: brighter cyan-to-violet on dark -->
    <linearGradient id="rimGradDark" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#22d3ee"/>
      <stop offset="100%" stop-color="#a78bfa"/>
    </linearGradient>
    <!-- Focal glow — more intense on dark -->
    <radialGradient id="focalGlowDark" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="#38bdf8" stop-opacity="1.0"/>
      <stop offset="60%"  stop-color="#38bdf8" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
    </radialGradient>
    <!-- Stream glow (makes lines bloom on dark bg) -->
    <filter id="streamGlow" x="-20%" y="-80%" width="140%" height="260%">
      <feGaussianBlur stdDeviation="1.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="focalFilterDark" x="-120%" y="-120%" width="340%" height="340%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="lensClipDark">
      <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"/>
    </clipPath>
  </defs>

  <!-- ── LEFT DATA STREAMS ──────────────────────────────────────────────── -->
  <g filter="url(#streamGlow)">
    <line x1="0"  y1="24"  x2="63"  y2="52"  stroke="#fb7185" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
    <line x1="0"  y1="42"  x2="63"  y2="63"  stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="0"  y1="62"  x2="63"  y2="74"  stroke="#fde047" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="0"  y1="85"  x2="63"  y2="85"  stroke="#4ade80" stroke-width="3.0" stroke-linecap="round"/>
    <line x1="0"  y1="108" x2="63"  y2="96"  stroke="#22d3ee" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="0"  y1="128" x2="63"  y2="107" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="0"  y1="146" x2="63"  y2="118" stroke="#e879f9" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
  </g>

  <!-- ── LENS BODY ──────────────────────────────────────────────────────── -->
  <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"
        fill="url(#lensGradDark)"
        stroke="url(#rimGradDark)"
        stroke-width="2.8"/>

  <!-- Glass highlight — brighter on dark for more depth -->
  <path d="M 78,63 Q 103,42 132,52"
        fill="none" stroke="#e0f2fe" stroke-width="2.2" stroke-linecap="round" opacity="0.50"/>
  <path d="M 82,73 Q 100,60 116,64"
        fill="none" stroke="#e0f2fe" stroke-width="1.4" stroke-linecap="round" opacity="0.28"/>

  <!-- Streams inside lens (clipped, subtle) -->
  <g clip-path="url(#lensClipDark)" opacity="0.30">
    <line x1="0" y1="24"  x2="200" y2="85" stroke="#fb7185" stroke-width="2.2"/>
    <line x1="0" y1="42"  x2="200" y2="85" stroke="#fb923c" stroke-width="2.2"/>
    <line x1="0" y1="62"  x2="200" y2="85" stroke="#fde047" stroke-width="2.4"/>
    <line x1="0" y1="85"  x2="200" y2="85" stroke="#4ade80" stroke-width="3.0"/>
    <line x1="0" y1="108" x2="200" y2="85" stroke="#22d3ee" stroke-width="2.4"/>
    <line x1="0" y1="128" x2="200" y2="85" stroke="#818cf8" stroke-width="2.2"/>
    <line x1="0" y1="146" x2="200" y2="85" stroke="#e879f9" stroke-width="2.2"/>
  </g>

  <!-- ── RIGHT DATA STREAMS (converging to focal point) ────────────────── -->
  <g filter="url(#streamGlow)">
    <line x1="167" y1="52"  x2="205" y2="85" stroke="#fb7185" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
    <line x1="167" y1="63"  x2="205" y2="85" stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="167" y1="74"  x2="205" y2="85" stroke="#fde047" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="167" y1="85"  x2="205" y2="85" stroke="#4ade80" stroke-width="3.0" stroke-linecap="round"/>
    <line x1="167" y1="96"  x2="205" y2="85" stroke="#22d3ee" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="167" y1="107" x2="205" y2="85" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="167" y1="118" x2="205" y2="85" stroke="#e879f9" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
  </g>

  <!-- ── FOCAL POINT ────────────────────────────────────────────────────── -->
  <circle cx="205" cy="85" r="18" fill="url(#focalGlowDark)" filter="url(#focalFilterDark)"/>
  <circle cx="205" cy="85" r="5.5" fill="#38bdf8"/>
  <circle cx="205" cy="85" r="2.5" fill="#e0f2fe"/>

  <!-- ── WORDMARK ───────────────────────────────────────────────────────── -->
  <text x="228" y="76" font-size="40" font-weight="800" letter-spacing="-1.5">
    <tspan fill="#38bdf8">Data</tspan><tspan fill="#f1f5f9">lens</tspan>
  </text>
  <text x="230" y="104" font-size="13.5" font-weight="500" fill="#64748b" letter-spacing="3.5">SCHEMA ANALYSIS</text>

  <!-- ── SEPARATOR ─────────────────────────────────────────────────────── -->
  <line x1="230" y1="112" x2="490" y2="112" stroke="#1e293b" stroke-width="1"/>
</svg>
'''

LOGO_ICON_LIGHT_SVG = r'''<svg viewBox="0 16 226 138" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif">
  <defs>
    <!-- Lens glass gradient -->
    <radialGradient id="lensGrad" cx="38%" cy="32%" r="65%">
      <stop offset="0%"   stop-color="#f0f9ff" stop-opacity="0.95"/>
      <stop offset="55%"  stop-color="#bae6fd" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0.25"/>
    </radialGradient>
    <!-- Rim gradient -->
    <linearGradient id="rimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
    <!-- Focal glow -->
    <radialGradient id="focalGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="#38bdf8" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
    </radialGradient>
    <!-- Clip to lens shape -->
    <clipPath id="lensClip">
      <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"/>
    </clipPath>
    <!-- Soft blur for glow effects -->
    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="focalFilter" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- ── LEFT DATA STREAMS (raw, fanning into lens) ───────────────────── -->
  <!-- 7 lines, diverging on left, converging toward lens entry at x≈65 -->
  <!-- Colors: warm→cool spectrum top to bottom -->
  <line x1="0"  y1="24"  x2="63"  y2="52"  stroke="#f43f5e" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="0"  y1="42"  x2="63"  y2="63"  stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="0"  y1="62"  x2="63"  y2="74"  stroke="#facc15" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="0"  y1="85"  x2="63"  y2="85"  stroke="#34d399" stroke-width="3.0" stroke-linecap="round" opacity="0.95"/>
  <line x1="0"  y1="108" x2="63"  y2="96"  stroke="#38bdf8" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="0"  y1="128" x2="63"  y2="107" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="0"  y1="146" x2="63"  y2="118" stroke="#c084fc" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>

  <!-- ── LENS BODY ─────────────────────────────────────────────────────── -->
  <!-- Biconvex lens: two Q-beziers meeting at left (65,85) and right (165,85) -->
  <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"
        fill="url(#lensGrad)"
        stroke="url(#rimGrad)"
        stroke-width="2.8"/>

  <!-- Inner glass highlight (top-left arc) -->
  <path d="M 78,63 Q 103,42 132,52"
        fill="none" stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.65"/>
  <!-- Secondary subtle highlight -->
  <path d="M 82,73 Q 100,60 116,64"
        fill="none" stroke="white" stroke-width="1.2" stroke-linecap="round" opacity="0.40"/>

  <!-- Data streams visible inside the lens (clipped, desaturated tint) -->
  <g clip-path="url(#lensClip)" opacity="0.35">
    <line x1="0" y1="24"  x2="200" y2="85" stroke="#f43f5e" stroke-width="2.2"/>
    <line x1="0" y1="42"  x2="200" y2="85" stroke="#fb923c" stroke-width="2.2"/>
    <line x1="0" y1="62"  x2="200" y2="85" stroke="#facc15" stroke-width="2.4"/>
    <line x1="0" y1="85"  x2="200" y2="85" stroke="#34d399" stroke-width="3.0"/>
    <line x1="0" y1="108" x2="200" y2="85" stroke="#38bdf8" stroke-width="2.4"/>
    <line x1="0" y1="128" x2="200" y2="85" stroke="#818cf8" stroke-width="2.2"/>
    <line x1="0" y1="146" x2="200" y2="85" stroke="#c084fc" stroke-width="2.2"/>
  </g>

  <!-- ── RIGHT DATA STREAMS (converging to focal point) ───────────────── -->
  <line x1="167" y1="52"  x2="205" y2="85" stroke="#f43f5e" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>
  <line x1="167" y1="63"  x2="205" y2="85" stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="167" y1="74"  x2="205" y2="85" stroke="#facc15" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="167" y1="85"  x2="205" y2="85" stroke="#34d399" stroke-width="3.0" stroke-linecap="round" opacity="0.95"/>
  <line x1="167" y1="96"  x2="205" y2="85" stroke="#38bdf8" stroke-width="2.4" stroke-linecap="round" opacity="0.85"/>
  <line x1="167" y1="107" x2="205" y2="85" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.80"/>
  <line x1="167" y1="118" x2="205" y2="85" stroke="#c084fc" stroke-width="2.2" stroke-linecap="round" opacity="0.75"/>

  <!-- ── FOCAL POINT ───────────────────────────────────────────────────── -->
  <!-- Glow halo -->
  <circle cx="205" cy="85" r="14" fill="url(#focalGlow)" filter="url(#focalFilter)"/>
  <!-- Core dot -->
  <circle cx="205" cy="85" r="5"  fill="#0ea5e9" filter="url(#softGlow)"/>
  <circle cx="205" cy="85" r="2.5" fill="white"/>
</svg>
'''

LOGO_ICON_DARK_SVG = r'''<svg viewBox="0 16 226 138" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif">
  <defs>
    <!-- Dark lens gradient — deep ocean glass -->
    <radialGradient id="lensGradDark" cx="38%" cy="32%" r="65%">
      <stop offset="0%"   stop-color="#e0f2fe" stop-opacity="0.12"/>
      <stop offset="50%"  stop-color="#0369a1" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#0c4a6e" stop-opacity="0.35"/>
    </radialGradient>
    <!-- Rim: brighter cyan-to-violet on dark -->
    <linearGradient id="rimGradDark" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#22d3ee"/>
      <stop offset="100%" stop-color="#a78bfa"/>
    </linearGradient>
    <!-- Focal glow — more intense on dark -->
    <radialGradient id="focalGlowDark" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="#38bdf8" stop-opacity="1.0"/>
      <stop offset="60%"  stop-color="#38bdf8" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
    </radialGradient>
    <!-- Stream glow (makes lines bloom on dark bg) -->
    <filter id="streamGlow" x="-20%" y="-80%" width="140%" height="260%">
      <feGaussianBlur stdDeviation="1.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="focalFilterDark" x="-120%" y="-120%" width="340%" height="340%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="lensClipDark">
      <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"/>
    </clipPath>
  </defs>

  <!-- ── LEFT DATA STREAMS ──────────────────────────────────────────────── -->
  <g filter="url(#streamGlow)">
    <line x1="0"  y1="24"  x2="63"  y2="52"  stroke="#fb7185" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
    <line x1="0"  y1="42"  x2="63"  y2="63"  stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="0"  y1="62"  x2="63"  y2="74"  stroke="#fde047" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="0"  y1="85"  x2="63"  y2="85"  stroke="#4ade80" stroke-width="3.0" stroke-linecap="round"/>
    <line x1="0"  y1="108" x2="63"  y2="96"  stroke="#22d3ee" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="0"  y1="128" x2="63"  y2="107" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="0"  y1="146" x2="63"  y2="118" stroke="#e879f9" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
  </g>

  <!-- ── LENS BODY ──────────────────────────────────────────────────────── -->
  <path d="M 65,85 Q 115,22 165,85 Q 115,148 65,85 Z"
        fill="url(#lensGradDark)"
        stroke="url(#rimGradDark)"
        stroke-width="2.8"/>

  <!-- Glass highlight — brighter on dark for more depth -->
  <path d="M 78,63 Q 103,42 132,52"
        fill="none" stroke="#e0f2fe" stroke-width="2.2" stroke-linecap="round" opacity="0.50"/>
  <path d="M 82,73 Q 100,60 116,64"
        fill="none" stroke="#e0f2fe" stroke-width="1.4" stroke-linecap="round" opacity="0.28"/>

  <!-- Streams inside lens (clipped, subtle) -->
  <g clip-path="url(#lensClipDark)" opacity="0.30">
    <line x1="0" y1="24"  x2="200" y2="85" stroke="#fb7185" stroke-width="2.2"/>
    <line x1="0" y1="42"  x2="200" y2="85" stroke="#fb923c" stroke-width="2.2"/>
    <line x1="0" y1="62"  x2="200" y2="85" stroke="#fde047" stroke-width="2.4"/>
    <line x1="0" y1="85"  x2="200" y2="85" stroke="#4ade80" stroke-width="3.0"/>
    <line x1="0" y1="108" x2="200" y2="85" stroke="#22d3ee" stroke-width="2.4"/>
    <line x1="0" y1="128" x2="200" y2="85" stroke="#818cf8" stroke-width="2.2"/>
    <line x1="0" y1="146" x2="200" y2="85" stroke="#e879f9" stroke-width="2.2"/>
  </g>

  <!-- ── RIGHT DATA STREAMS (converging to focal point) ────────────────── -->
  <g filter="url(#streamGlow)">
    <line x1="167" y1="52"  x2="205" y2="85" stroke="#fb7185" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
    <line x1="167" y1="63"  x2="205" y2="85" stroke="#fb923c" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="167" y1="74"  x2="205" y2="85" stroke="#fde047" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="167" y1="85"  x2="205" y2="85" stroke="#4ade80" stroke-width="3.0" stroke-linecap="round"/>
    <line x1="167" y1="96"  x2="205" y2="85" stroke="#22d3ee" stroke-width="2.4" stroke-linecap="round" opacity="0.90"/>
    <line x1="167" y1="107" x2="205" y2="85" stroke="#818cf8" stroke-width="2.2" stroke-linecap="round" opacity="0.88"/>
    <line x1="167" y1="118" x2="205" y2="85" stroke="#e879f9" stroke-width="2.2" stroke-linecap="round" opacity="0.85"/>
  </g>

  <!-- ── FOCAL POINT ────────────────────────────────────────────────────── -->
  <circle cx="205" cy="85" r="18" fill="url(#focalGlowDark)" filter="url(#focalFilterDark)"/>
  <circle cx="205" cy="85" r="5.5" fill="#38bdf8"/>
  <circle cx="205" cy="85" r="2.5" fill="#e0f2fe"/>
</svg>
'''
