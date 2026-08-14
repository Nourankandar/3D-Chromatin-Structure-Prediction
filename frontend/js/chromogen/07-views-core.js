/* ============================================================
   6. LANDING
   صفحة الترحيب، قائمة المرضى، بطاقة كل مريض وتفاصيله.
   ============================================================ */
const STAGES = ['stage_ingest','stage_preprocess','stage_predict','stage_reconstruct','stage_report'];


function injectHeroDots(host){
  if(!host) return;
  let html='';
  for(let i=0;i<26;i++){
    const left=(i*37)%100, top=(i*53)%100, dur=6+((i*7)%10), size=2+(i%4), delay=((i%6)*0.4).toFixed(1);
    html+=`<span style="left:${left}%;top:${top}%;width:${size}px;height:${size}px;--dur:${dur}s;--delay:${delay}s"></span>`;
  }
  host.innerHTML=html;
}

/* المزدوج DNA شكل*/
const DNA_GLYPH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 2c0 5 10 5 10 10S7 17 7 22"/><path d="M17 2c0 5-10 5-10 10s10 5 10 10"/><path d="M9 5.5h6M10.5 12h3M9.5 18.5h5" stroke-width="1"/></svg>`;

/* أشكال  صغيرة مبعثرة تطفو وتخبو DNA */
function injectDnaField(host, count=14){
  if(!host) return;
  let html='';
  for(let i=0;i<count;i++){
    const left=(i*61+8)%100, top=(i*41+6)%100, dur=8+((i*5)%8), size=22+(i%3)*7, delay=((i%5)*0.7).toFixed(1), turn=5+((i*3)%7);
    html+=`<span class="dna-float" style="left:${left}%;top:${top}%;--dur:${dur}s;--delay:${delay}s;--sz:${size}px;--turn:${turn}s">${DNA_GLYPH}</span>`;
  }
  host.innerHTML=html;
}

/*  (تلاشٍ + انزلاق) */
function observeReveals(root){
  const els = (root||document).querySelectorAll('.reveal:not(.in)');
  if(!('IntersectionObserver' in window)){ els.forEach(e=>e.classList.add('in')); return; }
  const io = new IntersectionObserver((ents)=>{ ents.forEach(en=>{ if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); } }); }, {threshold:0.12, rootMargin:'0px 0px -8% 0px'});
  els.forEach(e=>io.observe(e));
}

function renderLanding(){
  applyStaticText();
  document.getElementById('landingStages').innerHTML = STAGES.map((s,i)=>`
    <div class="stage reveal" style="transition-delay:${(i*0.08).toFixed(2)}s"><span class="mono xs muted">0${i+1}</span><p style="margin-top:.5rem;font-weight:500">${t(s)}</p></div>`).join('');
  injectHeroDots(document.getElementById('heroDots'));
  createScene(document.getElementById('helixCanvas'), buildHelix(), {dist:11});
  observeReveals(document.getElementById('screen-landing'));
}

/* ============================================================
   7. PATIENTS
   ============================================================ */
function statusBadge(s){
  const g = statusGroup(s);
  const pulse = g==='running' ? 'pulse' : '';
  return `<span class="badge ${g}" data-status="${s}" title="${statusLabel(s)}">
    <span class="dot ${pulse}"></span>${statusLabel(s)}</span>`;
}

