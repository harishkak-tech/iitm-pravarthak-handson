export async function request(path, { token, method = 'GET', body, signal } = {}) {
  const response = await fetch(`/api${path}`, {
    method, signal,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Please try again.`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export function publicAnswer(answer) {
  const known = new Set((answer.sources || []).map(String));
  for (const id of answer.citation_validation?.cited_ids || []) known.add(String(id));
  for (const hit of [...(answer.retrieved || []), ...(answer.evidence || [])]) {
    if (hit.chunk_id) known.add(String(hit.chunk_id));
    if (hit.source) known.add(String(hit.source));
  }
  return answer.content.replace(/[ \t]*\[([^\[\]\n]+)\](?!\()/g, (full, marker) => {
    const value = marker.replace(/^sources:\s*/i, '').trim();
    return known.has(value) || value.split(/[,;]/).every(part => known.has(part.trim())) ? '' : full;
  }).trim();
}
