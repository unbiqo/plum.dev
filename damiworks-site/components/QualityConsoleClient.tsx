'use client'

import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { CheckCircle2, LogOut, MessageSquareText, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import {
  QUALITY_ISSUE_TYPES,
  QUALITY_RATINGS,
  QUALITY_SEVERITIES,
  QUALITY_STATUSES,
  buildConversationQuery,
  buildMessageReviewPayload,
  issueLabel,
  type QualityIssueType,
  type QualityRating,
  type QualitySeverity,
  type QualityStatus,
} from '@/lib/qualityFeedback'

type FeedbackItem = {
  id: string
  created_at?: string
  updated_at?: string
  instance_id: string
  chat_id: string
  message_id: string
  rating: QualityRating | string
  issue_type: string
  severity: QualitySeverity | string
  status: QualityStatus
  user_message?: string | null
  assistant_answer: string
  corrected_answer?: string | null
  comment?: string | null
  reviewer_note?: string | null
  transcript_json?: Array<{ role?: string; content?: string; message_id?: string }>
  metadata?: Record<string, unknown>
}

type Conversation = {
  id?: string
  created_at?: string
  updated_at?: string
  last_message_at?: string
  instance_id: string
  chat_id: string
  channel?: string | null
  source?: string | null
  status?: string | null
  lead_status?: string | null
  message_count?: number
  feedback_count?: number
  last_user_message?: string | null
  last_assistant_message?: string | null
  metadata?: Record<string, unknown>
  conversation_cost_summary?: ConversationCostSummary
}

type ConversationMessage = {
  id?: string
  created_at?: string
  instance_id: string
  chat_id: string
  message_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  feedback?: FeedbackItem[]
  feedback_count?: number
}

type ConversationDetail = {
  conversation: Conversation
  messages: ConversationMessage[]
  feedback: FeedbackItem[]
  conversation_cost?: ConversationCost
}

type ConversationCostSummary = {
  total_input_tokens?: number
  total_output_tokens?: number
  total_tokens?: number
  total_cost_usd?: number | null
  has_estimated_usage?: boolean
  has_missing_pricing?: boolean
  llm_call_count?: number
  fallback_count?: number
  escalation_count?: number
  model_count?: number
  slowest_call_ms?: number
}

type CostGroup = {
  model?: string
  task_type?: string
  model_profile?: string
  calls?: number
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  cost_usd?: number | null
  pricing_missing?: boolean
  estimated?: boolean
}

type LlmCall = {
  created_at?: string
  task_type?: string
  model_profile?: string | null
  selected_model?: string | null
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  total_cost_usd?: number | null
  pricing_missing?: boolean
  estimated?: boolean
  latency_ms?: number
  fallback_used?: boolean
  escalation_used?: boolean
  success?: boolean
}

type ConversationCost = ConversationCostSummary & {
  estimated_cost_usd?: number
  by_model?: CostGroup[]
  by_task?: CostGroup[]
  calls?: LlmCall[]
}

type ConversationFilters = {
  instance_id: string
  chat_id: string
  lead_status: string
  has_feedback: string
  date_from: string
  date_to: string
}

const EMPTY_FILTERS: ConversationFilters = {
  instance_id: '',
  chat_id: '',
  lead_status: '',
  has_feedback: '',
  date_from: '',
  date_to: '',
}

const AGENT_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: '', label: 'All agents' },
  { value: 'damiworks_site', label: 'DamiWorks Site (Sales Consultant)' },
  { value: 'damiworks_custom_demo', label: 'Custom Demo' },
  { value: 'damiworks_english_school_demo', label: 'English School Demo' },
  { value: 'damiworks_medical_center_demo', label: 'MedNova Clinic (Medical Center)' },
]

function formatDate(value?: string): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function shortId(value: string): string {
  return value.length > 20 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value
}

