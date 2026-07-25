/* ============================================================
   5. ROUTER + NAV
   ============================================================ */
const NAV = [
  {id:'overview',  key:'nav_overview',  icon:'boxes'},
  {id:'dashboard', key:'nav_patients',  icon:'users'},
  {id:'predict',   key:'nav_predict',   icon:'flask'},
  {id:'cells',     key:'nav_cells',     icon:'boxes'},
  {id:'chromatin', key:'nav_chromatin', icon:'boxes'},
  {id:'protein',   key:'nav_protein',   icon:'dna'},
  {id:'profile',   key:'nav_profile',   icon:'users'},
  {id:'settings',  key:'nav_settings',  icon:'settings'},
];
function renderNav(){
  const html = NAV.map(n=>`<a class="navlink ${(S.route===n.id || (S.route==='patient' && n.id==='dashboard'))?'active':''}" data-go="${n.id}" href="#">${ICON[n.icon]}<span>${t(n.key)}</span></a>`).join('');
  const top = document.getElementById('topNav');
  if (top) top.innerHTML = html;
}
function go(route){
  S.route = route;
  const inApp = !['landing','login'].includes(route);
  document.getElementById('screen-landing').hidden = route!=='landing';
  document.getElementById('screen-login').hidden   = route!=='login';
  document.getElementById('shell').hidden          = !inApp;
  window.scrollTo(0,0);
  renderNav(); renderRoute();
}
document.addEventListener('click', e=>{
  const go_ = e.target.closest('[data-go]');
  if(go_){ e.preventDefault(); go(go_.dataset.go); }
});


/* ============================================================
   5b. OVERVIEW  +  PROFILE   (كل الأرقام مشتقّة من S.patients)
   ============================================================ */
const RUNNING_SET = ['pending','predicting_dnase','generating_hic','running'];

function computeStats(){
  const patients = S.patients || [];
  const tests = patients.flatMap(p => p.genomic_inputs || []);
  const by = st => tests.filter(t => st.includes(t.status)).length;
  const completed = by(['completed']), failed = by(['failed']), running = by(RUNNING_SET);
  return {
    patients: patients.length,
    tests: tests.length,
    completed, running, failed,
    success: tests.length ? Math.round(completed / tests.length * 100) : 0,
    avg: patients.length ? (tests.length / patients.length).toFixed(1) : '0.0',
    recent: tests.slice().sort((a,b)=> new Date(b.created_at) - new Date(a.created_at)).slice(0,5)
      .map(t => ({...t, patient: (patients.find(p => (p.genomic_inputs||[]).some(x=>x.id===t.id))||{}).name || '' }))
  };
}

function statusPill(st){
  const cls = st==='completed' ? 'ok' : st==='failed' ? 'err' : 'run';
  return `<span class="pill ${cls}">${t('status_'+st) || st}</span>`;
}

function renderOverview(view){
  if (S.patientsLoading){
    view.innerHTML = `<div class="wrap"><div class="head" style="margin-bottom:2rem"><h1>${t('ov_title')}</h1><p>${t('ov_subtitle')}</p></div>
      <div class="stat-grid">${[0,1,2,3].map(()=>`<div class="skel" style="height:104px;border-radius:16px"></div>`).join('')}</div>
      <div class="skel" style="height:220px;border-radius:16px;margin-top:2rem"></div></div>`;
    return;
  }
  const k = computeStats();
  const stat = (label, value, iconKey) => `<div class="stat-card">
      <div><div class="stat-label">${label}</div><div class="stat-value">${value}</div></div>
      <div class="stat-ic">${ICON[iconKey]}</div>
    </div>`;

  view.innerHTML = `<div class="wrap">
    <div class="head" style="margin-bottom:2rem"><h1>${t('ov_title')}</h1><p>${t('ov_subtitle')}</p></div>

    <div class="stat-grid">
      ${stat(t('ov_patients'),  k.patients,  'users')}
      ${stat(t('ov_tests'),     k.tests,     'flask')}
      ${stat(t('ov_completed'), k.completed, 'check')}
      ${stat(t('ov_running'),   k.running,   'retry')}
    </div>

    <section class="panel" style="margin-top:2rem">
      <div class="panel-head">
        <h2>${t('ov_recent')}</h2>
        <a class="link-arrow" data-go="dashboard" href="#"><span>${t('nav_patients')}</span>${ICON.chevron}</a>
      </div>
      ${k.recent.length ? `<ul class="rlist">${k.recent.map(r=>`
        <li>
          <div class="rl-main">
            <div class="rl-title">${esc(r.patient||'—')} — <span class="mono">${esc(r.chromosome||'—')}:${fmtNum(r.start_pos)}–${fmtNum(r.end_pos)}</span></div>
            <div class="rl-sub">${esc(r.cell_type||'—')} · ${new Date(r.created_at).toLocaleString(locale==='ar'?'ar-EG':'en-US')}</div>
          </div>
          ${statusBadge(r.status)}
        </li>`).join('')}</ul>`
      : `<div class="panel-empty">${t('no_patients_title')}</div>`}
    </section>
  </div>`;
}

