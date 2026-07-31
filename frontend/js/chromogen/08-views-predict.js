/* ============================================================
   8. NEW PREDICTION (+ protein search)
    نموذج تحليل جديد 
  (رفع FASTA، اختيار نوع خلية، بحث بروتين)
    وشاشة الإعدادات وأنواع الخلايا
   ============================================================ */
const PF = {patient:'', cell:'', chrom:'', start:'', end:'', file:null, submitting:false, started:false, rejected:false};


function renderPredict(view){
  let form;
  if (S.patientsLoading){
    form = `<div class="card" style="padding:1.5rem"><div class="stack">
      ${'<div class="skel" style="height:56px"></div>'.repeat(4)}<div class="skel" style="height:110px"></div><div class="skel" style="height:40px"></div>
    </div></div>`;
  } else if (!S.patients.length){
    form = `<div class="empty">
      <div class="ico">${ICON.users}</div>
      <p style="margin-top:1rem;font-weight:500">${t('predict_no_patients_title')}</p>
      <p class="sm-t muted" style="margin-top:.25rem;max-width:34ch">${t('predict_no_patients_desc')}</p>
      <button class="btn" style="margin-top:1.25rem" data-go="dashboard">${ICON.plus}<span>${t('add_patient')}</span></button></div>`;
  } else if (PF.started){
    form = `<div class="empty fade" style="border-style:solid;border-color:color-mix(in srgb,var(--primary) 30%,transparent);background:color-mix(in srgb,var(--primary) 5%,transparent)">
      <div class="ico">${ICON.check}</div>
      <p style="margin-top:1rem;font-weight:500">${t('prediction_running_title')}</p>
      <p class="sm-t muted" style="margin-top:.25rem;max-width:36ch">${t('prediction_running_desc')}</p>
      <div class="row" style="margin-top:1.5rem">
        <button class="btn" data-go="dashboard">${t('view_tests')}</button>
        <button class="btn outline" id="againBtn">${t('start_another')}</button>
      </div></div>`;
  } else {
    form = `<form id="predictForm" class="card" style="padding:1.5rem;display:flex;flex-direction:column;gap:1.25rem">
      <div class="cols2">
        <div class="field"><label class="label" for="pfPatient">${t('field_patient')}</label>
          <select id="pfPatient" class="select"><option value="" disabled ${!PF.patient?'selected':''}>${t('field_patient_ph')}</option>
          ${S.patients.map(p=>`<option value="${p.id}" ${PF.patient==p.id?'selected':''}>${esc(p.name)}</option>`).join('')}</select></div>
        <div class="field"><label class="label" for="pfCell">${t('field_cell_type')}</label>
          <div class="ct-inline">
            <select id="pfCell" class="select"><option value="" disabled ${!PF.cell?'selected':''}>${t('field_cell_type_ph')}</option>
            ${CELL_TYPES.map(c=>`<option value="${c.id}" ${PF.cell==c.id?'selected':''}>${c.name}</option>`).join('')}</select>
            <button type="button" class="icon-btn" id="pfCellAdd" title="${t('cells_manage')}" aria-label="${t('cells_manage')}">${ICON.plus||'+'}</button>
          </div></div>
      </div>

      <div class="field"><label class="label" for="pfChrom">${t('field_chromosome')}</label>
        <input id="pfChrom" class="input mono" placeholder="${t('field_chromosome_ph')}" value="${esc(PF.chrom)}"></div>

      <div class="cols2">
        <div class="field"><label class="label" for="pfStart">${t('field_start')}</label>
          <input id="pfStart" class="input mono" type="number" min="0" value="${esc(PF.start)}"></div>
        <div class="field"><label class="label" for="pfEnd">${t('field_end')}</label>
          <input id="pfEnd" class="input mono" type="number" min="0" value="${esc(PF.end)}"></div>
      </div>

      <p id="rangeErr" class="xs" style="color:var(--destructive);display:flex;gap:.4rem;align-items:center;margin-top:-.75rem" hidden>
        <span data-icon="alert"></span>${t('invalid_range')}</p>

      <!-- Derived from the region. Never typed by hand. -->
      <div id="hintBox"></div>

      <div class="field"><span class="label">${t('field_fasta')}</span>
        ${PF.file ? `<div class="card row" style="padding:.75rem">
            <span style="width:36px;height:36px;border-radius:10px;display:grid;place-items:center;background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary)">${ICON.file}</span>
            <div style="flex:1;min-width:0"><p class="sm-t" style="font-weight:500">${esc(PF.file.name)}</p><p class="xs muted">${fmtNum(Math.max(1,Math.round(PF.file.size/1024)))} KB</p></div>
            <button type="button" class="btn ghost icon sm" id="rmFile" title="${t('fasta_remove')}">${ICON.x}</button>
          </div>`
        : `<div class="drop ${PF.rejected?'bad':''}" id="drop">
            <div class="ico">${ICON.upload}</div>
            <p class="sm-t muted">${t('fasta_drop')} <button type="button" class="linkbtn" id="pickFile">${t('fasta_choose')}</button></p>
            <p class="xs muted">${t('fasta_hint')}</p>
          </div>`}
        <input id="fileInput" type="file" accept=".fasta,.fa,.txt" hidden>
        ${PF.rejected ? `<p class="xs" style="color:var(--destructive);display:flex;gap:.4rem;align-items:center">${ICON.alert}${t('fasta_rejected')}</p>`:''}
      </div>

      <button class="btn lg" type="submit" id="submitBtn" disabled style="width:100%">
        ${PF.submitting?`<span class="spin"></span><span>${t('prediction_started_loading')}</span>`:`<span>${t('start_prediction')}</span>`}
      </button>
      <p class="xs muted" style="display:flex;gap:.4rem;align-items:center;justify-content:center">${ICON.clock}${t('background_note')}</p>
    </form>`;
  }

  view.innerHTML = `<div class="wrap">
    <div class="head" style="margin-bottom:2rem"><h1>${t('predict_title')}</h1><p>${t('predict_subtitle')}</p></div>
    <div class="split">
      <section style="min-width:0">${form}</section>
      <aside>
        <div class="card" style="padding:1.25rem">
          <p class="sm-t" style="font-weight:500">${t('pipeline_reference')}</p>
          <ol class="rail" style="margin-top:1rem">
            ${STAGES.map((s,i)=>`<li><div class="col"><span class="num mono">${i+1}</span>${i<4?'<span class="line"></span>':''}</div><p>${t(s)}</p></li>`).join('')}
          </ol>
          <p class="xs muted" style="border-top:1px solid var(--border);padding-top:1rem">${t('pipeline_note')}</p>
        </div>
      </aside>
    </div>
  </div>`;

  bindPredict(view);
}


