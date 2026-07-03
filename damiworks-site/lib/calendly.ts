// Calendly is the primary conversion CTA. The URL comes exclusively from
// NEXT_PUBLIC_CALENDLY_URL — when it is missing or invalid, every Calendly CTA
// hides and the existing contact form / chat contact flow remains the only path.

export function resolveCalendlyUrl(raw: string | undefined | null): string | null {
  const url = (raw ?? '').trim()
  if (!url) return null
  if (!/^https?:\/\//i.test(url)) return null
  return url
}

// NEXT_PUBLIC_ vars are inlined at build time — the full literal reference is required.
export const CALENDLY_URL = resolveCalendlyUrl(process.env.NEXT_PUBLIC_CALENDLY_URL)
