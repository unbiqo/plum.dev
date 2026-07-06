import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

function fastApiUrl() {
  return process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
}

export async function POST(req: NextRequest) {
  const url = fastApiUrl()
  if (!url) return NextResponse.json({ error: 'FASTAPI_URL_not_configured' }, { status: 500 })

  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'invalid_json' }, { status: 400 })
  }

  try {
    const res = await fetch(`${url}/api/v1/message-feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json().catch(() => ({}))
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'unreachable' }, { status: 503 })
  }
}

export async function GET(req: NextRequest) {
  const url = fastApiUrl()
  if (!url) return NextResponse.json({ error: 'FASTAPI_URL_not_configured' }, { status: 500 })

  const target = new URL(`${url}/api/v1/message-feedback`)
  req.nextUrl.searchParams.forEach((value, key) => {
    if (value) target.searchParams.set(key, value)
  })

  try {
    const res = await fetch(target, {
      headers: { 'x-admin-token': req.headers.get('x-admin-token') ?? '' },
    })
    const data = await res.json().catch(() => ({}))
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'unreachable' }, { status: 503 })
  }
}