function updateDerived(view){
  const s = parseInt(PF.start,10), e = parseInt(PF.end,10);
  const both = Number.isFinite(s) && Number.isFinite(e), valid = both && e > s;

  const err = view.querySelector('#rangeErr');
  if (err){ err.hidden = !(both && !valid); err.querySelector('[data-icon]').innerHTML = ICON.alert; }
  view.querySelector('#pfEnd')?.setAttribute('aria-invalid', String(both && !valid));

  const box = view.querySelector('#hintBox');
  if (box){
    box.innerHTML = valid ? `<div class="alert info fade" style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
      <div style="grid-column:1/-1;display:flex;gap:.4rem;align-items:center;color:var(--primary);font-size:.75rem;font-weight:500">${ICON.info}${t('hint_title')}</div>
      <div><p class="xs muted">${t('hint_points')}</p><p class="mono" style="font-size:1.15rem;margin-top:.15rem">${fmtNum(estPoints(s,e))}</p></div>
      <div><p class="xs muted">${t('hint_region')}</p><p class="mono" style="font-size:1.15rem;margin-top:.15rem">${fmtRegion(e-s)}</p></div>
    </div>` : '';
  }

  const btn = view.querySelector('#submitBtn');
  if (btn) btn.disabled = !(PF.patient && PF.cell && PF.chrom.trim() && valid && PF.file) || PF.submitting;
}