function renderPatients(view){
  let body;
  if (S.patientsLoading){
    body = `<div class="pgrid">${[0,1,2].map(()=>`<div class="skel" style="height:186px;border-radius:16px"></div>`).join('')}</div>`;
  } else if (S.patientsError){
    body = `<div class="empty" style="border-style:solid;border-color:color-mix(in srgb,var(--destructive) 30%,transparent);background:color-mix(in srgb,var(--destructive) 5%,transparent)">
      <div class="ico" style="background:color-mix(in srgb,var(--destructive) 12%,transparent);color:var(--destructive)">${ICON.alert}</div>
      <p style="margin-top:1rem;font-weight:500">${t('patients_error')}</p>
      <button class="btn outline" style="margin-top:1rem" id="reloadBtn">${ICON.retry}<span>${t('retry')}</span></button></div>`;
  } else if (!S.patients.length){
    body = `<div class="empty">
      <div class="ico">${ICON.users}</div>
      <p style="margin-top:1rem;font-weight:500">${t('no_patients_title')}</p>
      <p class="sm-t muted" style="margin-top:.25rem;max-width:34ch">${t('no_patients_desc')}</p>
      <button class="btn" style="margin-top:1.25rem" data-add>${ICON.plus}<span>${t('add_patient')}</span></button></div>`;
  } else {
    body = `<div class="pgrid">${S.patients.map(patientCard).join('')}</div>`;
  }

  const totalLbl = locale==='ar' ? ('المجموع: '+fmtNum(S.patients.length)) : (fmtNum(S.patients.length)+' total');
  view.innerHTML = `<div class="wrap">
    <div class="between" style="margin-bottom:2rem">
      <div class="head"><h1>${t('patients_title')}</h1><p>${totalLbl}</p></div>
      <button class="btn" data-add>${ICON.plus}<span>${t('add_patient')}</span></button>
    </div>
    ${body}
  </div>`;

  view.querySelector('#reloadBtn')?.addEventListener('click', loadPatients);
  view.querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>openPatientDialog(null));
  view.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{ S.activePatient=+b.dataset.view; go('patient'); });
  view.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{
    const p = S.patients.find(x=>x.id===+b.dataset.del);
    if(!await confirmDialog(t('delete_patient_confirm_title'), t('delete_patient_confirm_desc'))) return;
    try {
      await api.del(`/patients/${p.id}/`);
      S.patients = S.patients.filter(x=>x.id!==p.id); renderRoute(); toast(t('toast_patient_deleted'));
    } catch(err){
      console.error('[patient delete]', err.response ? err.response.data : err);
      toast('تعذّر حذف المريض','error');
    }
  });
}
const allTests = () => S.patients.flatMap(p=>p.genomic_inputs);

function patientCard(p){
  const g = p.genomic_inputs || [];
  const testsWord = locale==='ar' ? 'تحليل' : 'tests';
  const viewWord  = locale==='ar' ? 'عرض'  : 'View';
  return `<article class="pcard fade">
    <div class="pcard-top">
      <div class="pcard-id">
        <span class="avatar">${esc(p.name.slice(0,2).toUpperCase())}</span>
        <div style="min-width:0">
          <div class="pcard-name">${esc(p.name)}</div>
          <div class="pcard-mrn mono">${esc(p.mrn)}</div>
        </div>
      </div>
      <button class="btn ghost icon sm" data-del="${p.id}" title="${t('delete_patient')}">${ICON.trash}</button>
    </div>
    <div class="pcard-fields">
      <div><div class="k">${t('patient_gender')}</div><div class="v">${t('gender_'+p.gender)}</div></div>
      <div><div class="k">${t('patient_dob')}</div><div class="v mono">${fmtDate(p.dob)}</div></div>
    </div>
    <div class="pcard-foot">
      <span class="muted sm-t">${fmtNum(g.length)} ${testsWord}</span>
      <a class="link-arrow" data-view="${p.id}" href="#"><span>${viewWord}</span>${ICON.chevron}</a>
    </div>
  </article>`;
}

