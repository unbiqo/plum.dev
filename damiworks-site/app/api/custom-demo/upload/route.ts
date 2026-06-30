import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

const CUSTOM_DEMO_INSTANCE_ID = 'damiworks_custom_demo'

export async function POST(req: NextRequest) {
  let formData: FormData
  try {
    formData = await req.formData()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid_form' }, { status: 400 })
  }

  const file = formData.get('file')
  const chatId = formData.get('chat_id')
  const instanceId = formData.get('instance_id')

  if (!(file instanceof File) || file.size <= 0) {
    return NextResponse.json({ ok: false, error: 'file_required' }, { status: 400 })
  }
  if (typeof chatId !== 'string' || chatId.trim().length === 0) {
    return NextResponse.json({ ok: false, error: 'chat_id_required' }, { status: 400 })
  }
  if (instanceId !== CUSTOM_DEMO_INSTANCE_ID) {
    return NextResponse.json({ ok: false, error: 'unsupported_instance' }, { status: 400 })
  }

  const outbound = new FormData()
  outbound.append('file', file, file.name)
  outbound.append('chat_id', chatId)
  outbound.append('instance_id', CUSTOM_DEMO_INSTANCE_ID)

  const fastApiUrl = process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30_000)

  try {
    const res = await fetch(`${fastApiUrl}/api/v1/custom-demo/documents`, {
      method: 'POST',
      body: outbound,
      signal: controller.signal,
    })
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ ok: false, error: 'unreachable' }, { status: 503 })
  } finally {
    clearTimeout(timeout)
  }
}