function bindPredict(view){
  const on = (id, ev, fn) => view.querySelector('#'+id)?.addEventListener(ev, fn);
  on('pfPatient','change', e=>{ PF.patient=e.target.value; updateDerived(view); });
  on('pfCell','change',    e=>{ PF.cell=e.target.value; updateDerived(view); });
  on('pfCellAdd','click',  ()=>{ openCellModal(()=>renderPredict(view)); });
  on('pfChrom','input',    e=>{ PF.chrom=e.target.value; updateDerived(view); });
  on('pfStart','input',    e=>{ PF.start=e.target.value; updateDerived(view); });
  on('pfEnd','input',      e=>{ PF.end=e.target.value; updateDerived(view); });
  on('againBtn','click',   ()=>{ Object.assign(PF,{chrom:'',start:'',end:'',file:null,started:false,rejected:false}); renderRoute(); });
  on('rmFile','click',     ()=>{ PF.file=null; PF.rejected=false; renderRoute(); });
  on('pickFile','click',   ()=> view.querySelector('#fileInput').click());
  on('fileInput','change', e=> acceptFile(e.target.files[0]));

  const drop = view.querySelector('#drop');
  if(drop){
    drop.addEventListener('dragover', e=>{ e.preventDefault(); drop.classList.add('over'); });
    drop.addEventListener('dragleave', ()=> drop.classList.remove('over'));
    drop.addEventListener('drop', e=>{ e.preventDefault(); drop.classList.remove('over'); acceptFile(e.dataTransfer.files[0]); });
  }

  view.querySelector('#predictForm')?.addEventListener('submit', async e=>{
    e.preventDefault();
    PF.submitting = true; renderRoute();

    
    const fd = new FormData();
    fd.append('patient_id',   PF.patient);
    fd.append('cell_type_id', PF.cell);
    fd.append('chromosome',   PF.chrom.trim());
    fd.append('start_pos',    PF.start);
    fd.append('end_pos',      PF.end);
    fd.append('fasta_file',   PF.file);

    try {
      
      const res = await api.post('/genomics/run-test/', fd);
      const inputId = res.input_data_id;
      PF.submitting=false; PF.started=true; renderRoute();
      toast(t('prediction_started'));
      await loadPatients();            // ليظهر التحليل الجديد في لوحة المرضى
      if (inputId) pollTestStatus(inputId);   // متابعة الحالة حتى الاكتمال
    } catch(err){
      console.error('[run-test]', err.response ? err.response.data : err);
      PF.submitting=false; renderRoute();
      toast('تعذّر رفع التحليل — تحقّق من الحقول والملف','error');
    }
  });

  updateDerived(view);
}

function acceptFile(f){
  if(!f) return;
  const ok = /\.(fasta|fa|txt)$/i.test(f.name);
  PF.file = ok ? f : null; PF.rejected = !ok;
  renderRoute();
  if(!ok) toast(t('fasta_rejected'),'error');
}




/* ============================================================
   أنواع الخلايا — صفحة مستقلة + منبثق مشترك 
   ============================================================ */
let CT_EDIT = null;  


function cellFormHTML(prefix){
  const ed = CT_EDIT ? CELL_TYPES.find(c=>c.id===CT_EDIT) : null;
  return `
  <div class="ct-form-grid">
    <div class="field"><label class="label" for="${prefix}Name">${t('cells_name')}</label>
      <input id="${prefix}Name" class="input" placeholder="${t('cells_name_ph')}" value="${ed?esc(ed.name):''}"></div>
    <div class="field"><label class="label" for="${prefix}Eid">${t('cells_eid')}</label>
      <input id="${prefix}Eid" class="input mono" type="number" min="0" max="163" placeholder="${t('cells_eid_ph')}" value="${ed&&ed.eid!=null?ed.eid:''}"></div>
  </div>
  <div class="field" style="margin-top:.9rem"><label class="label" for="${prefix}Desc">${t('cells_desc_f')}</label>
    <input id="${prefix}Desc" class="input" placeholder="${t('cells_desc_ph')}" value="${ed?esc(ed.desc):''}"></div>
  <p class="xs muted" style="margin-top:.4rem">${t('cells_hint')}</p>
  <div style="margin-top:1rem;display:flex;gap:.5rem">
    <button class="btn" data-ct-save="${prefix}">${CT_EDIT?t('cells_update'):t('cells_save')}</button>
    ${CT_EDIT?`<button class="btn outline" data-ct-cancel="${prefix}">${t('cells_cancel')}</button>`:''}
  </div>`;
}

