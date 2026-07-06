import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

function fastApiUrl() {
  return process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
}

export async function GET(req: NextRequest) {
  const url = fastApiUrl()
  if (!url) return NextResponse.json({ error: 'FASTAPI_URL_not_configured' }, { status: 500 })

  const target = new URL(`${url}/api/v1/quality/conversations`)
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
