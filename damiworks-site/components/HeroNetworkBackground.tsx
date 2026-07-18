'use client'

import { useEffect, useState } from 'react'
import Particles, { ParticlesProvider } from '@tsparticles/react'
import { loadSlim } from '@tsparticles/slim'
import type { Engine, ISourceOptions } from '@tsparticles/engine'

// ParticlesProvider requires this callback to be a single stable reference
// for the app's lifetime (it throws if a different function is ever passed).
const registerPlugins = async (engine: Engine) => {
  await loadSlim(engine)
}

const options: ISourceOptions = {
  fullScreen: { enable: false },
  background: { color: { value: 'transparent' } },
  fpsLimit: 60,
  particles: {
    number: { value: 90, density: { enable: true, width: 1440, height: 900 } },
    color: { value: '#d77855' },
    opacity: { value: 0.5 },
    size: { value: { min: 1, max: 3 } },
    links: {
      enable: true,
      color: '#d77855',
      distance: 170,
      opacity: 0.3,
      width: 1,
    },
    move: {
      enable: true,
      speed: 0.35,
      direction: 'none',
      random: true,
      straight: false,
      outModes: { default: 'out' },
    },
  },
  interactivity: {
    events: { resize: { enable: true } },
  },
  detectRetina: true,
}

// Neural-network-style hero backdrop: sparse drifting nodes connected by
// thin lines, in the site's terracotta accent. Skips rendering entirely
// under prefers-reduced-motion, same convention as the rest of the site's
// motion (see globals.css).
export default function HeroNetworkBackground() {
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    setReducedMotion(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  }, [])

  if (reducedMotion) return null

  return (
    <div className="absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
      <ParticlesProvider init={registerPlugins}>
        <Particles id="hero-network" options={options} className="h-full w-full" />
      </ParticlesProvider>
    </div>
  )
}