function statusTone(status?: string | null): string {
  if (status === 'fixed' || status === 'added_to_evals') return 'bg-green-500/10 text-green-600 border-green-500/20'
  if (status === 'ignored') return 'bg-secondary/10 text-secondary border-border-col'
  if (status === 'open') return 'bg-red-500/10 text-red-500 border-red-500/20'
  return 'bg-accent-soft text-accent border-accent/20'
}

function formatUsd(value?: number | null): string {
  if (value === null || value === undefined) return 'pricing missing'
  return `$${value.toFixed(6)}`
}

function formatNumber(value?: number | null): string {
  return typeof value === 'number' ? value.toLocaleString() : '0'
}

export default function QualityConsoleClient() {
  const [adminToken, setAdminToken] = useState('')
  const [signedIn, setSignedIn] = useState(false)
  const [activeTab, setActiveTab] = useState<'conversations' | 'feedback'>('conversations')
  const [filters, setFilters] = useState<ConversationFilters>(EMPTY_FILTERS)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [feedbackItems, setFeedbackItems] = useState<FeedbackItem[]>([])
  const [selected, setSelected] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const stored = sessionStorage.getItem('quality_console_admin_token')
    if (stored !== null) {
      setAdminToken(stored)
      setSignedIn(true)
    }
  }, [])

  const stats = useMemo(() => {
    const open = feedbackItems.filter((item) => item.status === 'open').length
    const critical = feedbackItems.filter((item) => item.severity === 'critical').length
    const fixed = feedbackItems.filter((item) => item.status === 'fixed' || item.status === 'added_to_evals').length
    return {
      conversations: conversations.length,
      open,
      critical,
      fixed,
    }
  }, [conversations, feedbackItems])

  const signIn = async () => {
    sessionStorage.setItem('quality_console_admin_token', adminToken)
    setSignedIn(true)
    await loadAll()
  }

  const signOut = () => {
    sessionStorage.removeItem('quality_console_admin_token')
    setAdminToken('')
    setSignedIn(false)
    setConversations([])
    setFeedbackItems([])
    setSelected(null)
  }

  const authHeaders = () => ({ 'x-admin-token': adminToken })

  const loadConversations = async (f: ConversationFilters = filters) => {
    const qs = buildConversationQuery({
      ...f,
      limit: 200,
      offset: 0,
    })
    const res = await fetch(`/api/quality/conversations?${qs}`, { headers: authHeaders() })
    if (res.status === 401) throw new Error('Admin token is invalid.')
    if (!res.ok) throw new Error('Could not load conversations.')
    const data = (await res.json()) as { items?: Conversation[] }
    const items = data.items ?? []
    setConversations(items)
    if (items[0] && !items.some((item) => item.instance_id === selected?.conversation.instance_id && item.chat_id === selected?.conversation.chat_id)) {
      await loadConversationDetail(items[0].instance_id, items[0].chat_id)
    }
  }

  const loadFeedback = async (f: ConversationFilters = filters) => {
    const qs = new URLSearchParams()
    qs.set('limit', '200')
    if (f.instance_id) qs.set('instance_id', f.instance_id)
    if (f.chat_id) qs.set('chat_id', f.chat_id)
    const res = await fetch(`/api/quality-feedback?${qs.toString()}`, { headers: authHeaders() })
    if (res.status === 401) throw new Error('Admin token is invalid.')
    if (!res.ok) throw new Error('Could not load feedback queue.')
    const data = (await res.json()) as { items?: FeedbackItem[] }
    setFeedbackItems(data.items ?? [])
  }

  const loadAll = async (f: ConversationFilters = filters) => {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([loadConversations(f), loadFeedback(f)])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load quality data.')
    } finally {
      setLoading(false)
    }
  }

  const selectAgent = (instanceId: string) => {
    const next = { ...filters, instance_id: instanceId }
    setFilters(next)
    void loadAll(next)
  }

  const loadConversationDetail = async (instanceId: string, chatId: string) => {
    setDetailLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `/api/quality/conversations/${encodeURIComponent(instanceId)}/${encodeURIComponent(chatId)}`,
        { headers: authHeaders() },
      )
      if (res.status === 401) throw new Error('Admin token is invalid.')
      if (!res.ok) throw new Error('Could not load conversation.')
      setSelected((await res.json()) as ConversationDetail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load conversation.')
    } finally {
      setDetailLoading(false)
    }
  }

  const saveFeedback = async (
    message: ConversationMessage,
    values: {
      id?: string
      rating: QualityRating
      issue_type: QualityIssueType | string
      severity: QualitySeverity
      status: QualityStatus
      comment: string
      corrected_answer: string
      reviewer_note: string
    },
  ) => {
    const existingId = values.id
    const payload = {
      rating: values.rating,
      issue_type: values.issue_type,
      severity: values.severity,
      status: values.status,
      comment: values.comment,
      corrected_answer: values.corrected_answer,
      reviewer_note: values.reviewer_note,
    }

    if (existingId) {
      const res = await fetch(`/api/quality-feedback/${encodeURIComponent(existingId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Could not update feedback.')
    } else if (selected) {
      const transcript = selected.messages.map((m) => ({
        role: m.role,
        content: m.content,
        message_id: m.message_id,
      }))
      const previousUser = [...selected.messages]
        .reverse()
        .find((m) => m.role === 'user' && new Date(m.created_at ?? 0) <= new Date(message.created_at ?? 0))
      const res = await fetch('/api/quality-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(
          buildMessageReviewPayload({
            instance_id: message.instance_id,
            chat_id: message.chat_id,
            message_id: message.message_id,
            rating: values.rating,
            issue_type: values.issue_type,
            severity: values.severity,
            status: values.status,
            user_message: previousUser?.content ?? null,
            assistant_answer: message.content,
            corrected_answer: values.corrected_answer,
            comment: values.comment,
            reviewer_note: values.reviewer_note,
            transcript_json: transcript,
            metadata: { submitted_from: 'conversation_review_console' },
          }),
        ),
      })
      if (!res.ok) throw new Error('Could not create feedback.')
    }

    await Promise.all([
      loadConversationDetail(message.instance_id, message.chat_id),
      loadFeedback(),
    ])
  }

  if (!signedIn) {
    return (
      <main className="min-h-screen bg-bg px-6 py-12 text-primary">
        <div className="mx-auto flex min-h-[70vh] max-w-md items-center">
          <div className="w-full rounded-2xl border border-border-col bg-surface p-7 shadow-sm">
            <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent">
              <ShieldCheck size={22} />
            </div>
            <h1 className="text-2xl font-semibold">AI Quality Console</h1>
            <p className="mt-2 text-sm leading-relaxed text-secondary">
              Review conversations and improve AI employees by instance.
            </p>
            <label className="mt-6 block text-sm font-medium text-primary">
              Admin token
              <input
                value={adminToken}
                onChange={(e) => setAdminToken(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void signIn()
                }}
                type="password"
                className="mt-2 w-full rounded-xl border border-border-col bg-bg px-4 py-3 text-sm outline-none focus:border-accent"
                placeholder="Enter internal review token"
              />
            </label>
            <button
              onClick={() => void signIn()}
              className="mt-4 w-full rounded-xl bg-accent px-4 py-3 text-sm font-medium text-white"
            >
              Open console
            </button>
            <p className="mt-3 text-xs text-secondary">
              Local environments may allow an empty token if the backend token is not configured.
            </p>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-bg text-primary">
      <div className="border-b border-border-col bg-surface">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold">AI Quality Console</h1>
            <p className="mt-1 text-sm text-secondary">
              Conversation review and message-level feedback across every instance_id.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => void loadAll()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-border-col px-3 py-2 text-sm text-secondary hover:text-primary disabled:opacity-50"
            >
              <RefreshCw size={15} /> Refresh
            </button>
            <button
              onClick={signOut}
              className="inline-flex items-center gap-2 rounded-xl border border-border-col px-3 py-2 text-sm text-secondary hover:text-primary"
            >
              <LogOut size={15} /> Sign out
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-6">
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Conversations" value={stats.conversations} />
          <StatCard label="Open feedback" value={stats.open} tone="red" />
          <StatCard label="Critical issues" value={stats.critical} tone="yellow" />
          <StatCard label="Fixed / evals" value={stats.fixed} tone="green" />
        </section>

        <section className="mt-5 rounded-2xl border border-border-col bg-surface p-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3 lg:grid-cols-6">
            <FilterInput label="Instance ID" value={filters.instance_id} onChange={(v) => setFilters((f) => ({ ...f, instance_id: v }))} />
            <FilterInput label="Chat ID" value={filters.chat_id} onChange={(v) => setFilters((f) => ({ ...f, chat_id: v }))} />
            <FilterInput label="Lead status" value={filters.lead_status} onChange={(v) => setFilters((f) => ({ ...f, lead_status: v }))} />
            <label className="text-xs font-medium text-secondary">
              Has feedback
              <select
                value={filters.has_feedback}
                onChange={(e) => setFilters((f) => ({ ...f, has_feedback: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-border-col bg-bg px-3 py-2 text-sm text-primary"
              >
                <option value="">Any</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <FilterInput label="From" type="date" value={filters.date_from} onChange={(v) => setFilters((f) => ({ ...f, date_from: v }))} />
            <FilterInput label="To" type="date" value={filters.date_to} onChange={(v) => setFilters((f) => ({ ...f, date_to: v }))} />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={() => void loadAll()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              <Search size={15} /> Apply filters
            </button>
            <button
              onClick={() => setFilters(EMPTY_FILTERS)}
              className="rounded-xl border border-border-col px-4 py-2 text-sm text-secondary hover:text-primary"
            >
              Clear
            </button>
            {error && <span className="text-sm text-red-500">{error}</span>}
          </div>
        </section>

        <div className="mt-5 flex gap-2">
          <TabButton active={activeTab === 'conversations'} onClick={() => setActiveTab('conversations')}>
            Conversations
          </TabButton>
          <TabButton active={activeTab === 'feedback'} onClick={() => setActiveTab('feedback')}>
            Feedback Queue
          </TabButton>
        </div>

        {activeTab === 'conversations' ? (
          <div className="mt-4 grid grid-cols-1 gap-5 xl:grid-cols-[430px_1fr]">
            <ConversationList
              conversations={conversations}
              selected={selected?.conversation ?? null}
              loading={loading}
              agent={filters.instance_id}
              onAgentChange={selectAgent}
              onSelect={(conversation) => void loadConversationDetail(conversation.instance_id, conversation.chat_id)}
            />
            <ConversationDetailPanel
              detail={selected}
              loading={detailLoading}
              onSaveFeedback={saveFeedback}
            />
          </div>
        ) : (
          <FeedbackQueue items={feedbackItems} onOpenConversation={(item) => {
            setActiveTab('conversations')
            void loadConversationDetail(item.instance_id, item.chat_id)
          }} />
        )}
      </div>
    </main>
  )
}

function StatCard({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'red' | 'yellow' | 'green' }) {
  const toneClass =
    tone === 'red' ? 'text-red-500' : tone === 'yellow' ? 'text-yellow-600' : tone === 'green' ? 'text-green-600' : 'text-primary'
  return (
    <div className="rounded-2xl border border-border-col bg-surface p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-secondary">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  )
}

function FilterInput({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="text-xs font-medium text-secondary">
      {label}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        type={type}
        className="mt-1 w-full rounded-xl border border-border-col bg-bg px-3 py-2 text-sm text-primary outline-none focus:border-accent"
      />
    </label>
  )
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl px-4 py-2 text-sm font-medium ${active ? 'bg-accent-soft text-accent' : 'text-secondary hover:bg-surface hover:text-primary'}`}
    >
      {children}
    </button>
  )
}

