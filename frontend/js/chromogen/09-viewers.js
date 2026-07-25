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

  const pts = test.report?.analysis_points ?? 0;
  const panel = `
    <div class="card" style="padding:1.25rem">
      <div class="between" style="margin-bottom:.5rem"><p style="font-weight:500">${esc(patient.name)}</p>${statusBadge(test.status)}</div>
      ${row(t('patient_mrn'), esc(patient.mrn))}
      ${row(t('field_chromosome'), `<span class="mono">${esc(test.chromosome)}</span>`)}
      ${row(t('region'), `<span class="mono xs">${fmtNum(test.start_pos)} – ${fmtNum(test.end_pos)}</span>`)}
      ${row(t('region_size'), fmtRegion(test.report.region_size))}
      ${row(t('cell_type'), esc(test.cell_type))}
      ${row(t('viewer_points'), fmtNum(pts))}
      ${row(t('created_at'), fmtDate(test.created_at))}
    </div>
    ${test.report.summary ? `<div class="card" style="padding:1.25rem">
      <p class="xs muted">${t('summary')}</p><p class="sm-t" style="margin-top:.5rem">${esc(test.report.summary)}</p></div>`:''}`;

  view.innerHTML = viewerFrame({
    title:t('chromatin_viewer_title'), desc:t('chromatin_viewer_desc'),
    backRoute:'dashboard', backLabel:t('back_to_patients'), panel, canvasId:'chromatinCanvas'
  });

  
  const outputId = test.output_data_id;
  const wrap = view.querySelector('.canvas-wrap');

  if (outputId && wrap) {
    const themeName = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    const token = localStorage.getItem('access') || localStorage.getItem('access_token') || '';
    const src = `hic_viewer.html?output_id=${encodeURIComponent(outputId)}&theme=${themeName}&accent=${accent}`
              + (token ? `&token=${encodeURIComponent(token)}` : '');
    wrap.innerHTML = `<iframe id="chromatinFrame" src="${src}" title="Chromatin 3D viewer"
      style="width:100%;height:clamp(380px,60vh,620px);border:0;display:block;border-radius:18px;background:var(--card)"></iframe>`;
  } else {
    const beads = Math.min(220, Math.max(60, pts));
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
      // ما في بنية تجريبية بـ RCSB → منستعمل تنبؤ AlphaFold (بنية متوقّعة مش مقاسة)
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
