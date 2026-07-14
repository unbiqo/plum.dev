// WhatsApp is a zero-friction CTA for the KZ market. The URL comes exclusively
// from NEXT_PUBLIC_WHATSAPP_URL (a wa.me link) — when it is missing or invalid,
// every WhatsApp CTA hides and the form / Calendly flow remains the only path.

export function resolveWhatsappUrl(raw: string | undefined | null): string | null {
  const url = (raw ?? '').trim()
  if (!url) return null
  if (!/^https?:\/\//i.test(url)) return null
  return url
}

// NEXT_PUBLIC_ vars are inlined at build time — the full literal reference is required.
export const WHATSAPP_URL = resolveWhatsappUrl(process.env.NEXT_PUBLIC_WHATSAPP_URL)
