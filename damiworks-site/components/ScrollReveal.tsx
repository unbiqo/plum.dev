'use client'

import { useEffect, useRef, useState } from 'react'

type ScrollRevealProps = {
  children: React.ReactNode
  className?: string
  delayMs?: number
}

export default function ScrollReveal({ children, className = '', delayMs = 0 }: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reducedMotion) {
      setVisible(true)
      return
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      {
        rootMargin: '0px 0px -12% 0px',
        threshold: 0.16,
      }
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={`transform-gpu transition-all duration-700 ease-out motion-reduce:transition-none ${
        visible ? 'translate-y-0 opacity-100 blur-0' : 'translate-y-8 opacity-0 blur-[2px]'
      } ${className}`}
      style={{ transitionDelay: visible ? `${delayMs}ms` : '0ms' }}
    >
      {children}
    </div>
  )
}