/* قائمة الأنواع المضافة */
function cellListHTML(){
  if(!CELL_TYPES.length) return `<div class="ct-empty">${t('cells_empty')}</div>`;
  return CELL_TYPES.map(c=>`
    <div class="ct-row">
      <div class="ct-ic">${c.eid!=null?c.eid:'—'}</div>
      <div class="ct-main">
        <div class="ct-name">${esc(c.name)}</div>
        <div class="ct-desc">${c.desc?esc(c.desc)+' · ':''}Enformer track ${c.eid!=null?c.eid:'—'}</div>
      </div>
      <div class="ct-acts">
        <button class="icon-btn" data-ct-edit="${c.id}" aria-label="${t('cells_update')}">${ICON.edit||'✎'}</button>
        <button class="icon-btn danger" data-ct-del="${c.id}" aria-label="${t('cells_deleted')}">${ICON.trash||'🗑'}</button>
      </div>
    </div>`).join('');
}

/* الصفحة المستقلة */
function renderCellTypes(view){
  view.innerHTML = `
  <div class="wrap" style="max-width:1100px">
    <div class="head" style="margin-bottom:2rem"><h1>${t('cells_title')}</h1><p>${t('cells_desc')}</p></div>
    <div class="stack">
      <div class="card" style="padding:1.25rem">
        <p style="font-weight:500;margin-bottom:.9rem">${CT_EDIT?t('cells_update'):t('cells_add')}</p>
        ${cellFormHTML('ctp')}
      </div>
      <div class="card">
        <div class="between" style="padding:1rem 1.25rem;border-bottom:1px solid var(--border)">
          <div style="font-weight:500">${t('cells_list')}</div><span class="chip">${CELL_TYPES.length}</span>
        </div>
        <div id="ctList">${cellListHTML()}</div>
      </div>
    </div>
  </div>`;
  bindCellActions(view, ()=>renderCellTypes(view));
}

/* المنبثق — نفس المحتوى، فوق أي شاشة */
function openCellModal(onDone){
  closeCellModal();
  CT_EDIT = null;
  const el = document.createElement('div');
  el.className = 'ct-modal-bg';
  el.id = 'ctModal';
  el.innerHTML = `
    <div class="ct-modal" role="dialog" aria-modal="true">
      <div class="ct-modal-hd">
        <div style="font-weight:600">${t('cells_manage')}</div>
        <button class="icon-btn" data-ct-close aria-label="${t('cells_cancel')}">${ICON.x||'✕'}</button>
      </div>
      <div class="ct-modal-bd" id="ctModalBody">
        ${cellFormHTML('ctm')}
        <div class="ct-divider"></div>
        <div class="between" style="margin-bottom:.5rem">
          <div style="font-weight:500;font-size:.88rem">${t('cells_list')}</div><span class="chip">${CELL_TYPES.length}</span>
        </div>
        <div class="ct-list-box">${cellListHTML()}</div>
      </div>
    </div>`;
  document.body.appendChild(el);
  el.addEventListener('click', e=>{ if(e.target===el) closeCellModal(); });
  const refresh = ()=>{
    const body = document.getElementById('ctModalBody');
    if(!body) return;
    body.innerHTML = `${cellFormHTML('ctm')}
      <div class="ct-divider"></div>
      <div class="between" style="margin-bottom:.5rem">
        <div style="font-weight:500;font-size:.88rem">${t('cells_list')}</div><span class="chip">${CELL_TYPES.length}</span>
      </div>
      <div class="ct-list-box">${cellListHTML()}</div>`;
    bindCellActions(el, refresh, onDone);
  };
  bindCellActions(el, refresh, onDone);
}
function closeCellModal(){
  const m = document.getElementById('ctModal');
  if(m) m.remove();
  CT_EDIT = null;
}


