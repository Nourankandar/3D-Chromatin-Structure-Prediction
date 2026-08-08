/* ============================================================
   10. VIEWERS
   الإطار المشترك للعارضين المصغّرين داخل لوحة الداشبورد 
   ============================================================ */
function viewerFrame({title, desc, backRoute, backLabel, panel, canvasId}){
  return `<div class="wrap">
    <button class="btn ghost sm" style="margin-bottom:1.25rem" data-go="${backRoute}">
      <span style="display:inline-flex;transform:rotate(${document.documentElement.dir==='rtl'?180:0}deg)">${ICON.back}</span><span>${backLabel}</span></button>
    <div class="between" style="margin-bottom:1.5rem">
      <div class="head"><h1>${title}</h1><p>${desc}</p></div>
      <div class="row" style="gap:1rem">
        <div class="row"><button class="switch" id="autoRotate" role="switch" aria-checked="true"></button>
          <label class="sm-t muted" for="autoRotate">${t('viewer_autorotate')}</label></div>
        <button class="btn outline sm" id="resetView">${ICON.reset}<span>${t('viewer_reset')}</span></button>
      </div>
    </div>
    <div class="split">
      <div class="canvas-wrap">
        <div class="grid-bg mask" style="position:absolute;inset:0;opacity:.22;pointer-events:none"></div>
        <canvas id="${canvasId}"></canvas>
        <span class="hint pill">${t('viewer_hint')}</span>
      </div>
      <aside class="stack">${panel}</aside>
    </div>
  </div>`;
}
function viewerEmpty(view, backRoute, label){
  view.innerHTML = `<div class="wrap"><div class="empty" style="padding:6rem 1.5rem">
    <div class="ico">${ICON.boxes}</div>
    <p class="sm-t muted" style="margin-top:1rem;max-width:36ch">${t('viewer_no_data')}</p>
    <button class="btn" style="margin-top:1.25rem" data-go="${backRoute}">${label}</button>
  </div></div>`;
}
const row = (k,v) => `<div class="panelrow"><span class="xs muted">${k}</span><span class="sm-t" style="font-weight:500;text-align:end">${v}</span></div>`;

function bindViewer(view, scene){
  const sw = view.querySelector('#autoRotate');
  sw.onclick = ()=>{ const on = sw.getAttribute('aria-checked')!=='true'; sw.setAttribute('aria-checked',on); scene.setAuto(on); };
  view.querySelector('#resetView').onclick = ()=> scene.reset();
}

function renderChromatin(view){
  const test = allTests().find(g=>g.id===S.activeTest);
  const patient = S.patients.find(p=>p.genomic_inputs.some(g=>g.id===S.activeTest));
  if(!test || test.status!=='completed'){ viewerEmpty(view,'dashboard',t('go_to_patients')); return; }
  const pts = test.report?.analysis_points ?? null;
  const regionSize = test.report?.region_size ?? (test.end_pos - test.start_pos);
  const outputId = test.output_data_id;
  const authToken = localStorage.getItem('chromogen-token') || '';
  const compareHref = outputId
    ? `hic_compare.html?output_id=${encodeURIComponent(outputId)}&input_id=${encodeURIComponent(test.id)}` + (authToken ? `&token=${encodeURIComponent(authToken)}` : '')
    : null;

  const panel = `
    <div class="card" style="padding:1.25rem">
      <div class="between" style="margin-bottom:.5rem"><p style="font-weight:500">${esc(patient.name)}</p>${statusBadge(test.status)}</div>
      ${row(t('patient_mrn'), esc(patient.mrn))}
      ${row(t('field_chromosome'), `<span class="mono">${esc(test.chromosome)}</span>`)}
      ${row(t('region'), `<span class="mono xs">${fmtNum(test.start_pos)} – ${fmtNum(test.end_pos)}</span>`)}
      ${row(t('region_size'), fmtRegion(regionSize))}
      ${row(t('cell_type'), esc(test.cell_type))}
      ${pts!=null ? row(t('viewer_points'), fmtNum(pts)) : ''}
      ${row(t('created_at'), fmtDate(test.created_at))}
    </div>
    ${test.report?.summary ? `<div class="card" style="padding:1.25rem">
      <p class="xs muted">${t('summary')}</p><p class="sm-t" style="margin-top:.5rem">${esc(test.report.summary)}</p></div>`:''}
    ${compareHref ? `<div style="display:flex; gap:8px">
      <a class="btn outline" style="flex:1" target="_blank" rel="noreferrer" href="${compareHref}">${ICON.external}<span>${t('viewer_compare_control')}</span></a>
      <button class="btn outline" style="flex:1" onclick="openReportModal(${test.id})">${ICON.file}<span>${t('viewer_report')}</span></button>
    </div>` : ''}`;

  view.innerHTML = viewerFrame({
    title:t('chromatin_viewer_title'), desc:t('chromatin_viewer_desc'),
    backRoute:'dashboard', backLabel:t('back_to_patients'), panel, canvasId:'chromatinCanvas'
  });

  const wrap = view.querySelector('.canvas-wrap');

  if (outputId && wrap) {
    const themeName = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    const src = `hic_viewer.html?output_id=${encodeURIComponent(outputId)}&side=patient&theme=${themeName}&accent=${accent}`
              + (authToken ? `&token=${encodeURIComponent(authToken)}` : '');
    wrap.innerHTML = `<iframe id="chromatinFrame" src="${src}" title="Chromatin 3D viewer"
      style="width:100%;height:clamp(380px,60vh,620px);border:0;display:block;border-radius:18px;background:var(--card)"></iframe>`;

    const frame = view.querySelector('#chromatinFrame');
    const postCtl = (msg) => frame.contentWindow?.postMessage({type:'chromo-ctl', ctl: msg}, '*');
    const sw = view.querySelector('#autoRotate');
    if (sw) sw.onclick = () => {
      const on = sw.getAttribute('aria-checked') !== 'true';
      sw.setAttribute('aria-checked', on);
      postCtl({rot: on});
    };
    const rb = view.querySelector('#resetView');
    if (rb) rb.onclick = () => postCtl({reset: true});
  } else {
    const beads = Math.min(220, Math.max(60, pts||0));
    bindViewer(view, createScene(view.querySelector('#chromatinCanvas'), buildChromatin(test.id, beads), {dist:13}));
  }
}

