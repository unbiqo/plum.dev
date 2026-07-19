'use client'

import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'

// Floating mini-CTA: appears after ~40% of the page is scrolled, hides again
// while the contact form itself is on screen (no double CTA next to the form).
export default function StickyCta({ label }: { label: string }) {
  const [pastThreshold, setPastThreshold] = useState(false)
  const [contactVisible, setContactVisible] = useState(false)

  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const doc = document.documentElement
      const max = doc.scrollHeight - window.innerHeight
      setPastThreshold(max > 0 && window.scrollY / max >= 0.4)
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })

    const contact = document.getElementById('contact')
    let observer: IntersectionObserver | null = null
    if (contact) {
      observer = new IntersectionObserver(([entry]) => setContactVisible(entry.isIntersecting), {
        rootMargin: '0px 0px -20% 0px',
      })
      observer.observe(contact)
    }

    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
      observer?.disconnect()
    }
  }, [])

  const visible = pastThreshold && !contactVisible

  return (
    <div
      className={`fixed bottom-4 left-0 right-0 z-40 flex justify-center px-4 transition-all duration-300 motion-reduce:transition-none sm:left-auto sm:right-6 sm:justify-end sm:px-0 ${
        visible ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-4 opacity-0'
      }`}
      aria-hidden={!visible}
    >
      <a
        href="#contact"
        tabIndex={visible ? 0 : -1}
        className="inline-flex min-h-12 items-center gap-2 rounded-full bg-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent/25 transition-opacity hover:opacity-90"
      >
        {label}
        <ArrowRight size={15} aria-hidden="true" />
      </a>
    </div>
  )
}
