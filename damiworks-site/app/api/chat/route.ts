import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'
// The English School demo turn can take three sequential LLM calls (planner +
// writer + repair) before its safe fallback; give the proxy enough headroom so
// a slow-but-successful backend answer is never turned into a generic error.
export const maxDuration = 60

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
  const {
    message,
    chat_id,
    chat_history,
    reset_context,
    intake_context,
    instance_id,
    message_id,
    response_message_id,
    locale,
    source,
  } =
    body as Record<string, unknown>

  if (typeof message !== 'string' || message.trim().length === 0)
    return NextResponse.json({ error: 'message_required' }, { status: 400 })
  if (message.length > 2000)
    return NextResponse.json({ error: 'message_too_long' }, { status: 400 })
  if (typeof chat_id !== 'string' || chat_id.trim().length === 0)
    return NextResponse.json({ error: 'chat_id_required' }, { status: 400 })
  if (chat_history !== undefined && !Array.isArray(chat_history))
    return NextResponse.json({ error: 'chat_history_invalid' }, { status: 400 })

  // Allowlist the instance: DamiWorks consultant (default), the Custom demo roleplay,
  // English school, or medical center live demos. The backend separates behavior by instance_id.
  const ALLOWED_INSTANCES = [
    'damiworks_site',
    'damiworks_custom_demo',
    'damiworks_english_school_demo',
    'damiworks_medical_center_demo',
  ] as const
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
  const timeout = setTimeout(() => controller.abort(), 55_000)

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
        message_id: typeof message_id === 'string' ? message_id : undefined,
        response_message_id: typeof response_message_id === 'string' ? response_message_id : undefined,
        locale: typeof locale === 'string' ? locale : undefined,
        source: typeof source === 'string' ? source : 'web_chat',
        chat_history: effectiveHistory,
        reset_context: Boolean(reset_context),
        // Calendly booking CTA is visible in the UI — the backend uses this to
        // present booking a call as the preferred next step in contact asks.
        calendly_enabled: Boolean((process.env.NEXT_PUBLIC_CALENDLY_URL ?? '').trim()),
      }),
    })

    // The backend answers 200 with a safe assistant message even when an LLM
    // substep failed. Prefer any assistant message in the body over the generic
    // UI error: a real sentence beats "Что-то пошло не так". request_id, when
    // present, is logged so a user report can be traced to the backend line.
    const data = (await res.json().catch(() => null)) as {
      answer?: string
      answer_parts?: string[] | null
      lead_status?: string | null
      lead_sent?: boolean
      metadata?: Record<string, unknown> | null
    } | null

    if (!data?.answer) {
      const requestId = data?.metadata?.request_id
      console.error('chat backend_error status=%s request_id=%s', res.status, requestId ?? 'none')
      return NextResponse.json({ error: 'backend_error' }, { status: 502 })
    }

    // Multi-bubble contract is additive: forward parts only when the backend
    // produced more than one; older backends simply omit the field.
    const answerParts = Array.isArray(data.answer_parts)
      ? data.answer_parts.filter((p): p is string => typeof p === 'string' && p.trim().length > 0)
      : []

    return NextResponse.json({
      answer: data.answer,
      answer_parts: answerParts.length > 1 ? answerParts : null,
      lead_status: data.lead_status ?? null,
      lead_sent: Boolean(data.lead_sent),
      metadata: data.metadata ?? null,
    })
  } catch (err) {
    // AbortError means we hit the 55s budget. The backend now bounds its own
    // model-pool walk well inside that, so an abort is a genuine outage rather
    // than one slow model.
    const aborted = err instanceof Error && err.name === 'AbortError'
    console.error('chat proxy failed aborted=%s', aborted)
    return NextResponse.json({ error: aborted ? 'timeout' : 'unreachable' }, { status: 503 })
  } finally {
    clearTimeout(timeout)
  }
}
