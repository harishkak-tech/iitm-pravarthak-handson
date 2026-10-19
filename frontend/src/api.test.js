import test from 'node:test';
import assert from 'node:assert/strict';
import { publicAnswer, request } from './api.js';

test('public display hides known citations while preserving Markdown links and brackets', () => {
  const answer = { content: 'Supported [source#1]. [note] [website](https://example.com) [Sources: source#1, chunk#2]', sources: ['source#1'], evidence: [{ chunk_id: 'chunk#2' }] };
  assert.equal(publicAnswer(answer), 'Supported. [note] [website](https://example.com)');
  assert.ok(answer.content.includes('[source#1]'));
  assert.equal(publicAnswer({ content: 'Answer [cite#1]', citation_validation: { cited_ids: ['cite#1'] } }), 'Answer');
});

test('request sends questions to the same-origin API and adds authorization only when provided', async () => {
  const previous = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (...args) => { calls.push(args); return { ok: true, json: async () => ({ content: 'Answer' }) }; };
  try {
    assert.deepEqual(await request('/ask_rag', { method: 'POST', body: { question: 'Question' } }), { content: 'Answer' });
    assert.equal(calls[0][0], '/api/ask_rag');
    assert.equal(calls[0][1].headers.Authorization, undefined);
    assert.equal(calls[0][1].body, '{"question":"Question"}');
    await request('/admin/settings', { token: 'test-token' });
    assert.equal(calls[1][1].headers.Authorization, 'Bearer test-token');
  } finally { globalThis.fetch = previous; }
});

test('HTTP errors retain status for expired admin sessions', async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Please sign in.' }) });
  try { await assert.rejects(request('/admin/settings'), err => err.status === 401 && err.message === 'Please sign in.'); }
  finally { globalThis.fetch = previous; }
});
