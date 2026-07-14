'use client'

import { useEffect, useRef, useState } from 'react'

type StaggerRevealProps = {
  children: React.ReactNode
  className?: string
}

// Cascade-reveal counterpart of ScrollReveal: when the wrapper enters the
// viewport, children marked with data-stagger-item (and an inline --stagger-i
// index) fade in one after another. Styles live in globals.css; reduced-motion
// shows everything immediately.
export default function StaggerReveal({ children, className = '' }: StaggerRevealProps) {
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
        rootMargin: '0px 0px -10% 0px',
        threshold: 0.2,
      }
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={ref} className={`stagger ${visible ? 'stagger-visible' : ''} ${className}`}>
      {children}
    </div>
  )
}
