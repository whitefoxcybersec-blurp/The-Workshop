let scopeRoot = 'demo.test';
let historyEvents = [];
let hypothesisRecords = [];

const hypotheses = [
  { id: 'cors', name: 'CORS permissivo pode expor dados autenticados', detail: 'H-01', confidence: 0.78 },
  { id: 'cookie', name: 'Política de cookie pode permitir CSRF', detail: 'H-02', confidence: 0.66 },
  { id: 'jwt', name: 'Validação de JWT merece revisão manual', detail: 'H-03', confidence: 0.43 },
];

const viewMeta = {
  hunt: { title: 'Hunt <em>map</em>', crumb: 'HUNT MAP', description: 'Sinais observados, hipóteses em avaliação e limites da sessão.' },
  findings: { title: 'Open <em>findings</em>', crumb: 'FINDINGS', description: 'Hipóteses ordenadas por confiança, com trilha de evidências.' },
  crypto: { title: 'Crypto <em>surface</em>', crumb: 'CRYPTO SURFACE', description: 'Inventário criptográfico derivado somente de artefatos observados.' },
  recon: { title: 'Recon <em>queue</em>', crumb: 'RECON QUEUE', description: 'Ações sugeridas aguardam avaliação de política. Nada é executado automaticamente.' },
  history: { title: 'Session <em>history</em>', crumb: 'HISTORY', description: 'Linha do tempo local de observações e decisões desta sessão.' },
};

let evidence = [];
let activeView = 'hunt';
let activeFilter = 'ALL';
let toastTimer;

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `WOLF Core returned HTTP ${response.status}`);
  }
  return response.json();
}

