/**
 * Tests for instance/chat/message keyed quality feedback helpers.
 * Run with: npx tsx tests/qualityFeedback.test.ts
 */
import assert from 'node:assert/strict'
import {
  QUALITY_ISSUE_TYPES,
  QUALITY_STATUSES,
  SUPPORTED_QUALITY_INSTANCE_IDS,
  buildConversationQuery,
  buildFeedbackTranscript,
  buildMessageReviewPayload,
  ensureMessageIds,
  findPreviousUserMessage,
} from '../lib/qualityFeedback'

const original = [
  { from: 'ai' as const, text: 'Hello' },
  { from: 'user' as const, text: 'How much is it?' },
  { from: 'ai' as const, text: 'It costs 10.' },
]

const messages = ensureMessageIds(original, 'test')
assert.equal(messages.length, 3)
assert.ok(messages.every((m) => typeof m.id === 'string' && m.id.startsWith('test_')))

const assistantId = messages[2].id as string
assert.equal(findPreviousUserMessage(messages, assistantId), 'How much is it?')

const transcript = buildFeedbackTranscript(messages)
assert.deepEqual(
  transcript.map((m) => m.role),
  ['assistant', 'user', 'assistant'],
)
assert.equal(transcript[2].message_id, assistantId)

assert.ok(QUALITY_ISSUE_TYPES.includes('unsafe_medical_answer'))
assert.ok(QUALITY_ISSUE_TYPES.includes('wrong_program_recommendation'))
assert.ok(QUALITY_ISSUE_TYPES.includes('other'))
assert.ok(QUALITY_STATUSES.includes('open'))
assert.ok(QUALITY_STATUSES.includes('fixed'))
assert.ok(QUALITY_STATUSES.includes('ignored'))
assert.ok(QUALITY_STATUSES.includes('added_to_evals'))
assert.ok(SUPPORTED_QUALITY_INSTANCE_IDS.includes('damiworks_site'))
assert.ok(SUPPORTED_QUALITY_INSTANCE_IDS.includes('damiworks_english_school_demo'))
assert.ok(SUPPORTED_QUALITY_INSTANCE_IDS.includes('damiworks_medical_center_demo'))

const query = buildConversationQuery({
  instance_id: 'damiworks_site',
  chat_id: 'chat-1',
  has_feedback: 'true',
  date_from: '2026-07-01',
  limit: 50,
})
assert.ok(query.includes('instance_id=damiworks_site'))
assert.ok(query.includes('chat_id=chat-1'))
assert.ok(query.includes('has_feedback=true'))
assert.ok(query.includes('limit=50'))

const reviewPayload = buildMessageReviewPayload({
  instance_id: 'damiworks_medical_center_demo',
  chat_id: 'chat-2',
  message_id: 'assistant-1',
  rating: 'negative',
  issue_type: 'wrong_schedule_or_slot',
  severity: 'high',
  status: 'added_to_evals',
  user_message: 'Дамир, завтра после обеда',
  assistant_answer: 'Записал вас на завтра.',
  corrected_answer: 'Точное время подтверждает администратор.',
  comment: 'AI confirmed appointment and invented confirmation.',
  transcript_json: [],
})
assert.equal(reviewPayload.instance_id, 'damiworks_medical_center_demo')
assert.equal(reviewPayload.chat_id, 'chat-2')
assert.equal(reviewPayload.message_id, 'assistant-1')
assert.equal(reviewPayload.corrected_answer, 'Точное время подтверждает администратор.')
assert.equal(reviewPayload.comment, 'AI confirmed appointment and invented confirmation.')
assert.equal(reviewPayload.status, 'added_to_evals')

console.log('\nAll qualityFeedback tests passed.\n')