/* بحث بروتين حسب الجين */
async function searchProteinForViewer(gene){
  gene = (gene||'').trim();
  if(!gene) return;
  S.proteinSearching = true; renderRoute();
  try{
    const data = await api.get('/genomics/search-protein/', { params:{ gene } });
    if(data && data.pdb_ids && data.pdb_ids.length){
      S.activeProtein = { gene:data.gene, uniprot_id:data.uniprot_id, protein_name:data.protein_name, pdb_ids:data.pdb_ids, predicted:false };
      S.activePdb = data.pdb_ids[0];
    } else if(data && data.uniprot_id){
      S.activeProtein = { gene:data.gene, uniprot_id:data.uniprot_id, protein_name:data.protein_name, pdb_ids:[], predicted:true };
      S.activePdb = null;
      toast(t('protein_predicted_note'));
    } else { toast(t('protein_not_found'),'error'); }
  }catch(err){
    console.error('[protein search]', err.response ? err.response.data : err);
    toast(t('protein_not_found'),'error');
  }
  S.proteinSearching = false; renderRoute();
}
function wireProteinSearch(view){
  const btn=view.querySelector('#viewerGeneBtn'), inp=view.querySelector('#viewerGeneInput');
  if(btn && inp) btn.onclick = ()=> searchProteinForViewer(inp.value);
}