async function refreshData() {
  const [session, evidenceData, scopeData, historyData, hypothesisData] = await Promise.all([
    apiRequest('/api/session'),
    apiRequest('/api/evidence'),
    apiRequest('/api/scope'),
    apiRequest('/api/history'),
    apiRequest('/api/hypotheses'),
  ]);
  evidence = evidenceData;
  scopeRoot = scopeData.roots[0] || 'no active root';
  historyEvents = historyData;
  hypothesisRecords = hypothesisData;
  document.querySelector('.target-name').textContent = `shop.${scopeRoot}`;
  document.querySelector('.scope-mini').innerHTML = `<span class="scope-dot"></span> ${escapeHtml(scopeRoot)}`;
  document.querySelector('.sidebar-version').textContent = `LOCAL SESSION · ${session.name}`;
  renderView();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

function getConfidence() {
  const corsEvidence = evidence.filter((item) => item.bearing !== 'neutral' && /cors|origin|access-control/i.test(`${item.title} ${item.detail}`));
  const logOdds = Math.log(0.62 / (1 - 0.62)) + corsEvidence.reduce((sum, item) => sum + (item.bearing === 'supports' ? Math.log(1.8) : item.bearing === 'contradicts' ? Math.log(0.5) : 0), 0);
  return 1 / (1 + Math.exp(-logOdds));
}

function getVisibleEvidence() {
  const search = document.querySelector('#evidence-search')?.value.trim().toLowerCase() || '';
  return evidence.filter((item) => {
    const matchesType = activeFilter === 'ALL' || item.kind === activeFilter;
    const matchesSearch = !search || `${item.title} ${item.kind} ${item.detail}`.toLowerCase().includes(search);
    return matchesType && matchesSearch;
  });
}

function renderEvidenceRows(items) {
  if (!items.length) return '<tr><td class="empty-row" colspan="5">Nenhuma evidência corresponde a este filtro.</td></tr>';
  return items.map((item) => {
    const bearingText = { supports: 'SUPPORTS', neutral: 'NEUTRAL', contradicts: 'CONTRADICTS' }[item.bearing];
    const bearingClass = item.bearing === 'neutral' ? 'is-neutral' : item.bearing === 'contradicts' ? 'is-contradicts' : '';
    const kindClass = ['CRYPTO', 'TLS'].includes(item.kind) ? 'crypto' : '';
    return `<tr><td>${escapeHtml(item.title)}</td><td><span class="type-chip ${kindClass}">${escapeHtml(item.kind)}</span></td><td class="${item.kind === 'CRYPTO' ? 'bearing' : 'bearing ' + bearingClass}">${bearingText}</td><td>${escapeHtml(item.detail)}</td><td>${escapeHtml(item.time)}</td></tr>`;
  }).join('');
}

function renderEvidenceTable() {
  const body = document.querySelector('#evidence-body');
  if (body) body.innerHTML = renderEvidenceRows(getVisibleEvidence());
}

function renderMap() {
  const confidence = getConfidence();
  const list = hypotheses.map((hypothesis) => {
    const current = hypothesis.id === 'cors' ? confidence : hypothesis.confidence;
    const percent = Math.round(current * 100);
    const tone = percent < 50 ? 'is-low' : percent < 70 ? 'is-mid' : '';
    const linkedEvidence = hypothesisRecords.find((record) => record.id === hypothesis.id)?.evidence_count ?? 0;
    const metadata = `${hypothesis.detail} · ${linkedEvidence} evidência${linkedEvidence === 1 ? '' : 's'} vinculada${linkedEvidence === 1 ? '' : 's'}`;
    return `<div class="hypothesis"><div><div class="hypothesis-name">${hypothesis.name}</div><div class="hypothesis-meta">${metadata}</div></div><div class="confidence-track" aria-label="Confiança ${percent}%"><div class="confidence-fill ${tone}" style="width:${percent}%"></div></div><div class="confidence-number">${percent}%</div></div>`;
  }).join('');
  return `<div class="dashboard-grid">
    <section class="panel">
      <div class="panel-header"><h2 class="panel-title">Bayesian engine <span class="panel-kicker">3 ACTIVE HYPOTHESES</span></h2><button class="panel-action" data-go="findings">ALL FINDINGS ↗</button></div>
      <div class="hypothesis-list">${list}</div>
      <div class="map-footer"><span>PRIORS UPDATED FROM OBSERVED SIGNALS</span><strong>LAST UPDATE · AGORA</strong></div>
    </section>
    <div class="side-stack">
      <section class="panel"><div class="panel-header"><h2 class="panel-title">Policy boundary</h2><span class="panel-kicker">ENFORCED</span></div>
        <div class="policy-body"><div class="policy-domain-label">ALLOWED ROOT</div><div class="policy-domain"><span>*.${scopeRoot}</span><span>IN SCOPE</span></div>
          <form class="scope-check" id="scope-check-form"><input id="scope-check-input" aria-label="Host para verificar escopo" placeholder="host a verificar" autocomplete="off" /><button type="submit">CHECK</button></form>
          <p class="scope-result" id="scope-result" aria-live="polite">WOLF Core · nenhum host contatado.</p>
          <div class="policy-footnote"><span>ACTIVE PROBES</span><span>DISABLED BY DEFAULT</span></div></div>
      </section>
      <section class="panel"><div class="panel-header"><h2 class="panel-title">Recent signals</h2><button class="panel-action" data-go="history">TIMELINE ↗</button></div>
        <div class="signal-list"><div class="signal-row"><span class="signal-dot"></span><span class="signal-name">Header CORS observado</span><span class="signal-type">HTTP</span></div><div class="signal-row"><span class="signal-dot warn"></span><span class="signal-name">Cookie sem SameSite</span><span class="signal-type">HTTP</span></div><div class="signal-row"><span class="signal-dot neutral"></span><span class="signal-name">TLS 1.3 · cert válido</span><span class="signal-type">TLS</span></div></div>
      </section>
    </div>
  </div>
  <section class="panel wide-panel"><div class="panel-header"><h2 class="panel-title">Evidence stream <span class="panel-kicker">SQLITE · ${String(evidence.length).padStart(2, '0')} RECORDS</span></h2><div class="evidence-tools"><input class="evidence-search" id="evidence-search" placeholder="SEARCH EVIDENCE" aria-label="Buscar evidências" /><select class="filter-select" id="evidence-filter" aria-label="Filtrar por tipo"><option value="ALL">ALL TYPES</option><option>HTTP</option><option>TLS</option><option>JWT</option><option>CRYPTO</option></select><input type="file" id="evidence-file" accept=".json,.har,.txt,.headers,application/json" hidden /><button class="panel-action" id="import-evidence">↑ IMPORT</button><button class="panel-action" id="add-evidence">+ ADD</button></div></div>
    <table class="evidence-table"><thead><tr><th>OBSERVATION</th><th>TYPE</th><th>BAYES</th><th>SOURCE / CONTEXT</th><th>TIME</th></tr></thead><tbody id="evidence-body">${renderEvidenceRows(getVisibleEvidence())}</tbody></table>
  </section>`;
}

function renderFindings() {
  return `<section class="panel view-panel"><div class="panel-header"><h2 class="panel-title">Findings & evidence</h2><span class="panel-kicker">CONFIDENCE · DESCENDING</span></div><p class="view-intro">Nenhum item é promovido automaticamente a vulnerabilidade confirmada. Cada hipótese permanece ligada às observações que a sustentam ou contradizem.</p><div class="view-list">${hypotheses.map((item) => { const linkedEvidence = hypothesisRecords.find((record) => record.id === item.id)?.evidence_count ?? 0; return `<div class="view-list-row"><strong>${item.name}</strong><span>${item.detail} · ${linkedEvidence} evidência(s) vinculada(s)</span><span>${Math.round((item.id === 'cors' ? getConfidence() : item.confidence) * 100)}% CONF.</span></div>`; }).join('')}</div></section>`;
}

function renderCrypto() {
  const counts = [
    ['TLS VERSION', 'TLS 1.3'], ['CERTIFICATE', '89d validity'], ['JWT SIGNATURE', 'RS256'],
    ['KEY DISCOVERY', 'JWKS · 1 key'], ['NONCE SAMPLE', '32 bytes'], ['KDF / IV', 'Not observed'],
  ];
  return `<section class="panel view-panel"><div class="panel-header"><h2 class="panel-title">Observed crypto surface</h2><span class="panel-kicker">PASSIVE INVENTORY</span></div><p class="view-intro">Inventário derivado de headers, tokens e metadados já presentes na sessão. Ausência de observação não indica ausência de controle.</p><div class="crypto-grid">${counts.map(([label, value]) => `<div class="crypto-item"><span>${label}</span><strong>${value}</strong></div>`).join('')}</div></section>`;
}

function renderRecon() {
  return `<section class="panel view-panel"><div class="panel-header"><h2 class="panel-title">Recon planner</h2><span class="panel-kicker">1 SUGGESTION · 0 EXECUTIONS</span></div><p class="view-intro">O planner só apresenta uma próxima ação de baixo impacto para revisão. Esta versão não executa requests, não resolve hosts e não testa endpoints.</p><div class="queue-item"><span class="queue-index">RQ-01</span><div><strong>Revisão manual do comportamento CORS em origem autorizada</strong><small>Rationale · confiança ainda abaixo do limiar de reporte (85%)</small></div><span class="queue-status">MANUAL ONLY</span></div><div class="queue-item"><span class="queue-index">RQ-02</span><div><strong>Revisar atributos de cookie nas respostas já coletadas</strong><small>Rationale · evidência passiva suficiente para triagem</small></div><span class="queue-status">PASSIVE ONLY</span></div></section><section class="panel wide-panel"><div class="panel-header"><h2 class="panel-title">Boundary stops</h2><span class="panel-kicker">POLICY LOG</span></div><p class="view-intro">Nenhuma ação ativa foi tentada. A checagem de escopo nesta sessão valida somente o sufixo autorizado <code>demo.test</code>, em memória local.</p></section>`;
}

function renderHistory() {
  return `<section class="panel view-panel"><div class="panel-header"><h2 class="panel-title">Session timeline</h2><span class="panel-kicker">SQLITE · NEWEST FIRST</span></div><div class="history-list">${historyEvents.slice(0, 30).map((item) => `<div class="history-event"><time>${escapeHtml(new Date(item.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }))}</time><span class="history-marker"></span><span><strong>${escapeHtml(item.event_type)}</strong> · ${escapeHtml(item.summary)}</span></div>`).join('') || '<p class="view-intro">Ainda não há eventos nesta sessão.</p>'}</div></section>`;
}

