import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

function fastApiUrl() {
  return process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ instanceId: string; chatId: string }> },
) {
  const url = fastApiUrl()
  if (!url) return NextResponse.json({ error: 'FASTAPI_URL_not_configured' }, { status: 500 })

  const { instanceId, chatId } = await params
  const target = `${url}/api/v1/quality/conversations/${encodeURIComponent(instanceId)}/${encodeURIComponent(chatId)}`

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