function ConversationList({
  conversations,
  selected,
  loading,
  agent,
  onAgentChange,
  onSelect,
}: {
  conversations: Conversation[]
  selected: Conversation | null
  loading: boolean
  agent: string
  onAgentChange: (agent: string) => void
  onSelect: (conversation: Conversation) => void
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-border-col bg-surface">
      <div className="border-b border-border-col px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">Conversations</div>
          <div className="text-xs text-secondary">{loading ? 'Loading...' : `${conversations.length} shown`}</div>
        </div>
        <label className="mt-2 block text-xs font-medium text-secondary">
          AI agent
          <select
            value={agent}
            onChange={(e) => onAgentChange(e.target.value)}
            className="mt-1 w-full rounded-xl border border-border-col bg-bg px-3 py-2 text-sm text-primary"
          >
            {AGENT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="max-h-[720px] overflow-y-auto">
        {conversations.map((conversation) => (
          <button
            key={`${conversation.instance_id}:${conversation.chat_id}`}
            onClick={() => onSelect(conversation)}
            className={`block w-full border-b border-border-col px-4 py-3 text-left transition-colors hover:bg-bg ${
              selected?.instance_id === conversation.instance_id && selected?.chat_id === conversation.chat_id ? 'bg-bg' : ''
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="truncate text-xs font-semibold text-accent">{conversation.instance_id}</span>
              <span className="text-[11px] text-secondary">{formatDate(conversation.last_message_at)}</span>
            </div>
            <div className="mt-1 font-mono text-[11px] text-secondary">chat_id: {shortId(conversation.chat_id)}</div>
            <div className="mt-2 line-clamp-2 text-sm text-primary">
              {conversation.last_user_message || conversation.last_assistant_message || 'No messages captured yet.'}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
              <span className="rounded-full border border-border-col bg-bg px-2 py-0.5">{conversation.message_count ?? 0} messages</span>
              <span className={`rounded-full border px-2 py-0.5 ${conversation.feedback_count ? 'border-red-500/20 bg-red-500/10 text-red-500' : 'border-border-col bg-bg text-secondary'}`}>
                {conversation.feedback_count ?? 0} feedback
              </span>
              {conversation.lead_status && <span className="rounded-full border border-border-col bg-bg px-2 py-0.5">{conversation.lead_status}</span>}
              {conversation.conversation_cost_summary && (
                <span className="rounded-full border border-border-col bg-bg px-2 py-0.5">
                  {formatUsd(conversation.conversation_cost_summary.total_cost_usd)}
                </span>
              )}
            </div>
          </button>
        ))}
        {conversations.length === 0 && (
          <div className="px-4 py-10 text-sm text-secondary">No conversations match the current filters.</div>
        )}
      </div>
    </section>
  )
}

function ConversationDetailPanel({
  detail,
  loading,
  onSaveFeedback,
}: {
  detail: ConversationDetail | null
  loading: boolean
  onSaveFeedback: Parameters<typeof ConversationMessageRow>[0]['onSaveFeedback']
}) {
  if (loading) {
    return <section className="rounded-2xl border border-border-col bg-surface p-6 text-sm text-secondary">Loading conversation...</section>
  }
  if (!detail) {
    return (
      <section className="rounded-2xl border border-border-col bg-surface p-10 text-center text-sm text-secondary">
        Select a conversation to review the full message timeline.
      </section>
    )
  }
  const c = detail.conversation
  return (
    <section className="overflow-hidden rounded-2xl border border-border-col bg-surface">
      <div className="border-b border-border-col px-5 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-wider text-secondary">Conversation</div>
            <div className="mt-1 font-mono text-sm text-primary">{c.instance_id}</div>
            <div className="mt-1 font-mono text-xs text-secondary">chat_id: {c.chat_id}</div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs text-secondary lg:text-right">
            <div>Created<br /><span className="text-primary">{formatDate(c.created_at)}</span></div>
            <div>Last message<br /><span className="text-primary">{formatDate(c.last_message_at)}</span></div>
            <div>Lead status<br /><span className="text-primary">{c.lead_status || '—'}</span></div>
            <div>Feedback<br /><span className="text-primary">{c.feedback_count ?? 0}</span></div>
          </div>
        </div>
      </div>
      <CostTokensPanel cost={detail.conversation_cost ?? c.conversation_cost_summary ?? null} />
      <div className="max-h-[760px] space-y-4 overflow-y-auto bg-bg/40 px-5 py-5">
        {detail.messages.map((message) => (
          <ConversationMessageRow
            key={message.message_id}
            message={message}
            detail={detail}
            onSaveFeedback={onSaveFeedback}
          />
        ))}
      </div>
    </section>
  )
}

function CostTokensPanel({ cost }: { cost: ConversationCost | ConversationCostSummary | null }) {
  const [open, setOpen] = useState(false)
  if (!cost || !cost.llm_call_count) {
    return (
      <div className="border-b border-border-col bg-surface px-5 py-3 text-xs text-secondary">
        Cost / Tokens: no LLM calls recorded for this conversation yet.
      </div>
    )
  }
  const full = cost as ConversationCost
  const byModel = full.by_model ?? []
  const byTask = full.by_task ?? []
  const calls = full.calls ?? []
  return (
    <div className="border-b border-border-col bg-surface px-5 py-4">
      <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-6">
        <CostMetric label="Total cost" value={formatUsd(cost.total_cost_usd)} />
        <CostMetric label="Tokens" value={`${formatNumber(cost.total_input_tokens)} / ${formatNumber(cost.total_output_tokens)} / ${formatNumber(cost.total_tokens)}`} />
        <CostMetric label="LLM calls" value={formatNumber(cost.llm_call_count)} />
        <CostMetric label="Fallbacks" value={formatNumber(cost.fallback_count)} />
        <CostMetric label="Escalations" value={formatNumber(cost.escalation_count)} />
        <CostMetric label="Flags" value={`${cost.has_estimated_usage ? 'estimated' : 'real'}${cost.has_missing_pricing ? ' / pricing missing' : ''}`} />
      </div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="mt-3 rounded-xl border border-border-col px-3 py-2 text-xs text-secondary hover:text-primary"
      >
        {open ? 'Hide' : 'Show'} Cost / Tokens breakdown
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          <CostTable
            title="By model"
            columns={['Model', 'Calls', 'Input', 'Output', 'Cost']}
            rows={byModel.map((row) => [
              row.model ?? 'unknown',
              formatNumber(row.calls),
              formatNumber(row.input_tokens),
              formatNumber(row.output_tokens),
              row.pricing_missing ? 'pricing missing' : formatUsd(row.cost_usd),
            ])}
          />
          <CostTable
            title="By task"
            columns={['Task', 'Profile', 'Model', 'Calls', 'Tokens', 'Cost']}
            rows={byTask.map((row) => [
              row.task_type ?? 'unknown',
              row.model_profile ?? 'unknown',
              row.model ?? 'unknown',
              formatNumber(row.calls),
              formatNumber(row.total_tokens),
              row.pricing_missing ? 'pricing missing' : formatUsd(row.cost_usd),
            ])}
          />
          <CostTable
            title="Detailed calls"
            columns={['Time', 'Task', 'Model', 'Input', 'Output', 'Cost', 'Latency', 'Fallback']}
            rows={calls.map((call) => [
              formatDate(call.created_at),
              call.task_type ?? 'unknown',
              call.selected_model ?? 'unknown',
              `${formatNumber(call.input_tokens)}${call.estimated ? ' est.' : ''}`,
              formatNumber(call.output_tokens),
              call.pricing_missing ? 'pricing missing' : formatUsd(call.total_cost_usd),
              `${formatNumber(call.latency_ms)} ms`,
              call.fallback_used ? 'yes' : 'no',
            ])}
          />
        </div>
      )}
    </div>
  )
}

function CostMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border-col bg-bg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-secondary">{label}</div>
      <div className="mt-1 truncate font-mono text-xs text-primary">{value}</div>
    </div>
  )
}

function CostTable({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold text-primary">{title}</div>
      <div className="overflow-x-auto rounded-xl border border-border-col">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-bg text-secondary">
            <tr>
              {columns.map((column) => (
                <th key={column} className="whitespace-nowrap px-3 py-2 font-medium">{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border-col">
            {rows.length ? rows.map((row, index) => (
              <tr key={`${title}-${index}`} className="bg-surface">
                {row.map((cell, cellIndex) => (
                  <td key={`${title}-${index}-${cellIndex}`} className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-primary">{cell}</td>
                ))}
              </tr>
            )) : (
              <tr><td colSpan={columns.length} className="px-3 py-4 text-secondary">No rows.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ConversationMessageRow({
  message,
  detail,
  onSaveFeedback,
}: {
  message: ConversationMessage
  detail: ConversationDetail
  onSaveFeedback: (
    message: ConversationMessage,
    values: {
      id?: string
      rating: QualityRating
      issue_type: QualityIssueType | string
      severity: QualitySeverity
      status: QualityStatus
      comment: string
      corrected_answer: string
      reviewer_note: string
    },
  ) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const feedback = message.feedback?.[0]
  const isAssistant = message.role === 'assistant'
  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`group relative max-w-[82%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
        <div className={`rounded-2xl border px-4 py-3 text-sm leading-relaxed shadow-sm ${
          message.role === 'user'
            ? 'border-accent/20 bg-accent-soft text-primary'
            : 'border-border-col bg-surface text-primary'
        }`}>
          <div className="mb-1 flex items-center justify-between gap-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-secondary">{message.role} | {shortId(message.message_id)}</span>
            {feedback && <span className={`rounded-full border px-2 py-0.5 text-[10px] ${statusTone(feedback.status)}`}>{feedback.status}</span>}
          </div>
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
        {isAssistant && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="mt-1 inline-flex items-center gap-1 rounded-lg border border-border-col bg-bg px-2 py-1 text-[11px] text-secondary hover:text-primary"
          >
            <MessageSquareText size={12} /> {feedback ? 'Edit review' : 'Review'}
          </button>
        )}
        {open && isAssistant && (
          <ReviewForm
            message={message}
            feedback={feedback}
            onSave={async (values) => {
              await onSaveFeedback(message, values)
              setOpen(false)
            }}
          />
        )}
      </div>
    </div>
  )
}

function ReviewForm({
  message,
  feedback,
  onSave,
}: {
  message: ConversationMessage
  feedback?: FeedbackItem
  onSave: (values: {
    id?: string
    rating: QualityRating
    issue_type: QualityIssueType | string
    severity: QualitySeverity
    status: QualityStatus
    comment: string
    corrected_answer: string
    reviewer_note: string
  }) => Promise<void>
}) {
  const [rating, setRating] = useState<QualityRating>((feedback?.rating as QualityRating) || 'negative')
  const [issueType, setIssueType] = useState<QualityIssueType | string>(feedback?.issue_type || 'other')
  const [severity, setSeverity] = useState<QualitySeverity>((feedback?.severity as QualitySeverity) || 'medium')
  const [status, setStatus] = useState<QualityStatus>(feedback?.status || 'open')
  const [comment, setComment] = useState(feedback?.comment || '')
  const [correctedAnswer, setCorrectedAnswer] = useState(feedback?.corrected_answer || '')
  const [reviewerNote, setReviewerNote] = useState(feedback?.reviewer_note || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async (nextStatus?: QualityStatus) => {
    setSaving(true)
    setError(null)
    try {
      await onSave({
        id: feedback?.id,
        rating,
        issue_type: issueType,
        severity,
        status: nextStatus ?? status,
        comment,
        corrected_answer: correctedAnswer,
        reviewer_note: reviewerNote,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save review.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-2 w-[min(560px,calc(100vw-48px))] rounded-2xl border border-border-col bg-surface p-4 shadow-lg">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <SelectField label="Rating" value={rating} values={QUALITY_RATINGS} onChange={(v) => setRating(v as QualityRating)} />
        <SelectField label="Issue type" value={issueType} values={QUALITY_ISSUE_TYPES} onChange={setIssueType} />
        <SelectField label="Severity" value={severity} values={QUALITY_SEVERITIES} onChange={(v) => setSeverity(v as QualitySeverity)} />
      </div>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <TextArea label="Что не так?" value={comment} onChange={setComment} rows={3} />
        <TextArea label="Reviewer note" value={reviewerNote} onChange={setReviewerNote} rows={3} />
      </div>
      <div className="mt-3">
        <TextArea label="Как должен был ответить?" value={correctedAnswer} onChange={setCorrectedAnswer} rows={5} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SelectField label="Status" value={status} values={QUALITY_STATUSES} onChange={(v) => setStatus(v as QualityStatus)} compact />
        <button onClick={() => void save()} disabled={saving} className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {saving ? 'Saving...' : 'Save feedback'}
        </button>
        <button onClick={() => void save('fixed')} disabled={saving} className="rounded-xl border border-border-col px-3 py-2 text-sm text-secondary hover:text-primary">Mark fixed</button>
        <button onClick={() => void save('ignored')} disabled={saving} className="rounded-xl border border-border-col px-3 py-2 text-sm text-secondary hover:text-primary">Ignore</button>
        <button onClick={() => void save('added_to_evals')} disabled={saving} className="inline-flex items-center gap-1 rounded-xl border border-green-500/20 bg-green-500/10 px-3 py-2 text-sm text-green-600">
          <CheckCircle2 size={14} /> Add to evals
        </button>
        {error && <span className="text-sm text-red-500">{error}</span>}
      </div>
    </div>
  )
}

function SelectField({ label, value, values, onChange, compact = false }: { label: string; value: string; values: readonly string[]; onChange: (value: string) => void; compact?: boolean }) {
  return (
    <label className={compact ? 'text-xs text-secondary' : 'text-xs font-medium text-secondary'}>
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-xl border border-border-col bg-bg px-3 py-2 text-sm text-primary"
      >
        {values.map((v) => <option key={v} value={v}>{issueLabel(v)}</option>)}
      </select>
    </label>
  )
}

function TextArea({ label, value, onChange, rows }: { label: string; value: string; onChange: (value: string) => void; rows: number }) {
  return (
    <label className="block text-xs font-medium text-secondary">
      {label}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="mt-1 w-full resize-y rounded-xl border border-border-col bg-bg px-3 py-2 text-sm text-primary outline-none focus:border-accent"
      />
    </label>
  )
}

function FeedbackQueue({ items, onOpenConversation }: { items: FeedbackItem[]; onOpenConversation: (item: FeedbackItem) => void }) {
  return (
    <section className="mt-4 overflow-hidden rounded-2xl border border-border-col bg-surface">
      <div className="border-b border-border-col px-4 py-3 text-sm font-semibold">Feedback Queue</div>
      <div className="divide-y divide-border-col">
        {items.map((item) => (
          <div key={item.id} className="grid grid-cols-1 gap-3 px-4 py-4 lg:grid-cols-[1fr_140px_120px_120px] lg:items-center">
            <div>
              <div className="text-xs font-semibold text-accent">{item.instance_id}</div>
              <div className="mt-1 font-mono text-[11px] text-secondary">chat_id: {shortId(item.chat_id)} | message_id: {shortId(item.message_id)}</div>
              <div className="mt-2 line-clamp-2 text-sm text-primary">{item.comment || item.assistant_answer}</div>
            </div>
            <span className="text-sm text-secondary">{item.issue_type}</span>
            <span className={`w-fit rounded-full border px-2 py-1 text-xs ${statusTone(item.status)}`}>{item.status}</span>
            <button onClick={() => onOpenConversation(item)} className="rounded-xl border border-border-col px-3 py-2 text-sm text-secondary hover:text-primary">
              Open chat
            </button>
          </div>
        ))}
        {items.length === 0 && <div className="px-4 py-10 text-sm text-secondary">No feedback items match the current filters.</div>}
      </div>
    </section>
  )
}