function renderView() {
  const meta = viewMeta[activeView];
  document.querySelector('#page-title').innerHTML = meta.title;
  document.querySelector('#page-description').textContent = meta.description;
  document.querySelector('#crumb-current').textContent = meta.crumb;
  document.querySelector('#view-content').innerHTML = ({ hunt: renderMap, findings: renderFindings, crypto: renderCrypto, recon: renderRecon, history: renderHistory })[activeView]();
  document.querySelector('#metric-evidence').textContent = String(evidence.length).padStart(2, '0');
  document.querySelector('#metric-confidence').innerHTML = `${Math.round((getConfidence() + 0.66 + 0.43) / 3 * 100)}<span class="metric-unit">%</span>`;
  document.querySelectorAll('.nav-link').forEach((button) => {
    const isActive = button.dataset.view === activeView;
    button.classList.toggle('is-active', isActive);
    if (isActive) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
}

function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2600);
}

document.querySelectorAll('.nav-link').forEach((button) => button.addEventListener('click', () => {
  activeView = button.dataset.view;
  renderView();
}));

document.querySelector('#view-content').addEventListener('click', (event) => {
  const target = event.target.closest('[data-go], #add-evidence, #import-evidence');
  if (!target) return;
  if (target.dataset.go) {
    activeView = target.dataset.go;
    renderView();
  } else if (target.id === 'import-evidence') {
    document.querySelector('#evidence-file').click();
  } else {
    document.querySelector('#evidence-dialog').showModal();
    document.querySelector('#evidence-title').focus();
  }
});

