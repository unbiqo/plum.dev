import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
  const contentType = req.headers.get('content-type') ?? ''
  if (contentType.includes('multipart/form-data')) {
    return NextResponse.json({ error: 'multipart_not_supported' }, { status: 400 })
  }

  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'invalid_json' }, { status: 400 })
  }
  const { message, chat_id, chat_history, reset_context, intake_context, instance_id } =
    body as Record<string, unknown>

  if (typeof message !== 'string' || message.trim().length === 0)
    return NextResponse.json({ error: 'message_required' }, { status: 400 })
  if (message.length > 2000)
    return NextResponse.json({ error: 'message_too_long' }, { status: 400 })
  if (typeof chat_id !== 'string' || chat_id.trim().length === 0)
    return NextResponse.json({ error: 'chat_id_required' }, { status: 400 })
  if (chat_history !== undefined && !Array.isArray(chat_history))
    return NextResponse.json({ error: 'chat_history_invalid' }, { status: 400 })

  // Allowlist the instance: DamiWorks consultant (default), the Custom demo roleplay
  // instance, or the English school live demo. The backend separates behavior by instance_id.
  const ALLOWED_INSTANCES = ['damiworks_site', 'damiworks_custom_demo', 'damiworks_english_school_demo'] as const
  const resolvedInstanceId =
    typeof instance_id === 'string' && (ALLOWED_INSTANCES as readonly string[]).includes(instance_id)
      ? instance_id
      : 'damiworks_site'

  // Build effective history (intake context also kept here for conversational memory)
  const effectiveHistory: Array<{ role: string; content: string }> = []
  effectiveHistory.push(...((chat_history as Array<{ role: string; content: string }>) ?? []))

  // Build effective message: intake context is injected as a system instruction prefix.
  const hasIntakeCtx = typeof intake_context === 'string' && intake_context.trim().length > 0
  let effectiveMessage: string

  if (hasIntakeCtx) {
    effectiveMessage = `${(intake_context as string).trim()}\n\nCurrent user message:\n${(message as string).trim()}`
  } else {
    effectiveMessage = (message as string).trim()
  }

  // Production must set FASTAPI_URL; in dev, fall back to the local backend port.
  const fastApiUrl = process.env.FASTAPI_URL ?? (process.env.NODE_ENV === 'production' ? null : 'http://localhost:8010')
  if (!fastApiUrl) return NextResponse.json({ error: 'FASTAPI_URL_not_configured' }, { status: 500 })
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30_000)

  try {
    const res = await fetch(`${fastApiUrl}/api/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        channel: 'web_site',
        chat_id,
        instance_id: resolvedInstanceId,
        message: effectiveMessage,
        chat_history: effectiveHistory,
        reset_context: Boolean(reset_context),
        // Calendly booking CTA is visible in the UI — the backend uses this to
        // present booking a call as the preferred next step in contact asks.
        calendly_enabled: Boolean((process.env.NEXT_PUBLIC_CALENDLY_URL ?? '').trim()),
      }),
    })

    if (!res.ok) return NextResponse.json({ error: 'backend_error' }, { status: 502 })

    const data = (await res.json()) as {
      answer: string
      lead_status?: string | null
      lead_sent?: boolean
    }
    return NextResponse.json({
      answer: data.answer,
      lead_status: data.lead_status ?? null,
      lead_sent: Boolean(data.lead_sent),
    })
  } catch {
    return NextResponse.json({ error: 'unreachable' }, { status: 503 })
  } finally {
    clearTimeout(timeout)
  }
}