function renderProtein(view){
  const p = S.activeProtein;
  const searching = S.proteinSearching;

  const searchCard = `
    <div class="card" style="padding:1.1rem 1.25rem">
      <label class="label" for="viewerGeneInput">${t('protein_search_label') || 'بحث عن بروتين حسب الجين'}</label>
      <div class="row" style="gap:.5rem;margin-top:.55rem">
        <input id="viewerGeneInput" class="input" placeholder="TP53" value="${p?esc(p.gene):''}" style="flex:1"
          onkeydown="if(event.key==='Enter'){event.preventDefault();document.getElementById('viewerGeneBtn').click();}">
        <button class="btn" id="viewerGeneBtn" style="width:auto;padding-inline:16px" ${searching?'disabled':''}>${searching?'<span class="spin"></span>':ICON.search}</button>
      </div>
    </div>`;

  if(!p){
    view.innerHTML = `<div class="wrap">
      <div class="head" style="margin-bottom:1.5rem"><h1>${t('protein_viewer_title')}</h1><p>${t('protein_viewer_desc')}</p></div>
      <div style="max-width:520px">${searchCard}</div>
      <div class="empty" style="margin-top:1.5rem">
        <div class="ico">${ICON.search}</div>
        <p style="margin-top:1rem;font-weight:500">${t('protein_search_hint_title') || 'ابحث عن جين لعرض بنيته'}</p>
        <p class="sm-t muted" style="margin-top:.25rem;max-width:42ch">${t('protein_search_hint_desc') || 'اكتب اسم الجين فوق (مثل TP53) لجلب البروتين وعرض بنيته ثلاثية الأبعاد.'}</p>
      </div>
    </div>`;
    wireProteinSearch(view);
    return;
  }

  const isPredicted = !p.pdb_ids || !p.pdb_ids.length;
  if(!isPredicted && (!S.activePdb || !p.pdb_ids.includes(S.activePdb))) S.activePdb = p.pdb_ids[0];

  const panel = searchCard + `
    <div class="card" style="padding:1.25rem">
      <p style="font-weight:500">${esc(p.protein_name)}</p>
      <div style="margin-top:.75rem">
        ${row(t('gene'), `<span class="mono">${p.gene}</span>`)}
        ${row(t('uniprot_id'), `<span class="mono">${p.uniprot_id}</span>`)}
        ${row(t('pdb_ids'), isPredicted ? '0' : fmtNum(p.pdb_ids.length))}
      </div>
      ${isPredicted ? `<div class="af-note">${ICON.info}<span>${t('protein_predicted_badge')}</span></div>` : ''}
    </div>
    ${isPredicted ? `
    <div class="card" style="padding:1.25rem">
      <p class="xs muted">${t('protein_source')}</p>
      <p class="mono sm-t" style="margin-top:.35rem">AlphaFold · AF-${p.uniprot_id}-F1</p>
      <a class="btn outline" style="width:100%;margin-top:1rem" target="_blank" rel="noreferrer"
         href="https://alphafold.ebi.ac.uk/entry/${p.uniprot_id}">${ICON.external}<span>${t('viewer_open_alphafold')}</span></a>
    </div>` : `
    <div class="card" style="padding:1.25rem">
      <label class="label" for="pdbSelect">${t('select_pdb')}</label>
      <select id="pdbSelect" class="select mono" style="margin-top:.5rem">
        ${p.pdb_ids.map(id=>`<option ${id===S.activePdb?'selected':''}>${id}</option>`).join('')}
      </select>
      <a class="btn outline" style="width:100%;margin-top:1rem" target="_blank" rel="noreferrer"
         href="https://www.rcsb.org/structure/${S.activePdb}">${ICON.external}<span>${t('viewer_open_rcsb')}</span></a>
    </div>`}`;

  view.innerHTML = viewerFrame({
    title:t('protein_viewer_title'), desc:t('protein_viewer_desc'),
    backRoute:'predict', backLabel:t('back'), panel, canvasId:'proteinCanvas'
  });

 
  const proteinSrc = () => {
    const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    const base = `protein_viewer.html?name=${encodeURIComponent(p.protein_name||'')}&gene=${encodeURIComponent(p.gene||'')}&theme=${theme}&accent=${accent}`;
    return isPredicted
      ? `${base}&uniprot=${encodeURIComponent(p.uniprot_id)}`
      : `${base}&pdb=${encodeURIComponent(S.activePdb)}`;
  };
  const wrap = view.querySelector('.canvas-wrap');
  if (wrap) wrap.innerHTML = `<iframe id="proteinFrame" src="${proteinSrc()}" title="Protein 3D viewer"
    style="width:100%;height:clamp(380px,60vh,620px);border:0;display:block;border-radius:18px;background:var(--card)"></iframe>`;

  wireProteinSearch(view);
  const sel = view.querySelector('#pdbSelect');
  if (sel) sel.onchange = e=>{
    S.activePdb = e.target.value;
    const fr = document.getElementById('proteinFrame'); if (fr) fr.src = proteinSrc();
    const link = view.querySelector('a[href*="rcsb.org/structure"]'); if (link) link.href = `https://www.rcsb.org/structure/${S.activePdb}`;
  };
}

/* ══════════════ التقرير الطبي ══════════════ */
let _currentReportId = null;

