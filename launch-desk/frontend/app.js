const form = document.getElementById('brief-form');
const stream = document.getElementById('stream');
const result = document.getElementById('result');
const progress = document.getElementById('progress');
const toolLog = document.getElementById('tool-log');
const score = document.getElementById('score');
const submit = document.getElementById('submit');

function addTool(message) {
  const item = document.createElement('div');
  item.className = 'tool-item';
  item.textContent = `✓ ${message}`;
  toolLog.appendChild(item);
}

function renderResult(data) {
  score.textContent = `${data.readiness_score}% ready`;
  result.classList.remove('hidden');
  result.innerHTML = `
    <section><h3>Executive summary</h3><p>${escapeHtml(data.executive_summary)}</p></section>
    <section><h3>Prioritized plan</h3><ol>${data.prioritized_plan.map(t => `<li><strong>${escapeHtml(t.priority)} · ${escapeHtml(t.title)}</strong><br><span>${escapeHtml(t.owner)} · ${escapeHtml(t.due)} — ${escapeHtml(t.rationale)}</span></li>`).join('')}</ol></section>
    <section><h3>Risk register</h3><ul>${data.risks.map(r => `<li><strong>${escapeHtml(r.severity)} · ${escapeHtml(r.risk)}</strong><br><span>${escapeHtml(r.mitigation)} · Owner: ${escapeHtml(r.owner)}</span></li>`).join('')}</ul></section>
    <section><h3>Owner checklist</h3><ul>${data.owner_checklist.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul></section>
    <section><h3>Launch copy</h3>${Object.entries(data.launch_copy).map(([k,v]) => `<div class="copy"><b>${escapeHtml(k)}</b><p>${escapeHtml(v)}</p></div>`).join('')}</section>
    <section><h3>Follow-up questions</h3>${data.follow_up_questions.length ? `<ul>${data.follow_up_questions.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>` : '<p>No material gaps detected.</p>'}</section>
  `;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  submit.textContent = 'Building plan…';
  stream.textContent = '';
  result.classList.add('hidden');
  toolLog.innerHTML = '';
  score.textContent = '—';
  progress.textContent = 'Connecting to Launch Desk…';

  const payload = Object.fromEntries(['product_brief','audience','launch_date','constraints','available_assets'].map(id => [id, document.getElementById(id).value]));
  try {
    const response = await fetch('/api/launch/stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Accept': 'text/event-stream'},
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) throw new Error(`Request failed (${response.status})`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const frames = buffer.split('\n\n');
      buffer = frames.pop();
      for (const frame of frames) {
        const eventMatch = frame.match(/^event: (.+)$/m);
        const dataMatch = frame.match(/^data: (.+)$/m);
        if (!eventMatch || !dataMatch) continue;
        const type = eventMatch[1];
        const data = JSON.parse(dataMatch[1]);
        if (type === 'status') progress.textContent = data.message;
        if (type === 'tool_progress') { progress.textContent = `Running ${data.tool}…`; addTool(`${data.tool} ${data.status}`); }
        if (type === 'text_delta') { stream.textContent += data.delta; progress.textContent = 'Drafting your launch plan…'; }
        if (type === 'complete') { renderResult(data.result); progress.textContent = 'Plan complete.'; }
        if (type === 'error') throw new Error(data.error);
      }
    }
  } catch (error) {
    progress.textContent = `Error: ${error.message}`;
  } finally {
    submit.disabled = false;
    submit.innerHTML = 'Build launch plan <span>→</span>';
  }
});
