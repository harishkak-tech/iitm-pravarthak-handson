import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Markdown from 'react-markdown';
import { request, publicAnswer } from './api.js';
import './styles.css';

const Json = ({ value }) => <pre>{JSON.stringify(value, null, 2)}</pre>;

function App() {
  const [token, setToken] = useState(null);
  const [login, setLogin] = useState(false);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function ask(event) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true); setError(''); setAnswer(null);
    try {
      const data = await request('/ask_rag', { method: 'POST', body: { question: question.trim() }, signal: AbortSignal.timeout(180000) });
      if (typeof data.content !== 'string') throw new Error('The assistant returned an incomplete response. Please try again.');
      setAnswer(data);
    } catch (err) { setError(err.name === 'TimeoutError' ? 'The assistant timed out. Please try again.' : err.message); }
    finally { setBusy(false); }
  }
  async function logout() {
    try { await request('/admin/logout', { token, method: 'POST' }); }
    catch { /* Local sign-out also works when the server is unavailable. */ }
    setToken(null);
  }
  return <>
    <header><a className="brand" href="/">Knowledge Assistant<span>PUBLIC POLICY KNOWLEDGE BASE</span></a>
      <button className="quiet" onClick={() => token ? logout() : setLogin(!login)}>{token ? 'Sign out' : login ? 'Back to assistant' : 'Admin login'}</button></header>
    <main>
      {login && !token && <Login onSuccess={value => { setToken(value); setLogin(false); }} />}
      {!login && <><section className="intro"><p className="eyebrow">YOUR KNOWLEDGE, WITH CLARITY</p><h1>What would you like<br />to understand?</h1><p>Explore public policies and services through answers grounded in our document collection.</p></section>
        <section className="card"><form onSubmit={ask}><label htmlFor="question">Ask a question</label><textarea id="question" placeholder="Who is eligible for PM-KISAN?" value={question} onChange={e => setQuestion(e.target.value)} required maxLength={10000} />
          <div className="form-footer"><span>Answers based on the available corpus</span><button disabled={busy || !question.trim()}>{busy ? 'Preparing answer…' : 'Ask assistant ↗'}</button></div></form>
          {error && <p className="error" role="alert">{error}</p>}
          <div aria-live="polite" aria-busy={busy}>{busy && <p className="loading">Searching the collection and preparing your answer…</p>}
            {answer && <article className="answer"><p className="eyebrow">ANSWER</p><Markdown>{publicAnswer(answer)}</Markdown></article>}</div>
        </section></>}
      {token && <Admin token={token} answer={answer} onExpired={() => { setToken(null); setLogin(true); }} />}
    </main><footer>Knowledge Assistant · Built around your document collection</footer>
  </>;
}

