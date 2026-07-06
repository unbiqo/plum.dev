'use client'

import { useState } from 'react'
import { Check, MessageSquareWarning, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import {
  QUALITY_ISSUE_TYPES,
  QUALITY_SEVERITIES,
  buildFeedbackTranscript,
  findPreviousUserMessage,
  issueLabel,
  type QualityChatMessage,
  type QualityIssueType,
  type QualityRating,
  type QualitySeverity,
} from '@/lib/qualityFeedback'

type Props = {
  instanceId: string
  chatId: string
  message: QualityChatMessage
  messages: QualityChatMessage[]
  metadata?: Record<string, unknown>
}

export default function MessageFeedback({ instanceId, chatId, message, messages, metadata }: Props) {
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState<QualityRating>('negative')
  const [issueType, setIssueType] = useState<QualityIssueType>('other')
  const [severity, setSeverity] = useState<QualitySeverity>('medium')
  const [comment, setComment] = useState('')
  const [correctedAnswer, setCorrectedAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState(false)

  if (message.from !== 'ai' || !message.id) return null
  const messageId = message.id

  const submit = async () => {
    setSubmitting(true)
    setError(false)
    try {
      const res = await fetch('/api/quality-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instance_id: instanceId,
          chat_id: chatId,
          message_id: messageId,
          rating,
          issue_type: issueType,
          severity,
          status: 'open',
          user_message: findPreviousUserMessage(messages, messageId),
          assistant_answer: message.text,
          corrected_answer: correctedAnswer.trim() || null,
          comment: comment.trim() || null,
          transcript_json: buildFeedbackTranscript(messages),
          metadata: {
            ...(metadata ?? {}),
            submitted_from: 'chat_widget',
          },
          source: 'web_chat',
          environment: process.env.NODE_ENV,
          tags: [],
        }),
      })
      if (!res.ok) throw new Error('feedback_failed')
      setSubmitted(true)
      setOpen(false)
    } catch {
      setError(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mt-1 flex flex-col items-start gap-2">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => {
            setRating('positive')
            setOpen(true)
          }}
          className="h-6 w-6 rounded-md text-secondary hover:bg-surface hover:text-primary flex items-center justify-center transition-colors"
          aria-label="Mark answer as helpful"
          title="Helpful"
        >
          <ThumbsUp size={13} />
        </button>
        <button
          type="button"
          onClick={() => {
            setRating('negative')
            setOpen(true)
          }}
          className="h-6 w-6 rounded-md text-secondary hover:bg-surface hover:text-primary flex items-center justify-center transition-colors"
          aria-label="Report answer issue"
          title="Report issue"
        >
          <ThumbsDown size={13} />
        </button>
        {submitted && (
          <span className="inline-flex items-center gap-1 text-[11px] text-green-600">
            <Check size={12} /> Saved
          </span>
        )}
      </div>

      {open && (
        <div className="w-full max-w-[360px] rounded-xl border border-border-col bg-bg p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-primary">
              <MessageSquareWarning size={13} />
              Quality feedback
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-secondary hover:text-primary"
              aria-label="Close feedback form"
            >
              <X size={14} />
            </button>
          </div>

          <div className="grid grid-cols-1 gap-2">
            <label className="text-[11px] text-secondary">
              Rating
              <select
                value={rating}
                onChange={(e) => setRating(e.target.value as QualityRating)}
                className="mt-1 w-full rounded-lg border border-border-col bg-surface px-2 py-1.5 text-xs text-primary"
              >
                <option value="negative">Negative</option>
                <option value="positive">Positive</option>
              </select>
            </label>
            <label className="text-[11px] text-secondary">
              Issue type
              <select
                value={issueType}
                onChange={(e) => setIssueType(e.target.value as QualityIssueType)}
                className="mt-1 w-full rounded-lg border border-border-col bg-surface px-2 py-1.5 text-xs text-primary"
              >
                {QUALITY_ISSUE_TYPES.map((issue) => (
                  <option key={issue} value={issue}>
                    {issueLabel(issue)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] text-secondary">
              Severity
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as QualitySeverity)}
                className="mt-1 w-full rounded-lg border border-border-col bg-surface px-2 py-1.5 text-xs text-primary"
              >
                {QUALITY_SEVERITIES.map((value) => (
                  <option key={value} value={value}>
                    {issueLabel(value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] text-secondary">
              What is wrong?
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="mt-1 w-full resize-none rounded-lg border border-border-col bg-surface px-2 py-1.5 text-xs text-primary"
              />
            </label>
            <label className="text-[11px] text-secondary">
              Corrected answer
              <textarea
                value={correctedAnswer}
                onChange={(e) => setCorrectedAnswer(e.target.value)}
                rows={3}
                className="mt-1 w-full resize-none rounded-lg border border-border-col bg-surface px-2 py-1.5 text-xs text-primary"
              />
            </label>
            {error && <div className="text-[11px] text-red-500">Could not save feedback.</div>}
            <button
              type="button"
              onClick={() => void submit()}
              disabled={submitting}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {submitting ? 'Saving...' : 'Save feedback'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
