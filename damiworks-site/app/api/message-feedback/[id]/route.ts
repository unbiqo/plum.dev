import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

function fastApiUrl() {
  return process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const url = fastApiUrl()
  if (!url) return NextResponse.json({ error: 'FASTAPI_URL_not_configured' }, { status: 500 })

  const { id } = await params
  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'invalid_json' }, { status: 400 })
  }

  try {
    const res = await fetch(`${url}/api/v1/message-feedback/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'x-admin-token': req.headers.get('x-admin-token') ?? '',
      },
      body: JSON.stringify(body),
    })
    const data = await res.json().catch(() => ({}))
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'unreachable' }, { status: 503 })
  }
}