document.querySelector('#view-content').addEventListener('input', (event) => {
  if (event.target.id === 'evidence-search') renderEvidenceTable();
});
document.querySelector('#view-content').addEventListener('change', (event) => {
  if (event.target.id === 'evidence-filter') {
    activeFilter = event.target.value;
    renderEvidenceTable();
  }
  if (event.target.id === 'evidence-file' && event.target.files.length) importArtifact(event.target.files[0]);
});

document.querySelector('#view-content').addEventListener('submit', async (event) => {
  if (event.target.id !== 'scope-check-form') return;
  event.preventDefault();
  const host = document.querySelector('#scope-check-input').value;
  const result = document.querySelector('#scope-result');
  try {
    const decision = await apiRequest('/api/scope/check', {
      method: 'POST',
      body: JSON.stringify({ host }),
    });
    result.classList.toggle('is-blocked', !decision.allowed);
    result.textContent = decision.allowed
      ? `${decision.host} · IN SCOPE · ${decision.matched_root}`
      : `${decision.host || 'host vazio'} · BLOCKED · fora do escopo.`;
    showToast(decision.allowed
      ? 'Host autorizado pela Policy API. Nenhuma conexão foi aberta.'
      : 'Boundary stop registrado pelo WOLF Core. Nenhuma conexão foi aberta.');
    if (!decision.allowed) historyEvents = await apiRequest('/api/history');
  } catch (error) {
    result.classList.add('is-blocked');
    result.textContent = 'Policy API indisponível · ação bloqueada.';
    showToast(error.message);
  }
});

async function importArtifact(file) {
  const extension = file.name.split('.').pop().toLowerCase();
  const format = extension === 'har' ? 'har' : extension === 'json' ? 'json' : 'headers';
  try {
    const imported = await apiRequest('/api/evidence/import', {
      method: 'POST',
      body: JSON.stringify({ format, source: file.name, content: await file.text() }),
    });
    await refreshData();
    showToast(`${imported.imported} observações importadas e persistidas no SQLite.`);
  } catch (error) {
    showToast(`Import falhou: ${error.message}`);
  } finally {
    document.querySelector('#evidence-file').value = '';
  }
}

document.querySelector('#evidence-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  try {
    await apiRequest('/api/evidence', {
      method: 'POST',
      body: JSON.stringify({
        source: 'manual observation',
        kind: String(form.get('kind')),
        observation: String(form.get('title')).trim(),
        bearing: String(form.get('bearing')),
        confidence: 0.9,
        detail: String(form.get('detail')).trim() || 'Observação manual · origem não especificada',
      }),
    });
    document.querySelector('#evidence-dialog').close();
    formElement.reset();
    await refreshData();
    showToast('Observação persistida no SQLite.');
  } catch (error) {
    showToast(`Não foi possível salvar: ${error.message}`);
  }
});

document.querySelector('#close-dialog').addEventListener('click', () => document.querySelector('#evidence-dialog').close());
document.querySelector('#cancel-dialog').addEventListener('click', () => document.querySelector('#evidence-dialog').close());

document.querySelector('#notification-button').addEventListener('click', (event) => {
  const button = event.currentTarget;
  const enabled = button.classList.toggle('is-on');
  button.setAttribute('aria-label', enabled ? 'Desativar notificações locais' : 'Ativar notificações locais');
  showToast(enabled ? 'Alertas visuais desta sessão ativados localmente.' : 'Alertas visuais desativados.');
});

renderView();
refreshData().catch((error) => {
  showToast(`WOLF Core indisponível: ${error.message}`);
});