/* صفحة تفاصيل المريض  */
function renderPatientDetail(view){
  const p = (S.patients||[]).find(x=>x.id===S.activePatient);
  if (!p){ go('dashboard'); return; }
  const g = p.genomic_inputs || [];
  view.innerHTML = `<div class="wrap">
    <a class="back-link" data-go="dashboard" href="#">${ICON.back}<span>${t('nav_patients')}</span></a>
    <div class="detail-head">
      <div class="row" style="gap:1rem;min-width:0">
        <span class="avatar" style="width:56px;height:56px;font-size:1.1rem;flex:none">${esc(p.name.slice(0,2).toUpperCase())}</span>
        <div style="min-width:0">
          <h1 style="font-size:1.6rem;font-weight:600">${esc(p.name)}</h1>
          <div class="muted" style="font-size:.85rem;margin-top:.2rem"><span class="mono">${esc(p.mrn)}</span> · ${t('gender_'+p.gender)} · <span class="mono">${fmtDate(p.dob)}</span></div>
        </div>
      </div>
      <div class="row">
        <button class="btn outline sm" data-edit-patient>${ICON.pencil}<span>${t('edit_patient')}</span></button>
        <button class="btn danger sm" data-del-patient>${ICON.trash}<span>${t('delete_patient')}</span></button>
      </div>
    </div>
    <section class="panel" style="margin-top:1.5rem">
      <div class="panel-head"><h2>${t('view_tests')}</h2><span class="pill">${fmtNum(g.length)}</span></div>
      ${g.length ? `<div class="panel-body"><div class="stack" style="gap:.75rem">${g.map(testRow).join('')}</div></div>`
        : `<div class="panel-empty">${ICON.flask}<span style="margin-inline-start:.5rem">${t('no_tests_title')}</span></div>`}
    </section>
  </div>`;

  view.querySelector('[data-edit-patient]')?.addEventListener('click', ()=>openPatientDialog(p));
  view.querySelector('[data-del-patient]')?.addEventListener('click', async()=>{
    if(!await confirmDialog(t('delete_patient_confirm_title'), t('delete_patient_confirm_desc'))) return;
    try { await api.del(`/patients/${p.id}/`); toast(t('toast_patient_deleted')); go('dashboard'); }
    catch(err){ console.error('[patient delete]', err.response?err.response.data:err); toast('تعذّر حذف المريض','error'); }
  });
  view.querySelectorAll('[data-open-test]').forEach(b=>b.onclick=()=>{ S.activeTest=+b.dataset.openTest; go('chromatin'); });
  view.querySelectorAll('[data-retry-test]').forEach(b=>b.onclick=()=>{ toast(t('toast_retry_started')||'أعِد رفع التحليل من شاشة «طلب تحليل جيني»'); go('predict'); });
  view.querySelectorAll('[data-del-test]').forEach(b=>b.onclick=async()=>{
    if(!await confirmDialog(t('delete_test_confirm_title'), t('delete_test_confirm_desc'))) return;
    const id = +b.dataset.delTest;
    try { await api.del(`/genomics/${id}/`); p.genomic_inputs = p.genomic_inputs.filter(x=>x.id!==id); renderRoute(); toast(t('toast_test_deleted')); }
    catch(err){ console.error('[test delete]', err.response?err.response.data:err); toast('تعذّر حذف التحليل','error'); }
  });
}
function testRow(g){
  return `<div class="test fade">
    <div>
      <div class="row"><span class="mono sm-t">${esc(g.chromosome||'—')}</span>
        ${g.start_pos!=null?`<span class="xs muted">${fmtNum(g.start_pos)} – ${fmtNum(g.end_pos)}</span>`:''}</div>
      <div class="xs muted" style="margin-top:.2rem">${fmtDateTime(g.created_at)} · ${esc(g.cell_type||'—')}</div>
    </div>
    <div class="row">
      ${statusBadge(g.status)}
      ${g.status==='completed'?`<button class="btn secondary sm" data-open-test="${g.id}">${ICON.boxes}<span>${t('open_chromatin')}</span></button>`:''}
      ${g.status==='failed'?`<button class="btn secondary sm" data-retry-test="${g.id}">${ICON.retry}<span>${t('retry')}</span></button>`:''}
      <button class="btn danger icon sm" data-del-test="${g.id}" title="${t('delete_test')}">${ICON.trash}</button>
    </div>
  </div>`;
}

/* patient dialog */
function openPatientDialog(patient){
  S.editing = patient || null;
  const dlg = document.getElementById('patientDialog');
  applyStaticText(dlg);
  document.getElementById('pdTitle').textContent = patient ? t('edit_patient') : t('add_patient');
  pdName.value = patient?.name ?? ''; pdMrn.value = patient?.mrn ?? '';
  pdGender.value = patient?.gender ?? 'male'; pdDob.value = patient?.dob ?? '';
  dlg.showModal();
}
document.getElementById('patientForm').addEventListener('submit', async e=>{
  const input = {name:pdName.value.trim(), mrn:pdMrn.value.trim(), gender:pdGender.value, dob:pdDob.value};
  if(!input.name || !input.mrn || !input.dob){ e.preventDefault(); return; }
  const payload = { name:input.name, mrn:input.mrn, gender:(GENDER_TO_API[input.gender]||'O'), dob:input.dob };
  const editing = S.editing; S.editing = null;
  try {
    if (editing){ await api.patch(`/patients/${editing.id}/`, payload); toast(t('toast_patient_updated')); }
    else        { await api.post('/patients/', payload);                toast(t('toast_patient_added')); }
    await loadPatients();
  } catch(err){
    console.error('[patient save]', err.response ? err.response.data : err);
    toast('تعذّر حفظ المريض — تحقّق من البيانات (رقم MRN مكرّر؟)','error');
  }
});
document.getElementById('patientDialog').querySelector('[data-close]').onclick = () => document.getElementById('patientDialog').close();