function Login({ onSuccess }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { const data = await request('/admin/login', { method: 'POST', body: Object.fromEntries(form) }); onSuccess(data.token); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="card login"><h1>Admin login</h1><p>Manage settings and inspect saved evaluations.</p><form onSubmit={submit}>
    <label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" defaultValue="admin" required />
    <label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" required />
    {error && <p className="error" role="alert">{error}</p>}<button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
  </form></section>;
}

function Admin({ token, answer, onExpired }) {
  const [tab, setTab] = useState('Settings and runs');
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(null);
  const [history, setHistory] = useState({ golden_runs: [], runs: [] });
  const [jobs, setJobs] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  function handleError(err) { if (err.status === 401) onExpired(); else setError(err.message); }
  const call = (path, options) => request(`/admin${path}`, { token, ...options });
  async function refresh(reload = false) {
    setError('');
    try {
      const [settings, saved, currentJobs] = await Promise.all([call('/settings'), call('/history'), call('/jobs')]);
      setHistory(saved); setJobs(currentJobs);
      if (reload) { setRecord(settings); setDraft(settings.settings); }
    } catch (err) { handleError(err); }
  }
  useEffect(() => {
    let active = true;
    refresh(true);
    const timer = setInterval(async () => {
      try {
        const [current, saved] = await Promise.all([call('/jobs'), call('/history')]);
        if (active) { setJobs(current); setHistory(saved); }
      } catch (err) { if (active) handleError(err); }
    }, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [token]);
  async function save(launch) {
    setBusy(true); setError(''); setMessage('');
    try {
      const saved = await call('/settings', { method: 'PUT', body: { settings: draft, expected_revision: record.revision } });
      setRecord(saved); setDraft(saved.settings); setMessage('Settings saved.');
      if (launch) { await call('/jobs', { method: 'POST', body: { expected_revision: saved.revision } }); setMessage('Settings saved. Evaluation launched.'); }
      await refresh();
    } catch (err) { handleError(err); }
    finally { setBusy(false); }
  }
  const activeJob = jobs.some(job => ['queued', 'running'].includes(job.status));
  return <section className="admin"><div className="section-title"><div><p className="eyebrow">ADMINISTRATION</p><h2>Workspace</h2></div><button className="quiet" onClick={() => refresh()}>Refresh results</button></div>
    <nav aria-label="Admin sections">{['Settings and runs', 'Golden evaluations', 'Pipeline runs', 'Answer diagnostics'].map(name => <button key={name} aria-pressed={tab === name} className={tab === name ? 'selected' : 'quiet'} onClick={() => setTab(name)}>{name}</button>)}</nav>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status" className="success">{message}</p>}
    {tab === 'Settings and runs' && <div className="card"><h3>Saved application settings</h3>{record ? <>
      <p>Revision {record.revision} · Updated by {record.updated_by}. New questions use saved settings.</p>
      <button className="quiet" disabled={busy} onClick={() => refresh(true)}>Reload saved settings</button>
      <form onSubmit={event => { event.preventDefault(); save(event.nativeEvent.submitter.value === 'launch'); }}>
      <SettingsEditor key={record.revision} value={draft} onChange={setDraft} schema={record.schema} definitions={record.schema.$defs} />
      <p>Changes to corpus, chunking, embeddings or collection require re-ingestion before evaluation.</p>
      <div className="actions"><button disabled={busy} value="save">Save settings</button><button disabled={busy || activeJob} value="launch">Save and run golden set</button></div>
      </form>
    </> : <p>Loading settings…</p>}
      <h3>Evaluation jobs</h3>{!jobs.length && <p>No evaluations launched yet.</p>}{jobs.map(job => <details key={job.id} open={job === jobs[0]}><summary>{job.status} · {job.id.slice(0, 8)} · revision {job.settings_revision}</summary>
        <p>{job.completed_questions} / {job.total_questions} questions · Run {job.run_id || 'pending'}</p>{job.total_questions > 0 && <progress value={job.completed_questions} max={job.total_questions} />}{job.error && <p className="error">{job.error}</p>}<Json value={job} /></details>)}
    </div>}
    {tab === 'Golden evaluations' && <RunBrowser runs={history.golden_runs} golden token={token} onError={handleError} />}
    {tab === 'Pipeline runs' && <RunBrowser runs={history.runs} golden={false} token={token} onError={handleError} />}
    {tab === 'Answer diagnostics' && <div className="card"><h3>Latest answer diagnostics</h3>{answer ? <><Markdown>{answer.content}</Markdown><h4>Sources, retrieved chunks, evidence and citations</h4><Json value={answer} /></> : <p>Ask a question to inspect its evidence and diagnostics.</p>}</div>}
  </section>;
}

function SettingsEditor({ value, onChange, path = 'settings', schema, definitions }) {
  return <div className="settings">{Object.entries(value).map(([key, current]) => {
    const id = `${path}.${key}`;
    const label = key.replaceAll('_', ' ');
    const update = next => onChange({ ...value, [key]: next });
    let field = schema?.properties?.[key] || {};
    if (field.$ref) field = definitions[field.$ref.split('/').at(-1)];
    const nullable = field.anyOf?.some(option => option.type === 'null');
    const base = nullable ? field.anyOf.find(option => option.type !== 'null') : field;
    if (current && typeof current === 'object' && !Array.isArray(current) && field.properties) return <details key={key}><summary>{label}</summary><SettingsEditor value={current} onChange={update} path={id} schema={field} definitions={definitions} /></details>;
    return <div className="field" key={key}><label htmlFor={id}>{label}</label>
      {base.enum ? <select id={id} value={current} onChange={e => update(e.target.value)}>{base.enum.map(option => <option key={option}>{option}</option>)}</select>
        : nullable && base.type === 'boolean' ? <select id={id} value={String(current)} onChange={e => update(JSON.parse(e.target.value))}><option value="null">Use environment default</option><option value="false">Live</option><option value="true">Offline</option></select>
        : typeof current === 'boolean' ? <input id={id} type="checkbox" checked={current} onChange={e => update(e.target.checked)} />
        : ['integer', 'number'].includes(base.type) ? <input id={id} type="number" required={!nullable} step={base.type === 'integer' ? 1 : 'any'} value={current ?? ''} placeholder={nullable ? 'Use default / no limit' : ''} onChange={e => update(e.target.value === '' ? null : Number(e.target.value))} />
        : typeof current === 'object' ? <JsonField id={id} value={current} onChange={update} />
        : <textarea id={id} rows={key === 'system_prompt' ? 8 : 2} value={current} onChange={e => update(e.target.value)} />}</div>;
  })}</div>;
}

function JsonField({ id, value, onChange }) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState('');
  return <><textarea id={id} value={text} onChange={e => {
    setText(e.target.value);
    try { const parsed = JSON.parse(e.target.value); onChange(parsed); setError(''); e.target.setCustomValidity(''); }
    catch { setError('Enter valid JSON before saving.'); e.target.setCustomValidity('Enter valid JSON before saving.'); }
  }} />{error && <p role="alert" className="error">{error}</p>}</>;
}

function SavedRunDetails({ run }) {
  const kpis = run.summary?.kpis || {};
  const number = (value, suffix = '', digits = 2) => Number.isFinite(value) ? `${value.toFixed(digits)}${suffix}` : 'Not recorded';
  const rates = [ ['Task success', 'task_success'], ['Citation validity', 'citation_validity'],
    ['Correct abstention', 'correct_abstention'], ['False abstention', 'false_abstention'],
    ['Grounded responses', 'grounded_response'], ['Hallucination', 'hallucination'] ];
  const flatten = (value, prefix = '') => Object.entries(value || {}).flatMap(([key, item]) => {
    const name = prefix ? `${prefix}.${key}` : key;
    return item && typeof item === 'object' && !Array.isArray(item) && Object.keys(item).length
      ? flatten(item, name) : [[name, JSON.stringify(item)]];
  });
  return <section aria-label="Saved run details"><h3>Eight evaluation KPIs · Run {run.id}</h3>
    <div className="kpi-grid">{rates.map(([label, key]) => <div className="kpi" key={key}><span>{label}</span>
      <strong>{number(kpis[key]?.rate == null ? null : kpis[key].rate * 100, '%', 1)}</strong>
      {kpis[key] && <small>{kpis[key].numerator} / {kpis[key].denominator}</small>}</div>)}
      <div className="kpi"><span>Response latency</span><strong>p50 {number(kpis.latency_p50_seconds, ' s')}</strong><small>p95 {number(kpis.latency_p95_seconds, ' s')}</small></div>
      <div className="kpi"><span>Mean generation cost</span><strong>{Number.isFinite(kpis.mean_generation_cost_usd) ? `$${kpis.mean_generation_cost_usd.toFixed(6)}` : 'Not recorded'}</strong><small>USD per question</small></div>
    </div><p>Latency measure: {kpis.latency_measure || 'Not recorded'}. Missing metrics were not recorded for this run.</p>
    <h3>Settings used · Run {run.id}</h3><p>Saved snapshot from this evaluation.</p>
    <p>Golden set: {run.golden_path} · Corpus: {run.corpus_dir} · Question limit: {run.entry_limit ?? 'All'}</p>
    <div className="table-wrap"><table><thead><tr><th>Setting</th><th>Value</th></tr></thead><tbody>
      {flatten({ settings: run.settings, judge: run.judge_settings }).map(([key, value]) => <tr key={key}><td>{key}</td><td>{value}</td></tr>)}
    </tbody></table></div>
    {run.summary?.rag_metrics?.mode && <details><summary>RAGAS metrics · {run.summary.rag_metrics.mode}</summary><Json value={run.summary.rag_metrics} /></details>}
  </section>;
}

function RunBrowser({ runs, golden, token, onError }) {
  const [selected, setSelected] = useState('');
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('All');
  const [loading, setLoading] = useState(false);
  const runId = selected || (runs[0]?.id ? String(runs[0].id) : '');
  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    setRows([]); setLoading(true);
    request(`/admin/runs/${runId}?golden=${golden}`, { token, signal: controller.signal }).then(setRows).catch(err => { if (err.name !== 'AbortError') onError(err); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [runId, golden, token]);
  if (!runs.length) return <div className="card"><p>No saved runs yet. Completed evaluations appear here automatically.</p></div>;
  const run = runs.find(item => String(item.id) === runId);
  const filtered = rows.filter(row => JSON.stringify(row).toLowerCase().includes(search.toLowerCase()) && (!golden || status === 'All' || Boolean(row.pass_fail) === (status === 'Passed')));
  return <div className="card"><h3>Run history</h3><div className="table-wrap"><table><thead><tr><th>Run</th><th>Started</th><th>Model</th><th>Pass rate</th></tr></thead><tbody>{runs.map(item => <tr key={item.id}><td>{item.id}</td><td>{item.started_at}</td><td>{item.model}</td><td>{item.summary ? `${((item.summary.pass_rate || 0) * 100).toFixed(1)}%` : '—'}</td></tr>)}</tbody></table></div>
    <label htmlFor={`run-${golden}`}>Inspect run</label><select id={`run-${golden}`} value={runId} onChange={e => setSelected(e.target.value)}>{runs.map(item => <option key={item.id} value={item.id}>Run {item.id} · {item.model} · {item.started_at}</option>)}</select>
    {golden && run && <SavedRunDetails key={run.id} run={run} />}
    <details><summary>Full saved run JSON</summary><Json value={run} /></details>
    <label htmlFor={`search-${golden}`}>Search questions, answers or judge reasoning</label><input id={`search-${golden}`} value={search} onChange={e => setSearch(e.target.value)} />
    {golden && <><label htmlFor="result-status">Result status</label><select id="result-status" value={status} onChange={e => setStatus(e.target.value)}>{['All', 'Failed', 'Passed'].map(item => <option key={item}>{item}</option>)}</select></>}
    <p aria-live="polite">{loading ? 'Loading results…' : `Showing ${filtered.length} of ${rows.length} results`}</p>{filtered.map((row, index) => <details key={row.id ?? index}><summary>{golden ? (row.pass_fail ? 'Passed · ' : 'Failed · ') : ''}{row.question || row.text || row.id}</summary><Markdown>{row.answer_text || row.content || ''}</Markdown><Json value={row} /></details>)}
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