function renderProfile(view){
  const role = USER.is_superuser ? t('pr_superuser') : t('pr_staff');
  const row = (icon, label, value, mono) => `<div class="card between" style="padding:1.15rem">
      <div class="row" style="gap:.9rem">
        <span style="opacity:.7">${icon}</span>
        <div><p class="sm-t muted">${label}</p>
          <p style="font-weight:500;margin-top:.1rem;${mono?'font-family:var(--mono,monospace)':''}">${value}</p></div>
      </div>
    </div>`;

  view.innerHTML = `<div class="wrap" style="max-width:760px">
    <div class="head" style="margin-bottom:2rem"><h1>${t('pr_title')}</h1><p>${t('pr_subtitle')}</p></div>

    <div class="card" style="padding:1.75rem;display:flex;align-items:center;gap:1.25rem;margin-bottom:1.25rem">
      <div style="width:72px;height:72px;border-radius:50%;display:grid;place-items:center;
        background:var(--primary);color:var(--primary-foreground);font-size:1.8rem;font-weight:600">
        ${(USER.username[0]||'?').toUpperCase()}
      </div>
      <div><p style="font-size:1.35rem;font-weight:600">${USER.username}</p>
        <p class="sm-t muted">${role}</p></div>
    </div>

    <div class="stack" style="gap:.85rem">
      ${row(ICON.users, t('pr_username'), USER.username, true)}
      ${row(ICON.file,  t('pr_email'),    USER.email,    true)}
      ${row(ICON.check, t('pr_role'),     role,          false)}
      ${row(ICON.clock, t('pr_joined'),   new Date(USER.date_joined).toLocaleDateString(), true)}
    </div>

    

    <div class="card between" style="padding:1.25rem;margin-top:1.5rem">
      <div>
        <p style="font-weight:500">${t('pw_title')}</p>
        <p class="sm-t muted" style="margin-top:.15rem">${t('pw_desc')}</p>
      </div>
      <button class="btn outline" id="pwOpen">${t('pw_submit')}</button>
    </div>
  </div>`;

  const openBtn = view.querySelector('#pwOpen');
  if (openBtn) openBtn.onclick = openPasswordModal;
}

/* ── منبثق تغيير كلمة المرور  ── */
function closePasswordModal(){
  const m = document.getElementById('pwModal');
  if (m) m.remove();
}
function openPasswordModal(){
  closePasswordModal();
  const el = document.createElement('div');
  el.className = 'ct-modal-bg';
  el.id = 'pwModal';
  el.innerHTML = `
    <div class="ct-modal" role="dialog" aria-modal="true" style="width:min(480px,100%)">
      <div class="ct-modal-hd">
        <div style="font-weight:600">${t('pw_title')}</div>
        <button class="icon-btn" id="pwClose" aria-label="${t('cells_cancel')}">${ICON.x||'✕'}</button>
      </div>
      <div class="ct-modal-bd">
        <p class="sm-t muted" style="margin-bottom:1.1rem">${t('pw_desc')}</p>
        <div class="stack" style="gap:.9rem">
          <div class="field"><label class="label" for="pwOld">${t('pw_old')}</label>
            <input id="pwOld" class="input" type="password" autocomplete="current-password" placeholder="${t('pw_old_ph')}"></div>
          <div class="field"><label class="label" for="pwNew">${t('pw_new')}</label>
            <input id="pwNew" class="input" type="password" autocomplete="new-password" placeholder="${t('pw_new_ph')}"></div>
          <div class="field"><label class="label" for="pwConfirm">${t('pw_confirm')}</label>
            <input id="pwConfirm" class="input" type="password" autocomplete="new-password" placeholder="${t('pw_confirm_ph')}"></div>
        </div>
        <div style="margin-top:1.25rem;display:flex;gap:.5rem;justify-content:flex-end">
          <button class="btn outline" id="pwCancel">${t('cells_cancel')}</button>
          <button class="btn" id="pwSubmit">${t('pw_submit')}</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(el);

  el.addEventListener('click', e=>{ if(e.target===el) closePasswordModal(); });
  el.querySelector('#pwClose').onclick  = closePasswordModal;
  el.querySelector('#pwCancel').onclick = closePasswordModal;
  // إغلاق بمفتاح Escape
  const onEsc = e => { if(e.key==='Escape'){ closePasswordModal(); document.removeEventListener('keydown', onEsc); } };
  document.addEventListener('keydown', onEsc);
  setTimeout(()=>{ const f=el.querySelector('#pwOld'); if(f) f.focus(); }, 50);

  const btn = el.querySelector('#pwSubmit');
  el.querySelectorAll('input').forEach(inp=>{
    inp.addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); btn.click(); } });
  });
  btn.onclick = async () => {
    const oldp = (el.querySelector('#pwOld')||{}).value || '';
    const newp = (el.querySelector('#pwNew')||{}).value || '';
    const conf = (el.querySelector('#pwConfirm')||{}).value || '';

    if (!oldp || !newp || !conf)  return toast(t('pw_err_required'), 'error');
    if (newp.length < 6)          return toast(t('pw_err_short'),    'error');
    if (newp !== conf)            return toast(t('pw_err_match'),    'error');
    if (newp === oldp)            return toast(t('pw_err_same'),     'error');

    const label = btn.textContent;
    btn.disabled = true; btn.textContent = t('pw_saving');
    try {
      await api.post('/auth/change-password/', { old_password: oldp, new_password: newp });
      toast(t('pw_ok'));
      closePasswordModal();
    } catch (e) {
      const data = e.response && e.response.data;
      const msg = data && (data.message || (data.old_password && data.old_password[0]) || (data.new_password && data.new_password[0]));
      if (e.response && e.response.status === 400) toast(msg || t('pw_err_wrong'), 'error');
      else { console.error('[change-password]', data || e); toast(t('pw_err_generic'), 'error'); }
      btn.disabled = false; btn.textContent = label;
    }
  };
}

function renderRoute(){
  clearScenes();
  if (S.route==='landing'){ renderLanding(); return; }
  if (S.route==='login') return;
  const view = document.getElementById('view');
  ({overview:renderOverview, profile:renderProfile, dashboard:renderPatients, predict:renderPredict, settings:renderSettings, cells:renderCellTypes,
    chromatin:renderChromatin, protein:renderProtein, patient:renderPatientDetail}[S.route] || renderPatients)(view);
}
