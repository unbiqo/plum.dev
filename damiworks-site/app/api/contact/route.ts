import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'invalid_json' }, { status: 400 })
  }

  const { name, contact, businessType, message } = body as {
    name?: string
    contact?: string
    businessType?: string
    message?: string
  }

  if (!name?.trim() || !contact?.trim()) {
    return NextResponse.json({ error: 'name_and_contact_required' }, { status: 400 })
  }

  const fastApiUrl = process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
  if (!fastApiUrl) {
    console.error('[contact] FASTAPI_URL is not configured')
    return NextResponse.json({ error: 'contact_service_not_configured' }, { status: 503 })
  }

  try {
    const upstream = await fetch(`${fastApiUrl}/api/v1/contact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        contact: contact.trim(),
        business_type: businessType ?? null,
        message: message ?? null,
      }),
    })
    if (!upstream.ok) {
      console.error('[contact] backend rejected request status=%s', upstream.status)
      return NextResponse.json({ error: 'contact_delivery_failed' }, { status: 502 })
    }
  } catch {
    console.error('[contact] backend is unreachable')
    return NextResponse.json({ error: 'contact_service_unreachable' }, { status: 503 })
  }

  return NextResponse.json({ ok: true })
}
