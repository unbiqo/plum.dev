import { NextRequest, NextResponse } from 'next/server'
import { type LeadSummary } from '@/lib/intake'

export const runtime = 'nodejs'

// Lead lifecycle is owned by the backend (Supabase + owner Telegram notification).
// This route forwards the intake-completion "created" signal to FastAPI; the chat
// endpoint itself handles the contact-collected update. (The old formatLeadMessage
// + direct Telegram send in lib/intake.ts is kept but no longer called.)
export async function POST(req: NextRequest) {
  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'invalid_json' }, { status: 400 })
  }

  const lead = body as LeadSummary
  if (!lead?.chat_id || typeof lead.chat_id !== 'string') {
    return NextResponse.json({ error: 'chat_id_required' }, { status: 400 })
  }

  const fastApiUrl = process.env.FASTAPI_URL ?? 'http://localhost:8000'
  const payload = {
    chat_id: lead.chat_id,
    instance_id: 'damiworks_site',
    interest_level: lead.interest_level,
    business_type: lead.business_type,
    channels: lead.channels ?? [],
    tasks: lead.tasks ?? [],
    handoff_target: lead.handoff,
    volume: lead.volume,
    timeline: lead.timeline,
    package_recommended: lead.recommended_package,
    estimated_setup_price: lead.estimated_price,
    summary: lead.conversation_summary,
    transcript: (lead.last_messages ?? []).map((m) => ({ role: m.role, content: m.content })),
  }

  try {
    await fetch(`${fastApiUrl}/api/v1/lead`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    // Never surface lead delivery errors to the browser.
    console.error('[lead] forward to backend failed for chat_id:', lead.chat_id)
  }

  return NextResponse.json({ ok: true })
}