function bindCellActions(root, refresh, onDone){
  root.querySelectorAll('[data-ct-close]').forEach(b=>b.onclick=()=>{ closeCellModal(); if(onDone) onDone(); });

  root.querySelectorAll('[data-ct-cancel]').forEach(b=>b.onclick=()=>{ CT_EDIT=null; refresh(); });

  root.querySelectorAll('[data-ct-edit]').forEach(b=>b.onclick=()=>{
    CT_EDIT = Number(b.dataset.ctEdit); refresh();
  });

  root.querySelectorAll('[data-ct-del]').forEach(b=>b.onclick=async ()=>{
    const id = Number(b.dataset.ctDel);
    if(!confirm(t('cells_confirm_del'))) return;
    try{
      await deleteCellType(id);
      await fetchCellTypes();
      toast(t('cells_deleted'));
      if(CT_EDIT===id) CT_EDIT=null;
      refresh(); if(onDone) onDone();
    }catch(e){
      console.error('[cell-type delete]', e.response? e.response.data : e);
      toast(t('cells_err_save'));
    }
  });

  root.querySelectorAll('[data-ct-save]').forEach(b=>b.onclick=async ()=>{
    const px = b.dataset.ctSave;
    const name = (document.getElementById(px+'Name')||{}).value?.trim() || '';
    const eidRaw = (document.getElementById(px+'Eid')||{}).value ?? '';
    const desc = (document.getElementById(px+'Desc')||{}).value?.trim() || '';
    if(!name){ toast(t('cells_err_name')); return; }
    const eid = Number(eidRaw);
    if(eidRaw==='' || Number.isNaN(eid) || eid<0 || eid>163){ toast(t('cells_err_eid')); return; }
    const payload = { name, target_enformer_id: eid, description: desc };
    try{
      if(CT_EDIT){ await updateCellType(CT_EDIT, payload); toast(t('cells_updated')); }
      else       { await createCellType(payload);          toast(t('cells_added')); }
      CT_EDIT = null;
      await fetchCellTypes();
      refresh(); if(onDone) onDone();
    }catch(e){
      console.error('[cell-type save]', e.response? e.response.data : e);
      toast(t('cells_err_save'));
    }
  });
}

function renderSettings(view){
  const seg = (name, value, options) => `<div class="segmented" role="radiogroup" aria-label="${name}">
    ${options.map(o=>`<button role="radio" aria-checked="${o.v===value}" data-seg="${name}" data-v="${o.v}">${o.icon||''}<span>${o.label}</span></button>`).join('')}
  </div>`;
  view.innerHTML = `<div class="wrap" style="max-width:760px">
    <div class="head" style="margin-bottom:2rem"><h1>${t('settings_title')}</h1></div>
    <div class="stack">
      <div class="card between" style="padding:1.25rem">
        <div><p style="font-weight:500">${t('theme')}</p><p class="sm-t muted" style="margin-top:.15rem">${t('theme_desc')}</p></div>
        ${seg('theme', theme, [{v:'light',label:t('theme_light'),icon:ICON.sun},{v:'dark',label:t('theme_dark'),icon:ICON.moon}])}
      </div>
      <div class="card between" style="padding:1.25rem">
        <div><p style="font-weight:500">${t('language')}</p><p class="sm-t muted" style="margin-top:.15rem">${t('language_desc')}</p></div>
        ${seg('lang', locale, [{v:'ar',label:t('lang_ar'),icon:ICON.lang},{v:'en',label:t('lang_en')}])}
      </div>
      <div class="card" style="padding:1.25rem">
        <div style="margin-bottom:1rem"><p style="font-weight:500">${locale==='ar'?'لون التطبيق':'App color'}</p><p class="sm-t muted" style="margin-top:.15rem">${locale==='ar'?'اختاري لون الثيم المفضّل':'Choose your preferred theme color'}</p></div>
        <div class="accent-grid">
          ${ACCENTS.map(a=>`<button class="accent-chip${a.id===accent?' on':''}" data-accent-id="${a.id}" title="${locale==='ar'?a.label:a.labelEn}" aria-label="${locale==='ar'?a.label:a.labelEn}">
            <span class="accent-dot" style="background:${a.swatch}"></span>
            <span class="accent-name">${locale==='ar'?a.label:a.labelEn}</span>
          </button>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
  view.querySelectorAll('[data-seg]').forEach(b=>b.onclick=()=>{
    if(b.dataset.seg==='theme'){ theme=b.dataset.v; applyTheme(); renderRoute(); }
    else { locale=b.dataset.v; applyLocale(); }
  });
  view.querySelectorAll('[data-accent-id]').forEach(b=>b.onclick=()=>{
    accent=b.dataset.accentId; applyAccent(); renderRoute();
  });
}