function reportModalHTML(){
  return `
  <div id="reportModalOverlay" style="display:none;position:fixed;inset:0;background:rgba(4,16,14,.72);
    backdrop-filter:blur(3px);align-items:center;justify-content:center;z-index:200" onclick="if(event.target===this) closeReportModal()">
    <div style="background:linear-gradient(180deg,var(--card),var(--background));border-radius:18px;width:92%;max-width:460px;
      border:1px solid var(--border);box-shadow:0 30px 70px -20px rgba(0,0,0,.6);overflow:hidden;max-height:85vh;display:flex;flex-direction:column">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;padding:20px 22px 16px;border-bottom:1px solid var(--border);flex:none">
        <div style="display:flex;gap:12px;align-items:center">
          <div style="width:38px;height:38px;border-radius:10px;background:color-mix(in srgb, var(--primary) 15%, transparent);
            display:flex;align-items:center;justify-content:center;color:var(--primary)">${ICON.file}</div>
          <div><p style="font-weight:600;font-size:15px;margin:0" id="reportModalTitle">${t('viewer_report')}</p></div>
        </div>
        <span onclick="closeReportModal()" style="cursor:pointer;color:var(--muted-foreground);font-size:16px;padding:2px">✕</span>
      </div>
      <div style="padding:18px 22px;overflow-y:auto" id="reportModalBody">
        <p class="sm-t muted">${t('loading')||'...'}</p>
      </div>
    </div>
  </div>`;
}
function ensureReportModal(){
  if(!document.getElementById('reportModalOverlay'))
    document.body.insertAdjacentHTML('beforeend', reportModalHTML());
}
function closeReportModal(){
  const o=document.getElementById('reportModalOverlay'); if(o) o.style.display='none';
  _currentReportId=null;
}
async function openReportModal(testId){
  ensureReportModal();
  const overlay=document.getElementById('reportModalOverlay');
  const body=document.getElementById('reportModalBody');
  overlay.style.display='flex';
  body.innerHTML=`<p class="sm-t muted">جاري الجلب...</p>`;
  try{
    const inputDetail = await api.get(`/genomics/${testId}/`);
    const reportId = inputDetail?.output?.report_id;
    if(!reportId){ body.innerHTML=`<p class="sm-t muted">لا يوجد تقرير مرتبط بهذا التحليل بعد.</p>`; return; }
    await loadReport(reportId);
  }catch(e){
    body.innerHTML=`<p class="sm-t" style="color:var(--destructive)">تعذّر جلب التقرير.</p>`;
  }
}
async function loadReport(reportId){
  _currentReportId = reportId;
  const body=document.getElementById('reportModalBody');
  body.innerHTML=`<p class="sm-t muted">جاري الجلب...</p>`;
  try{
    const r = await api.get(`/reports/${reportId}/`);
    renderReportBody(r);
  }catch(e){
    body.innerHTML=`<p class="sm-t" style="color:var(--destructive)">تعذّر جلب التقرير.</p>`;
  }
}
function renderReportBody(r){
  const body=document.getElementById('reportModalBody');
  const st = r.status; 
  if(st==='draft' || st==='generating'){
    body.innerHTML=`<div style="text-align:center;padding:24px 0">
      <p class="sm-t muted">${st==='generating' ? 'التقرير عم يتولّد الآن...' : 'التقرير لسا ما بلّش توليده.'}</p>
      <button class="btn outline" style="margin-top:12px" onclick="loadReport(${r.id})">تحديث الحالة</button>
    </div>`;
    return;
  }
  if(st==='failed'){
    body.innerHTML=`<div style="text-align:center;padding:20px 0">
      <p class="sm-t" style="color:var(--destructive)">فشل توليد التقرير.</p>
      <button class="btn outline" style="margin-top:12px" onclick="regenerateReport(${r.id})">أعد المحاولة</button>
    </div>`;
    return;
  }
  // completed
  body.innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;gap:8px;align-items:center">
        <span style="background:color-mix(in srgb, var(--primary) 16%, transparent);color:var(--primary);
          font-size:11px;padding:4px 12px;border-radius:999px">مكتمل</span>
        <span class="mono-s muted" style="font-size:11px">${fmtDate(r.created_at)}</span>
      </div>
      <button title="إعادة توليد" onclick="regenerateReport(${r.id})"
        style="width:30px;height:30px;border-radius:9px;border:1px solid var(--border);background:transparent;color:var(--primary);display:flex;align-items:center;justify-content:center;cursor:pointer">↻</button>
    </div>
    <div style="background:var(--muted);border-radius:12px;padding:14px;margin-bottom:14px">
      <p class="xs muted" style="text-transform:uppercase;letter-spacing:.04em;margin:0 0 4px">التشخيص المحتمل</p>
      <p class="sm-t" style="margin:0">${esc(r.detected_disease || '—')}</p>
    </div>
    <div style="background:var(--muted);border-radius:12px;padding:14px;margin-bottom:18px">
      <p class="xs muted" style="text-transform:uppercase;letter-spacing:.04em;margin:0 0 6px">الملخّص</p>
      <p class="sm-t" style="white-space:pre-wrap;line-height:1.8;margin:0">${esc(r.summary_text || '—')}</p>
    </div>
    <button class="btn" style="width:100%" onclick="exportReportPDF(${r.id})">${ICON.file}<span>تصدير التقرير PDF</span></button>
  `;
}
async function regenerateReport(reportId){
  const body=document.getElementById('reportModalBody');
  body.innerHTML=`<p class="sm-t muted">جاري إعادة الطلب...</p>`;
  try{
    await api.post(`/reports/${reportId}/regenerate/`, {});
    await loadReport(reportId);
  }catch(e){
    body.innerHTML=`<p class="sm-t" style="color:var(--destructive)">تعذّر إعادة التوليد.</p>`;
  }
}
async function exportReportPDF(reportId){
  try{
    const res = await axios.get(`${API_BASE}/reports/${reportId}/export-pdf/`, {responseType:'blob'});
    const blobUrl = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = blobUrl; a.download = `report_${reportId}.pdf`; a.click();
    URL.revokeObjectURL(blobUrl);
  }catch(e){
    alert('  تأكد أن التقرير مكتمل ');
  }
}
