'use client'

import { useState } from 'react'
import type { DictContact } from '@/lib/i18n'

export default function ContactSection({ dict }: { dict: DictContact }) {
  const [form, setForm] = useState({
    name: '',
    contact: '',
    businessType: '',
    message: '',
  })
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
  }

  const inputClass =
    'w-full bg-surface border border-border-col rounded-xl px-4 py-3 text-sm text-primary placeholder:text-secondary focus:outline-none focus:border-accent transition-colors'

  return (
    <section id="contact" className="scroll-mt-20 py-24 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">

          {/* Left */}
          <div>
            <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-4 whitespace-pre-line">
              {dict.headline}
            </h2>
            <p className="text-secondary mb-2">{dict.description}</p>
            <p className="text-sm text-secondary">{dict.note}</p>
          </div>

          {/* Right */}
          {submitted ? (
            <div className="bg-accent-soft border border-accent/20 rounded-2xl p-8 text-accent font-medium">
              {dict.successMessage}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <input
                  required
                  placeholder={dict.placeholderName}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={inputClass}
                />
                <input
                  required
                  placeholder={dict.placeholderContact}
                  value={form.contact}
                  onChange={(e) => setForm({ ...form, contact: e.target.value })}
                  className={inputClass}
                />
              </div>
              <select
                required
                value={form.businessType}
                onChange={(e) => setForm({ ...form, businessType: e.target.value })}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                <option value="">{dict.placeholderBusinessType}</option>
                {dict.businessTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <textarea
                rows={4}
                placeholder={dict.placeholderMessage}
                value={form.message}
                onChange={(e) => setForm({ ...form, message: e.target.value })}
                className={`${inputClass} resize-none`}
              />
              <button
                type="submit"
                className="w-full bg-accent text-white rounded-xl py-3 font-medium text-sm hover:opacity-90 transition-opacity"
              >
                {dict.submitButton}
              </button>
            </form>
          )}

        </div>
      </div>
    </section>
  )
}
