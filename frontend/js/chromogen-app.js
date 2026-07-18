const API_BASE = 'http://127.0.0.1:8000/api';
axios.defaults.withCredentials = false;


let _accessToken = null, _refreshToken = null;
function saveTokens(access, refresh){
  _accessToken = access; _refreshToken = refresh || _refreshToken;
  try {
    if (access)        localStorage.setItem('chromogen-token', access);
    if (_refreshToken) localStorage.setItem('chromogen-refresh', _refreshToken);
  } catch(e){}
}
function clearTokens(){
  _accessToken = null; _refreshToken = null;
  try { localStorage.removeItem('chromogen-token'); localStorage.removeItem('chromogen-refresh'); } catch(e){}
}
try {
  _accessToken  = localStorage.getItem('chromogen-token')   || null;
  _refreshToken = localStorage.getItem('chromogen-refresh') || null;
} catch(e){}

axios.interceptors.request.use(cfg=>{
  if (_accessToken) cfg.headers['Authorization'] = 'Bearer ' + _accessToken;
  return cfg;
}, err=>Promise.reject(err));
axios.interceptors.response.use(r=>r, async err=>{
  const orig   = err.config || {};
  const status = err.response && err.response.status;
  const url    = orig.url || '';
  // لا نجدّد على طلبات الدخول/التحديث/الخروج نفسها، ولا نكرّر المحاولة أكثر من مرة
  const skip = url.includes('/auth/login') || url.includes('/auth/token/refresh') || url.includes('/auth/logout');

  if (status === 401 && !orig._retried && !skip && _refreshToken){
    orig._retried = true;
    try {
      const rr = await axios.post(API_BASE + '/auth/token/refresh/', { refresh: _refreshToken });
      saveTokens(rr.data.access, rr.data.refresh || _refreshToken);
      orig.headers = orig.headers || {};
      orig.headers['Authorization'] = 'Bearer ' + _accessToken;
      return axios(orig);   // أعد تنفيذ الطلب الأصلي بالتوكن الجديد
    } catch(e){
      clearTokens();
      if (typeof go === 'function') go('login');
      if (typeof toast === 'function') toast('انتهت الجلسة، الرجاء الدخول من جديد','error');
      return Promise.reject(e);
    }
  }
  if (status === 401 && !skip){
    clearTokens();
    if (typeof go === 'function') go('login');
  }
  return Promise.reject(err);
});


const GENDER_TO_UI  = { M:'male', F:'female', O:'other' };
const GENDER_TO_API = { male:'M', female:'F', other:'O' };

function patientFromApi(p){
  return {
    id: p.id, name: p.name, mrn: p.mrn,
    gender: GENDER_TO_UI[p.gender] || 'other',
    dob: p.dob,
    genomic_inputs: [],
  };
}
function testFromApi(t){
  return {
    id: t.id, status: t.status, created_at: t.created_at,
    cell_type: t.cell_type_name || '',
    chromosome: t.chromosome, start_pos: t.start_pos, end_pos: t.end_pos,
    fasta_file: t.dna_sequence_file || '',
    output_data_id: t.output_data_id || null,
    report: null,
  };
}

const api = {
  get:  (path, cfg)       => axios.get(API_BASE+path, cfg).then(r=>r.data),
  post: (path, body, cfg) => axios.post(API_BASE+path, body, cfg).then(r=>r.data),
  patch:(path, body)      => axios.patch(API_BASE+path, body).then(r=>r.data),
  del:  (path)            => axios.delete(API_BASE+path).then(r=>r.data),
};

/* ============================================================
   0. ICONS (inline so the file has zero dependencies)
   ============================================================ */
const I = (p,extra="") => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ${extra}>${p}</svg>`;
const ICON = {
  dna:      I('<path d="M6 3c0 6 12 6 12 12M6 21c0-6 12-6 12-12"/><path d="M7 6h10M7 18h10M8.5 9.5h7M8.5 14.5h7" stroke-width="1.1"/>'),
  users:    I('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'),
  flask:    I('<path d="M10 2v6.5L4.5 18A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-3L14 8.5V2"/><path d="M8.5 2h7M7 15h10"/>'),
  boxes:    I('<path d="M12 2 4 6v12l8 4 8-4V6z"/><path d="M4 6l8 4 8-4M12 22V10"/>'),
  settings: I('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a1.7 1.7 0 0 0-1.5-1H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 3 8.6a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 9 3V3a2 2 0 1 1 4 0v.1A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21 9h0a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'),
  logout:   I('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>'),
  sun:      I('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  moon:     I('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
  lang:     I('<path d="m5 8 6 6M4 14l6-6 2-3M2 5h12M7 2h1M22 22l-5-10-5 10M14 18h6"/>'),
  search:   I('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
  plus:     I('<path d="M12 5v14M5 12h14"/>'),
  pencil:   I('<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>'),
  trash:    I('<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/>'),
  chevron:  I('<path d="m6 9 6 6 6-6"/>'),
  retry:    I('<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>'),
  reset:    I('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>'),
  alert:    I('<circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>'),
  check:    I('<path d="M20 6 9 17l-5-5"/>'),
  upload:   I('<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>'),
  file:     I('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>'),
  x:        I('<path d="M18 6 6 18M6 6l12 12"/>'),
  info:     I('<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>'),
  clock:    I('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  back:     I('<path d="M19 12H5M12 19l-7-7 7-7"/>'),
  external: I('<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'),
};

document.querySelectorAll('[data-icon]').forEach(n => n.innerHTML = ICON[n.dataset.icon]);

/* ============================================================
   1. i18n
   ============================================================ */
const DICT = {
  en:{
    brand:'ChromoGen', tagline:'Genomic Analysis Platform', loading:'Loading…', cancel:'Cancel', save:'Save',
    delete:'Delete', retry:'Retry', optional:'optional', back:'Back',
    landing_status:'System status: online', landing_hero_a:'Predicting the', landing_hero_b:'architecture', landing_hero_c:'of the genome',
    landing_sub:'From a genomic region to a predicted 3D chromatin structure. Run background predictions, explore protein structures, and visualize results in an interactive 3D viewer.',
    landing_cta:'Enter the lab', landing_cta_secondary:'Explore features',
    landing_feature1_title:'Chromatin prediction', landing_feature1_desc:'Submit a genomic region and a cell type to reconstruct its predicted 3D chromatin structure in the background.',
    landing_feature2_title:'Protein search', landing_feature2_desc:'Search a gene name to retrieve its protein, UniProt id, and known PDB structures.',
    landing_feature3_title:'3D viewers', landing_feature3_desc:'Explore predicted chromatin and protein structures in fully interactive 3D viewers.',
    landing_pipeline_title:'A five-stage pipeline', landing_pipeline_desc:'Every prediction moves through the same five stages before a report is produced.',
    stage_ingest:'Ingest', stage_preprocess:'Preprocess', stage_predict:'Predict', stage_reconstruct:'Reconstruct', stage_report:'Report',
    pipeline_note:'The backend reports no per-stage progress — only the five status values.', pipeline_reference:'Pipeline stages',
    nav_overview:'Overview', nav_profile:'Profile',
    ov_title:'Overview', ov_subtitle:'Computed from your patients and tests',
    ov_patients:'Patients', ov_tests:'Total tests', ov_completed:'Completed', ov_running:'Running', ov_failed:'Failed',
    ov_success:'Success rate', ov_avg:'Avg tests / patient', ov_recent:'Recent tests', ov_derived:'Derived in the browser — no extra API',
    pr_title:'Profile', pr_subtitle:'Your account details',
    pr_username:'Username', pr_email:'Email', pr_role:'Role', pr_joined:'Joined',
    pr_superuser:'Superuser', pr_staff:'Administrator', pr_readonly:'Read-only — the backend exposes no profile update endpoint',
    login_title:'Sign in', login_subtitle:'Access your genomic analysis workspace', username:'Username', password:'Password',
    login_button:'Sign in', login_error:'Login failed. Please check your credentials and try again.',
    logout:'Log out',
    nav_patients:'Patients', nav_predict:'New prediction', nav_settings:'Settings', nav_chromatin:'Chromatin viewer', nav_protein:'Protein viewer',
    patients_title:'Patients', patients_subtitle:'Manage registered patients and their tests',
    add_patient:'Add patient', edit_patient:'Edit patient', delete_patient:'Delete patient',
    patient_name:'Name', patient_mrn:'MRN', patient_gender:'Gender', patient_dob:'Date of birth',
    gender_male:'Male', gender_female:'Female', gender_other:'Other', tests_count:'Tests',
    no_patients_title:'No patients yet', no_patients_desc:'Add your first patient to start running predictions.',
    no_tests_title:'No tests yet', no_tests_desc:'This patient has no tests. Start a new prediction.',
    patients_error:'Could not load the patient list.',
    delete_patient_confirm_title:'Delete this patient?', delete_patient_confirm_desc:'This will permanently remove the patient and all associated tests.',
    delete_test_confirm_title:'Delete this test?', delete_test_confirm_desc:'This will permanently remove this test and its report.',
    view_tests:'View tests', created_at:'Created', region:'Region', cell_type:'Cell type',
    open_chromatin:'Open 3D viewer', delete_test:'Delete test', back_to_patients:'Back to patients', go_to_patients:'Go to patients',
    status_pending:'Pending', status_predicting_dnase:'Predicting DNase', status_generating_hic:'Generating Hi-C', status_queued:'Queued', status_running:'Running', status_completed:'Completed', status_failed:'Failed',
    predict_title:'New prediction', predict_subtitle:'Configure and start a chromatin structure prediction',
    field_patient:'Patient', field_patient_ph:'Choose a patient', field_cell_type:'Cell type', field_cell_type_ph:'Choose a cell type',
    field_chromosome:'Chromosome', field_chromosome_ph:'e.g. chr21', field_start:'Start position', field_end:'End position',
    hint_title:'Estimated analysis', hint_points:'Analysis points at 5 kb', hint_region:'Region size',
    field_fasta:'FASTA file', fasta_hint:'Accepts .fasta, .fa, or .txt', fasta_choose:'Choose file',
    fasta_rejected:'File rejected. Only .fasta, .fa, or .txt files are accepted.', fasta_drop:'Drag a file here, or',
    fasta_remove:'Remove file', start_prediction:'Start prediction',
    background_note:'Processing runs in the background. You can leave this page.',
    prediction_started:'Prediction started. It is now processing in the background.',
    prediction_started_loading:'Starting prediction…',
    prediction_running_title:'Prediction started', prediction_running_desc:'The test is queued and keeps processing after you leave this page.',
    start_another:'Start another prediction', invalid_range:'The end position must be greater than the start position.',
    predict_no_patients_title:'No patients to predict for', predict_no_patients_desc:'Register a patient first, then come back to start a prediction.',
    protein_title:'Protein search', protein_subtitle:'Find a protein structure by gene name',
    field_gene:'Gene name', field_gene_ph:'e.g. TP53', search:'Search', searching:'Searching…',
    gene:'Gene', protein_name:'Protein name', uniprot_id:'UniProt id', pdb_ids:'PDB ids',
    open_protein_viewer:'Open in 3D protein viewer', protein_not_found:'No protein found for that gene name.',
    protein_empty:'Search a gene name to see its protein and structures.', protein_result:'Result',
    settings_title:'Settings', settings_subtitle:'Only two controls exist',
    theme:'Theme', theme_light:'Light', theme_dark:'Dark', theme_desc:'Choose how the workspace looks.',
    language:'Language', lang_ar:'العربية', lang_en:'English', language_desc:'Switch the interface language and its direction.',
    chromatin_viewer_title:'3D Chromatin viewer', chromatin_viewer_desc:'Interactive view of the predicted chromatin structure.',
    protein_viewer_title:'3D Protein viewer', protein_viewer_desc:'Interactive view of the protein structure.',
    viewer_hint:'Drag to rotate · scroll to zoom', viewer_no_data:'No structure to display. Open a viewer from a completed result.',
    viewer_reset:'Reset view', viewer_autorotate:'Auto-rotate', viewer_points:'Analysis points',
    viewer_open_rcsb:'Open on RCSB', select_pdb:'PDB structure', summary:'Summary', region_size:'Region size',
    toast_patient_added:'Patient added.', toast_patient_updated:'Patient updated.', toast_patient_deleted:'Patient deleted.',
    toast_test_deleted:'Test deleted.', toast_retry_started:'The test is queued again.', toast_error:'Something went wrong. Please try again.',
  },
  ar:{
    brand:'كروموجين', tagline:'منصة التحليل الجينومي', loading:'جارٍ التحميل…', cancel:'إلغاء', save:'حفظ',
    delete:'حذف', retry:'إعادة المحاولة', optional:'اختياري', back:'رجوع',
    landing_status:'حالة النظام: متصل', landing_hero_a:'التنبؤ', landing_hero_b:'ببنية', landing_hero_c:'الجينوم',
    landing_sub:'من منطقة جينومية إلى بنية كروماتين ثلاثية الأبعاد متوقّعة. شغّل التنبؤات في الخلفية، واستكشف بنى البروتينات، وتصفّح النتائج في عارض ثلاثي الأبعاد تفاعلي.',
    landing_cta:'ادخل إلى المختبر', landing_cta_secondary:'استكشف الميزات',
    landing_feature1_title:'التنبؤ بالكروماتين', landing_feature1_desc:'أدخل منطقة جينومية ونوع خلية لإعادة بناء بنية الكروماتين ثلاثية الأبعاد المتوقّعة في الخلفية.',
    landing_feature2_title:'بحث البروتينات', landing_feature2_desc:'ابحث باسم الجين لاسترجاع البروتين ومعرّف UniProt وبنى PDB المعروفة.',
    landing_feature3_title:'عارضات ثلاثية الأبعاد', landing_feature3_desc:'استكشف بنى الكروماتين والبروتينات المتوقّعة في عارضات ثلاثية الأبعاد تفاعلية بالكامل.',
    landing_pipeline_title:'خط معالجة من خمس مراحل', landing_pipeline_desc:'يمرّ كل تنبؤ عبر المراحل الخمس نفسها قبل إنتاج التقرير.',
    stage_ingest:'الاستقبال', stage_preprocess:'المعالجة المسبقة', stage_predict:'التنبؤ', stage_reconstruct:'إعادة البناء', stage_report:'التقرير',
    pipeline_note:'لا يُبلّغ الخادم عن تقدّم كل مرحلة — فقط قيم الحالة الخمس.', pipeline_reference:'مراحل خط المعالجة',
    nav_overview:'لوحة التحكم', nav_profile:'الملف الشخصي',
    ov_title:'لوحة التحكم', ov_subtitle:'محسوبة من المرضى والتحاليل الموجودة',
    ov_patients:'المرضى', ov_tests:'إجمالي التحاليل', ov_completed:'مكتملة', ov_running:'قيد المعالجة', ov_failed:'فشل',
    ov_success:'نسبة النجاح', ov_avg:'متوسّط التحاليل لكل مريض', ov_recent:'آخر التحاليل', ov_derived:'محسوبة في المتصفّح — بدون أي API إضافي',
    pr_title:'الملف الشخصي', pr_subtitle:'تفاصيل حسابك',
    pr_username:'اسم المستخدم', pr_email:'البريد الإلكتروني', pr_role:'الصلاحية', pr_joined:'تاريخ الانضمام',
    pr_superuser:'مشرف عام', pr_staff:'مسؤول', pr_readonly:'للقراءة فقط — لا يوفّر الباك إند نقطة تعديل للملف الشخصي',
    login_title:'تسجيل الدخول', login_subtitle:'ادخل إلى مساحة عمل التحليل الجينومي', username:'اسم المستخدم', password:'كلمة المرور',
    login_button:'تسجيل الدخول', login_error:'فشل تسجيل الدخول. يرجى التحقق من بياناتك والمحاولة مرة أخرى.',
    logout:'تسجيل الخروج',
    nav_patients:'المرضى', nav_predict:'تنبؤ جديد', nav_settings:'الإعدادات', nav_chromatin:'عارض الكروماتين', nav_protein:'عارض البروتين',
    patients_title:'المرضى', patients_subtitle:'إدارة المرضى المسجّلين واختباراتهم',
    add_patient:'إضافة مريض', edit_patient:'تعديل المريض', delete_patient:'حذف المريض',
    patient_name:'الاسم', patient_mrn:'الرقم الطبي', patient_gender:'الجنس', patient_dob:'تاريخ الميلاد',
    gender_male:'ذكر', gender_female:'أنثى', gender_other:'آخر', tests_count:'الاختبارات',
    no_patients_title:'لا يوجد مرضى بعد', no_patients_desc:'أضف أول مريض لبدء تشغيل التنبؤات.',
    no_tests_title:'لا توجد اختبارات بعد', no_tests_desc:'لا يملك هذا المريض أي اختبارات. ابدأ تنبؤًا جديدًا.',
    patients_error:'تعذّر تحميل قائمة المرضى.',
    delete_patient_confirm_title:'حذف هذا المريض؟', delete_patient_confirm_desc:'سيؤدي هذا إلى حذف المريض وجميع اختباراته نهائيًا.',
    delete_test_confirm_title:'حذف هذا الاختبار؟', delete_test_confirm_desc:'سيؤدي هذا إلى حذف هذا الاختبار وتقريره نهائيًا.',
    view_tests:'عرض الاختبارات', created_at:'أُنشئ في', region:'المنطقة', cell_type:'نوع الخلية',
    open_chromatin:'فتح العارض ثلاثي الأبعاد', delete_test:'حذف الاختبار', back_to_patients:'العودة إلى المرضى', go_to_patients:'الذهاب إلى المرضى',
    status_pending:'قيد الانتظار', status_predicting_dnase:'تنبؤ DNase', status_generating_hic:'توليد Hi-C', status_queued:'في الطابور', status_running:'قيد التشغيل', status_completed:'مكتمل', status_failed:'فشل',
    predict_title:'تنبؤ جديد', predict_subtitle:'اضبط وابدأ تنبؤ بنية الكروماتين',
    field_patient:'المريض', field_patient_ph:'اختر مريضًا', field_cell_type:'نوع الخلية', field_cell_type_ph:'اختر نوع خلية',
    field_chromosome:'الكروموسوم', field_chromosome_ph:'مثال: chr21', field_start:'موضع البداية', field_end:'موضع النهاية',
    hint_title:'التحليل التقديري', hint_points:'نقاط التحليل عند 5 كيلوباز', hint_region:'حجم المنطقة',
    field_fasta:'ملف FASTA', fasta_hint:'يقبل ‎.fasta أو ‎.fa أو ‎.txt', fasta_choose:'اختر ملفًا',
    fasta_rejected:'الملف مرفوض. يُقبل فقط ‎.fasta أو ‎.fa أو ‎.txt.', fasta_drop:'اسحب ملفًا إلى هنا، أو',
    fasta_remove:'إزالة الملف', start_prediction:'ابدأ التنبؤ',
    background_note:'تتم المعالجة في الخلفية. يمكنك مغادرة هذه الصفحة.',
    prediction_started:'بدأ التنبؤ. تتم معالجته الآن في الخلفية.',
    prediction_started_loading:'جارٍ بدء التنبؤ…',
    prediction_running_title:'بدأ التنبؤ', prediction_running_desc:'تمّت جدولة الاختبار وستستمرّ المعالجة بعد مغادرتك هذه الصفحة.',
    start_another:'ابدأ تنبؤًا آخر', invalid_range:'يجب أن يكون موضع النهاية أكبر من موضع البداية.',
    predict_no_patients_title:'لا يوجد مرضى لتشغيل تنبؤ لهم', predict_no_patients_desc:'سجّل مريضًا أولًا، ثم عد لبدء التنبؤ.',
    protein_title:'بحث البروتينات', protein_subtitle:'ابحث عن بنية بروتين باسم الجين',
    field_gene:'اسم الجين', field_gene_ph:'مثال: TP53', search:'بحث', searching:'جارٍ البحث…',
    gene:'الجين', protein_name:'اسم البروتين', uniprot_id:'معرّف UniProt', pdb_ids:'معرّفات PDB',
    open_protein_viewer:'فتح في عارض البروتين ثلاثي الأبعاد', protein_not_found:'لم يُعثر على بروتين لاسم الجين هذا.',
    protein_empty:'ابحث باسم الجين لعرض البروتين وبنيته.', protein_result:'النتيجة',
    settings_title:'الإعدادات', settings_subtitle:'يوجد عنصران فقط للتحكّم',
    theme:'السمة', theme_light:'فاتح', theme_dark:'داكن', theme_desc:'اختر مظهر مساحة العمل.',
    language:'اللغة', lang_ar:'العربية', lang_en:'English', language_desc:'بدّل لغة الواجهة واتجاهها.',
    chromatin_viewer_title:'عارض الكروماتين ثلاثي الأبعاد', chromatin_viewer_desc:'عرض تفاعلي لبنية الكروماتين المتوقّعة.',
    protein_viewer_title:'عارض البروتين ثلاثي الأبعاد', protein_viewer_desc:'عرض تفاعلي لبنية البروتين.',
    viewer_hint:'اسحب للتدوير · مرّر للتكبير', viewer_no_data:'لا توجد بنية للعرض. افتح العارض من نتيجة مكتملة.',
    viewer_reset:'إعادة ضبط العرض', viewer_autorotate:'دوران تلقائي', viewer_points:'نقاط التحليل',
    viewer_open_rcsb:'فتح في RCSB', select_pdb:'بنية PDB', summary:'الملخص', region_size:'حجم المنطقة',
    toast_patient_added:'تمت إضافة المريض.', toast_patient_updated:'تم تحديث المريض.', toast_patient_deleted:'تم حذف المريض.',
    toast_test_deleted:'تم حذف الاختبار.', toast_retry_started:'أُعيدت جدولة الاختبار.', toast_error:'حدث خطأ ما. يرجى المحاولة مرة أخرى.',
  }
};
let locale = 'en', theme = 'dark';
const t = k => (DICT[locale][k] ?? DICT.en[k] ?? k);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function applyStaticText(root=document){ root.querySelectorAll('[data-t]').forEach(n => n.textContent = t(n.dataset.t)); }
function applyLocale(){
  document.documentElement.lang = locale;
  document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
  document.querySelectorAll('.js-lang').forEach(b => b.innerHTML = `${ICON.lang}<span>${locale==='en'?'ع':'EN'}</span>`);
  applyStaticText(); renderNav(); renderRoute();
}
function applyTheme(){
  document.documentElement.classList.toggle('dark', theme==='dark');
  document.querySelectorAll('.js-theme').forEach(b => b.innerHTML = theme==='dark' ? ICON.sun : ICON.moon);
  scenes.forEach(s => s.refreshColors());
}

/* ---------- formatting ---------- */
const nf = () => new Intl.NumberFormat(locale==='ar'?'ar-EG':'en-US');
const fmtNum = n => nf().format(n);
const fmtDate = iso => new Intl.DateTimeFormat(locale==='ar'?'ar-EG':'en-US',{year:'numeric',month:'short',day:'numeric'}).format(new Date(iso));
const fmtRegion = bp => bp<=0 ? '—' : bp>=1e6 ? `${fmtNum(Math.round(bp/1e4)/100)} Mb` : `${fmtNum(Math.round(bp/100)/10)} kb`;
const estPoints = (s,e) => Math.max(1, Math.round((e-s)/5000));

/* ============================================================
   2. MOCK STATE (mirrors the REST API shape)
   ============================================================ */

let CELL_TYPES = [];
async function fetchCellTypes(){
  try {
    const data = await api.get('/genomics/cell-types/');
    CELL_TYPES = (data.cell_types || data.results || data || []).map(c=>({id:c.id, name:c.name}));
  } catch(e){
    console.error('[cell-types]', e.response ? e.response.data : e);
    CELL_TYPES = [];
  }
}
const PROTEINS = {
  TP53:{gene:'TP53',protein_name:'Cellular tumor antigen p53',uniprot_id:'P04637',pdb_ids:['1TUP','2OCJ','3TS8','4HJE','6GGB']},
  BRCA1:{gene:'BRCA1',protein_name:'Breast cancer type 1 susceptibility protein',uniprot_id:'P38398',pdb_ids:['1JM7','1T15','4IGK']},
  EGFR:{gene:'EGFR',protein_name:'Epidermal growth factor receptor',uniprot_id:'P00533',pdb_ids:['1IVO','2ITY','3W2S','4HJO']},
};
const SEED_PATIENTS = () => ([
  {id:1,name:'Layla Haddad',mrn:'MRN-004521',gender:'female',dob:'1990-04-18',genomic_inputs:[
    {id:101,status:'completed',created_at:'2024-06-01T10:30:00Z',cell_type:'GM12878',chromosome:'chr21',start_pos:30000000,end_pos:30500000,fasta_file:'chr21_region.fasta',
     report:{summary:'Chromatin structure reconstructed for chr21:30M–30.5M.',analysis_points:100,region_size:500000}},
    {id:102,status:'running',created_at:'2024-06-03T14:05:00Z',cell_type:'K562',chromosome:'chr7',start_pos:55000000,end_pos:55250000,fasta_file:'chr7_egfr.fa',report:null},
  ]},
  {id:2,name:'Omar Nasser',mrn:'MRN-004522',gender:'male',dob:'1985-11-02',genomic_inputs:[
    {id:103,status:'failed',created_at:'2024-05-28T08:15:00Z',cell_type:'IMR90',chromosome:'chr17',start_pos:7660000,end_pos:7690000,fasta_file:'tp53_locus.txt',report:null},
  ]},
  {id:3,name:'Sara Khoury',mrn:'MRN-004523',gender:'female',dob:'1998-07-25',genomic_inputs:[]},
]);

const USER = { username:'rema', email:'rema@biotreatment.lab', is_superuser:true, date_joined:'2026-06-24T09:12:00Z' };

const S = {
  route:'landing',
  patients:[], patientsLoading:true, patientsError:false,
  expanded:null, editing:null, activeTest:null, activeProtein:null, activePatient:null,
  demo:'normal',
};
let idCounter = 1000;

const wait = ms => new Promise(r=>setTimeout(r,ms));

async function loadPatients(){
  S.patientsLoading = true; S.patientsError = false; renderRoute();
  try {
    // 1) قائمة المرضى 
    const data = await api.get('/patients/');
    const rows = Array.isArray(data) ? data : (data.results || data.patients || []);
    const patients = rows.map(patientFromApi);

    // 2) تحاليل كل مريض عبر الأكشن 
    await Promise.all(patients.map(async p=>{
      try {
        const td = await api.get(`/patients/${p.id}/tests/`);
        const tests = td.tests || td.results || [];
        p.genomic_inputs = tests.map(testFromApi);
      } catch(e){ p.genomic_inputs = []; }
    }));

    S.patients = patients;
    S.patientsLoading = false; renderRoute();
  } catch(e){
    console.error('[loadPatients]', e.response ? e.response.data : e);
    S.patientsLoading = false; S.patientsError = true; renderRoute();
  }
}

/*  pipeline  استعلام دوري عن  */
const _pollTimers = {};
function pollTestStatus(inputId){
  if (_pollTimers[inputId]) clearInterval(_pollTimers[inputId]);
  _pollTimers[inputId] = setInterval(async ()=>{
    try {
      const st = await api.get(`/genomics/test-status/${inputId}/`);
      // حدّث حالة هذا التحليل إن كان محمّلاً
      S.patients.forEach(p=>p.genomic_inputs.forEach(g=>{
        if (g.id===inputId){ g.status = st.status; if (st.output_data_id) g.output_data_id = st.output_data_id; }
      }));
      if (S.route==='dashboard') renderRoute();
      if (st.status==='completed' || st.status==='failed'){
        clearInterval(_pollTimers[inputId]); delete _pollTimers[inputId];
        if (st.status==='completed') toast(t('toast_test_completed') || 'اكتمل التحليل بنجاح');
        else toast('فشل التحليل — راجع السيرفر','error');
      }
    } catch(e){ /* خطأ مؤقت — منكمّل الاستعلام */ }
  }, 4000);
}

/* ============================================================
   3. TOASTS + DIALOGS
   ============================================================ */
function toast(msg, kind='success'){
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.innerHTML = `${kind==='error'?ICON.alert:ICON.check}<span>${esc(msg)}</span>`;
  document.getElementById('toasts').append(el);
  setTimeout(()=>{ el.style.opacity='0'; el.style.transition='opacity .2s'; setTimeout(()=>el.remove(),200); }, 3200);
}
function confirmDialog(title, desc){
  return new Promise(resolve=>{
    const dlg = document.getElementById('confirmDialog');
    document.getElementById('cfTitle').textContent = title;
    document.getElementById('cfDesc').textContent = desc;
    const ok = document.getElementById('cfOk');
    const done = v => { dlg.close(); ok.onclick=null; resolve(v); };
    ok.onclick = ()=>done(true);
    dlg.querySelector('[data-close]').onclick = ()=>done(false);
    dlg.oncancel = ()=>resolve(false);
    dlg.showModal();
  });
}

/* ============================================================
   4. 3D ENGINE — tiny painter's-algorithm renderer on 2D canvas.
   ============================================================ */
const scenes = [];
const mulberry32 = a => () => { a|=0; a=a+0x6D2B79F5|0; let x=Math.imul(a^a>>>15,1|a); x=x+Math.imul(x^x>>>7,61|x)^x; return ((x^x>>>14)>>>0)/4294967296; };
const hashSeed = s => { let h=2166136261; for(const c of String(s)){h^=c.charCodeAt(0);h=Math.imul(h,16777619);} return h>>>0; };
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const hex2rgb = h => { const v=h.replace('#',''); return [parseInt(v.slice(0,2),16),parseInt(v.slice(2,4),16),parseInt(v.slice(4,6),16)]; };
const mix = (a,b,tt) => a.map((v,i)=>Math.round(v+(b[i]-v)*tt));
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;


const _colCanvas = document.createElement('canvas'); _colCanvas.width = _colCanvas.height = 1;
const _colCtx = _colCanvas.getContext('2d', { willReadFrequently:true });
function resolveColor(v){
  _colCtx.fillStyle = '#8eb69b';
  try { if (v) _colCtx.fillStyle = v; } catch(e){}
  _colCtx.fillRect(0,0,1,1);
  const d = _colCtx.getImageData(0,0,1,1).data;
  return [d[0], d[1], d[2]];
}

/** Generic scene: an array of {x,y,z,r,color} nodes + links between consecutive nodes. */
function createScene(canvas, build, opts={}){
  const ctx = canvas.getContext('2d');
  let nodes = [], rotX = -.25, rotY = .5, dist = opts.dist ?? 12, auto = opts.auto ?? true;
  let dragging = false, lx = 0, ly = 0, raf = 0;

  function refreshColors(){ nodes = build({from:resolveColor(cssVar('--scene-from')), via:resolveColor(cssVar('--scene-via')), to:resolveColor(cssVar('--scene-to'))}); }
  function reset(){ rotX = -.25; rotY = .5; dist = opts.dist ?? 12; }

  function resize(){
    const rect = canvas.getBoundingClientRect();
    const w = Math.round(rect.width)  || canvas.clientWidth  || canvas.offsetWidth;
    const h = Math.round(rect.height) || canvas.clientHeight || canvas.offsetHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio||1, 2);
    canvas.width = w*dpr; canvas.height = h*dpr;
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }

  function project(p){
    const cy=Math.cos(rotY), sy=Math.sin(rotY), cx=Math.cos(rotX), sx=Math.sin(rotX);
    let x = p.x*cy - p.z*sy, z = p.x*sy + p.z*cy;
    let y = p.y*cx - z*sx;  z = p.y*sx + z*cx;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const fov = Math.min(w,h) * 0.9;
    const k = fov / (dist + z + 8);
    return {sx:w/2 + x*k, sy:h/2 - y*k, k, z};
  }

  function frame(){
    if (auto && !dragging) rotY += 0.0035;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h){ raf = requestAnimationFrame(frame); return; }
    ctx.clearRect(0,0,w,h);

    const items = [];
    const pts = nodes.map(project);
    for (let i=0;i<nodes.length;i++){
      items.push({z:pts[i].z, kind:'node', i});
      if (i>0 && !nodes[i].nolink) items.push({z:(pts[i].z+pts[i-1].z)/2, kind:'link', i});
    }
    items.sort((a,b)=>b.z-a.z);   // far first

    for (const it of items){
      const p = pts[it.i], n = nodes[it.i];
      const depth = Math.max(0, Math.min(1, 1 - (p.z+6)/16));  // 0 far … 1 near
      if (it.kind === 'link'){
        const q = pts[it.i-1];
        ctx.beginPath(); ctx.moveTo(q.sx,q.sy); ctx.lineTo(p.sx,p.sy);
        ctx.strokeStyle = rgb(n.color); ctx.globalAlpha = .25 + depth*.5;
        ctx.lineWidth = Math.max(.6, n.r * p.k * 0.9);
        ctx.lineCap = 'round'; ctx.stroke();
      } else {
        const r = Math.max(.8, n.r * p.k);
        const g = ctx.createRadialGradient(p.sx - r*.35, p.sy - r*.35, r*.1, p.sx, p.sy, r);
        g.addColorStop(0, rgb(mix(n.color,[255,255,255],.45)));
        g.addColorStop(1, rgb(n.color));
        ctx.beginPath(); ctx.arc(p.sx,p.sy,r,0,Math.PI*2);
        ctx.globalAlpha = .55 + depth*.45; ctx.fillStyle = g; ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    raf = requestAnimationFrame(frame);
  }

  canvas.addEventListener('pointerdown', e=>{ dragging=true; lx=e.clientX; ly=e.clientY; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointerup',   e=>{ dragging=false; });
  canvas.addEventListener('pointermove', e=>{
    if(!dragging) return;
    rotY += (e.clientX-lx)*0.008; rotX += (e.clientY-ly)*0.008;
    rotX = Math.max(-1.4, Math.min(1.4, rotX)); lx=e.clientX; ly=e.clientY;
  });
  canvas.addEventListener('wheel', e=>{ e.preventDefault(); dist = Math.max(5, Math.min(30, dist + e.deltaY*0.01)); }, {passive:false});

  const ro = new ResizeObserver(resize); ro.observe(canvas);
  resize(); refreshColors(); frame();
  // ضمان ضبط الأبعاد بعد اكتمال تخطيط الصفحة (يعالج حالة أن الكانفس لسا بلا حجم لحظة الإنشاء)
  requestAnimationFrame(()=>{ resize(); requestAnimationFrame(resize); });
  setTimeout(resize, 60); setTimeout(resize, 250);

  const api = {
    refreshColors, reset,
    setAuto(v){ auto = v; },
    destroy(){ cancelAnimationFrame(raf); ro.disconnect(); const i=scenes.indexOf(api); if(i>-1) scenes.splice(i,1); }
  };
  scenes.push(api);
  return api;
}
function clearScenes(){ [...scenes].forEach(s=>s.destroy()); }

/** Double helix (landing hero). */
const buildHelix = () => pal => {
  const A=[], B=[], count=34, radius=1.6, height=8, turns=2.4;
  for(let i=0;i<count;i++){
    const tt=i/(count-1), y=(tt-.5)*height, a=tt*Math.PI*2*turns;
    A.push({x:Math.cos(a)*radius, y, z:Math.sin(a)*radius, r:.17, color:pal.from});
    B.push({x:Math.cos(a+Math.PI)*radius, y, z:Math.sin(a+Math.PI)*radius, r:.17, color:pal.via});
  }
  B[0].nolink = true;              
  return [...A, ...B];
};

/** Confined random walk → the globular look of a folded chromatin domain. */
const buildChromatin = (seed, beads) => pal => {
  const rand = mulberry32(seed);
  const pts=[]; let x=0,y=0,z=0, hx=1,hy=.2,hz=.1;
  const norm=()=>{const l=Math.hypot(hx,hy,hz)||1;hx/=l;hy/=l;hz/=l;};
  norm();
  for(let i=0;i<beads;i++){
    pts.push([x,y,z]);
    const d = Math.hypot(x,y,z)/18;
    hx += (rand()-.5)*.85 - x*d; hy += (rand()-.5)*.85 - y*d; hz += (rand()-.5)*.85 - z*d;
    norm(); x+=hx*.55; y+=hy*.55; z+=hz*.55;
  }
  const cx=pts.reduce((s,p)=>s+p[0],0)/beads, cy=pts.reduce((s,p)=>s+p[1],0)/beads, cz=pts.reduce((s,p)=>s+p[2],0)/beads;
  return pts.map((p,i)=>{
    const tt=i/(beads-1);
    const color = tt<.5 ? mix(pal.from,pal.via,tt*2) : mix(pal.via,pal.to,(tt-.5)*2);
    return {x:p[0]-cx, y:p[1]-cy, z:p[2]-cz, r: i===0||i===beads-1 ? .3 : .14, color};
  });
};


const buildProtein = pdbId => pal => {
  const rand = mulberry32(hashSeed(pdbId.toUpperCase()));
  const pts=[]; let x=-4,y=-1.5,z=0, hx=1,hy=.35,hz=.2;
  const norm=()=>{const l=Math.hypot(hx,hy,hz)||1;hx/=l;hy/=l;hz/=l;};
  norm();
  for(let b=0;b<7;b++){
    const helix = b%2===0;
    if(helix){
      const steps=(2+Math.floor(rand()*2))*14, radius=.6, rise=.14;
      const ax=[hx,hy,hz];
      let sxv=[ax[1]*0-ax[2]*1, ax[2]*0-ax[0]*0, ax[0]*1-ax[1]*0];
      const sl=Math.hypot(...sxv)||1; sxv=sxv.map(v=>v/sl);
      const ov=[ax[1]*sxv[2]-ax[2]*sxv[1], ax[2]*sxv[0]-ax[0]*sxv[2], ax[0]*sxv[1]-ax[1]*sxv[0]];
      for(let i=0;i<=steps;i++){
        const a=(i/14)*Math.PI*2;
        pts.push({p:[x+ax[0]*i*rise+Math.cos(a)*radius*sxv[0]+Math.sin(a)*radius*ov[0],
                     y+ax[1]*i*rise+Math.cos(a)*radius*sxv[1]+Math.sin(a)*radius*ov[1],
                     z+ax[2]*i*rise+Math.cos(a)*radius*sxv[2]+Math.sin(a)*radius*ov[2]], helix:true});
      }
      const last=pts[pts.length-1].p; x=last[0]; y=last[1]; z=last[2];
    } else {
      const steps=5+Math.floor(rand()*4);
      for(let i=0;i<=steps;i++){
        pts.push({p:[x,y,z],helix:false});
        const d=Math.hypot(x,y,z)/40;
        hx+=(rand()-.5)*.9-x*d; hy+=(rand()-.5)*.9-y*d; hz+=(rand()-.5)*.9-z*d;
        norm(); x+=hx*.6; y+=hy*.6; z+=hz*.6;
      }
    }
  }
  const n=pts.length;
  const c=[0,1,2].map(i=>pts.reduce((s,q)=>s+q.p[i],0)/n);
  return pts.map(q=>({x:q.p[0]-c[0], y:q.p[1]-c[1], z:q.p[2]-c[2], r:q.helix?.22:.11, color:q.helix?pal.from:pal.to}));
};

/* ============================================================
   5. ROUTER + NAV
   ============================================================ */
const NAV = [
  {id:'overview',  key:'nav_overview',  icon:'boxes'},
  {id:'dashboard', key:'nav_patients',  icon:'users'},
  {id:'predict',   key:'nav_predict',   icon:'flask'},
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
   5. OVERVIEW  +  PROFILE   
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

    <p class="sm-t muted" style="margin-top:1.25rem">${ICON.info} ${t('pr_readonly')}</p>
  </div>`;
}

function renderRoute(){
  clearScenes();
  if (S.route==='landing'){ renderLanding(); return; }
  if (S.route==='login') return;
  const view = document.getElementById('view');
  ({overview:renderOverview, profile:renderProfile, dashboard:renderPatients, predict:renderPredict, settings:renderSettings,
    chromatin:renderChromatin, protein:renderProtein, patient:renderPatientDetail}[S.route] || renderPatients)(view);
}

/* ============================================================
   6. LANDING
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


const DNA_GLYPH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 2c0 5 10 5 10 10S7 17 7 22"/><path d="M17 2c0 5-10 5-10 10s10 5 10 10"/><path d="M9 5.5h6M10.5 12h3M9.5 18.5h5" stroke-width="1"/></svg>`;


function injectDnaField(host, count=14){
  if(!host) return;
  let html='';
  for(let i=0;i<count;i++){
    const left=(i*61+8)%100, top=(i*41+6)%100, dur=8+((i*5)%8), size=22+(i%3)*7, delay=((i%5)*0.7).toFixed(1), turn=5+((i*3)%7);
    html+=`<span class="dna-float" style="left:${left}%;top:${top}%;--dur:${dur}s;--delay:${delay}s;--sz:${size}px;--turn:${turn}s">${DNA_GLYPH}</span>`;
  }
  host.innerHTML=html;
}

/* كشف تدريجي (تلاشٍ + انزلاق) للعناصر  */
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
  const pulse = (s==='running'||s==='queued') ? 'pulse' : '';
  return `<span class="badge ${s}"><span class="dot ${pulse}"></span>${t('status_'+s)}</span>`;
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

/* صفحة تفاصيل المريض */
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
      <div class="xs muted" style="margin-top:.2rem">${fmtDate(g.created_at)} · ${esc(g.cell_type||'—')}</div>
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

/* ============================================================
   8. NEW PREDICTION (+ protein search)
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
          <select id="pfCell" class="select"><option value="" disabled ${!PF.cell?'selected':''}>${t('field_cell_type_ph')}</option>
          ${CELL_TYPES.map(c=>`<option value="${c.id}" ${PF.cell==c.id?'selected':''}>${c.name}</option>`).join('')}</select></div>
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
    <div style="margin-top:1.25rem">${proteinSearchHTML()}</div>
  </div>`;

  bindPredict(view);
  bindProteinSearch(view);
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

/* ---------- protein search (shared block) ---------- */
const PS = {gene:'', state:'idle', result:null};
function proteinSearchHTML(){
  let result = '';
  if (PS.state==='idle')
    result = `<p class="sm-t muted" style="text-align:center;border:1px dashed var(--border);border-radius:12px;padding:1.5rem">${t('protein_empty')}</p>`;
  if (PS.state==='not_found')
    result = `<div class="alert error">${ICON.alert}<span>${t('protein_not_found')}</span></div>`;
  if (PS.state==='result'){
    const r = PS.result;
    result = `<div class="fade" style="border:1px solid var(--border);border-radius:14px;padding:1rem;background:color-mix(in srgb,var(--background) 40%,transparent)">
      <p class="xs muted">${t('protein_result')}</p>
      <p style="font-weight:500;margin-top:.2rem">${esc(r.protein_name)}</p>
      <div class="cols2" style="margin-top:1rem">
        <div><p class="xs muted">${t('gene')}</p><p class="mono sm-t">${r.gene}</p></div>
        <div><p class="xs muted">${t('uniprot_id')}</p><p class="mono sm-t">${r.uniprot_id}</p></div>
      </div>
      <p class="xs muted" style="margin-top:1rem">${t('pdb_ids')}</p>
      <div class="row" style="flex-wrap:wrap;margin-top:.5rem">${r.pdb_ids.map(id=>`<span class="chip mono">${id}</span>`).join('')}</div>
      <button class="btn lg" style="width:100%;margin-top:1.25rem" id="openProtein">${ICON.dna}<span>${t('open_protein_viewer')}</span></button>
    </div>`;
  }
  return `<section class="card" style="padding:1.5rem">
    <div class="between" style="align-items:flex-start">
      <div>
        <div class="row"><h2 style="font-size:1.05rem;font-weight:500">${t('protein_title')}</h2><span class="pill">${t('optional')}</span></div>
        <p class="sm-t muted" style="margin-top:.25rem">${t('protein_subtitle')}</p>
      </div>
      <span class="ico" style="width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary)">${ICON.dna}</span>
    </div>
    <form id="proteinForm" class="field" style="margin-top:1.25rem">
      <label class="label" for="geneInput">${t('field_gene')}</label>
      <div class="row" style="align-items:stretch">
        <input id="geneInput" class="input mono" placeholder="${t('field_gene_ph')}" value="${esc(PS.gene)}" aria-invalid="${PS.state==='not_found'}">
        <button class="btn lg" type="submit" ${PS.state==='loading'||!PS.gene.trim()?'disabled':''} style="flex:0 0 auto">
          ${PS.state==='loading'?`<span class="spin"></span><span>${t('searching')}</span>`:`${ICON.search}<span>${t('search')}</span>`}
        </button>
      </div>
    </form>
    <div style="margin-top:1.25rem">${result}</div>
  </section>`;
}
function bindProteinSearch(view){
  const input = view.querySelector('#geneInput');
  const btn = view.querySelector('#proteinForm button[type=submit]');
  input?.addEventListener('input', e=>{ PS.gene=e.target.value; if(btn) btn.disabled = !PS.gene.trim(); });
  view.querySelector('#proteinForm')?.addEventListener('submit', async e=>{
    e.preventDefault();
    const gene = PS.gene.trim();
    if(!gene) return;
    PS.state='loading'; renderRoute();
    try {
      const data = await api.get('/genomics/search-protein/', { params:{ gene } });
      if (data && data.pdb_ids){
        PS.result = { gene:data.gene, uniprot_id:data.uniprot_id, protein_name:data.protein_name, pdb_ids:data.pdb_ids };
        PS.state = 'result';
      } else { PS.result=null; PS.state='not_found'; toast(t('protein_not_found'),'error'); }
    } catch(err){
      PS.result=null; PS.state='not_found';
      toast(t('protein_not_found'),'error');
    }
    renderRoute();
  });
  view.querySelector('#openProtein')?.addEventListener('click', ()=>{ S.activeProtein = PS.result; go('protein'); });
}

/* ============================================================
   9. SETTINGS — the only two controls that exist
   ============================================================ */
function renderSettings(view){
  const seg = (name, value, options) => `<div class="segmented" role="radiogroup" aria-label="${name}">
    ${options.map(o=>`<button role="radio" aria-checked="${o.v===value}" data-seg="${name}" data-v="${o.v}">${o.icon||''}<span>${o.label}</span></button>`).join('')}
  </div>`;
  view.innerHTML = `<div class="wrap" style="max-width:760px">
    <div class="head" style="margin-bottom:2rem"><h1>${t('settings_title')}</h1><p>${t('settings_subtitle')}</p></div>
    <div class="stack">
      <div class="card between" style="padding:1.25rem">
        <div><p style="font-weight:500">${t('theme')}</p><p class="sm-t muted" style="margin-top:.15rem">${t('theme_desc')}</p></div>
        ${seg('theme', theme, [{v:'light',label:t('theme_light'),icon:ICON.sun},{v:'dark',label:t('theme_dark'),icon:ICON.moon}])}
      </div>
      <div class="card between" style="padding:1.25rem">
        <div><p style="font-weight:500">${t('language')}</p><p class="sm-t muted" style="margin-top:.15rem">${t('language_desc')}</p></div>
        ${seg('lang', locale, [{v:'ar',label:t('lang_ar'),icon:ICON.lang},{v:'en',label:t('lang_en')}])}
      </div>
    </div>
  </div>`;
  view.querySelectorAll('[data-seg]').forEach(b=>b.onclick=()=>{
    if(b.dataset.seg==='theme'){ theme=b.dataset.v; applyTheme(); renderRoute(); }
    else { locale=b.dataset.v; applyLocale(); }
  });
}

/* ============================================================
   10. VIEWERS
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
  const beads = Math.min(220, Math.max(60, pts));
  bindViewer(view, createScene(view.querySelector('#chromatinCanvas'), buildChromatin(test.id, beads), {dist:13}));
}

function renderProtein(view){
  const p = S.activeProtein;
  if(!p){ viewerEmpty(view,'predict',t('protein_title')); return; }
  if(!S.activePdb || !p.pdb_ids.includes(S.activePdb)) S.activePdb = p.pdb_ids[0];

  const panel = `
    <div class="card" style="padding:1.25rem">
      <p style="font-weight:500">${esc(p.protein_name)}</p>
      <div style="margin-top:.75rem">
        ${row(t('gene'), `<span class="mono">${p.gene}</span>`)}
        ${row(t('uniprot_id'), `<span class="mono">${p.uniprot_id}</span>`)}
        ${row(t('pdb_ids'), fmtNum(p.pdb_ids.length))}
      </div>
    </div>
    <div class="card" style="padding:1.25rem">
      <label class="label" for="pdbSelect">${t('select_pdb')}</label>
      <select id="pdbSelect" class="select mono" style="margin-top:.5rem">
        ${p.pdb_ids.map(id=>`<option ${id===S.activePdb?'selected':''}>${id}</option>`).join('')}
      </select>
      <a class="btn outline" style="width:100%;margin-top:1rem" target="_blank" rel="noreferrer"
         href="https://www.rcsb.org/structure/${S.activePdb}">${ICON.external}<span>${t('viewer_open_rcsb')}</span></a>
    </div>`;

  view.innerHTML = viewerFrame({
    title:t('protein_viewer_title'), desc:t('protein_viewer_desc'),
    backRoute:'predict', backLabel:t('back'), panel, canvasId:'proteinCanvas'
  });
  bindViewer(view, createScene(view.querySelector('#proteinCanvas'), buildProtein(S.activePdb), {dist:14}));
  view.querySelector('#pdbSelect').onchange = e=>{ S.activePdb = e.target.value; renderRoute(); };
}

/* ============================================================
   11. WIRING
   ============================================================ */
document.querySelectorAll('.js-theme').forEach(b=>b.onclick=()=>{ theme = theme==='dark'?'light':'dark'; applyTheme(); if(S.route==='settings') renderRoute(); });
document.querySelectorAll('.js-lang').forEach(b=>b.onclick=()=>{ locale = locale==='en'?'ar':'en'; applyLocale(); });
document.querySelectorAll('.js-logout').forEach(b=>b.onclick=async()=>{
  try { if (_refreshToken) await api.post('/auth/logout/', { refresh:_refreshToken }); } catch(e){}
  clearTokens();
  go('login');
});

async function doLogin(e){
  if (e) e.preventDefault();
  const err = document.getElementById('loginError');
  const btn = document.getElementById('loginBtn');
  const u   = document.getElementById('username');
  const pw  = document.getElementById('password');
  if (err) err.hidden = true;

  const username = (u && u.value.trim()) || '';
  const password = (pw && pw.value) || '';
  if (!username || !password){
    if (err){ err.hidden = false; const s=err.querySelector('[data-t]'); if(s) s.textContent = t('login_error'); }
    return;
  }

  if (btn){ btn.disabled = true; btn.innerHTML = `<span class="spin"></span><span>${t('loading')}</span>`; }
  try {
    // POST /api/auth/login/  ->  { status, tokens:{access,refresh}, user }
    const data = await api.post('/auth/login/', { username, password });
    if (data.status !== 'success') throw new Error(data.message || 'login failed');

    saveTokens(data.tokens.access, data.tokens.refresh);
    const usr = data.user || {};
    USER.username     = usr.username || username;
    USER.email        = usr.email || '';
    USER.is_superuser = !!usr.is_superuser;
    USER.date_joined  = usr.date_joined || new Date().toISOString();

    if (btn){ btn.disabled = false; btn.innerHTML = `<span>${t('login_button')}</span>`; }
    await fetchCellTypes();     // تعبئة أنواع الخلايا الحقيقية لشاشة التحليل
    go('overview');
    loadPatients();
  } catch (ex) {
    console.error('[login]', ex.response ? ex.response.data : ex);
    if (btn){ btn.disabled = false; btn.innerHTML = `<span>${t('login_button')}</span>`; }
    if (err){
      err.hidden = false;
      const span = err.querySelector('[data-t]');
      if (span) span.textContent = (ex.response && ex.response.data && ex.response.data.message) || t('login_error');
    }
  }
}

const _lf = document.getElementById('loginForm');
if (_lf) _lf.addEventListener('submit', doLogin);
const _lb = document.getElementById('loginBtn');
if (_lb) _lb.addEventListener('click', doLogin);

document.getElementById('stateDemo')?.addEventListener('change', e=>{ S.demo = e.target.value; loadPatients(); });

applyTheme(); applyLocale();


injectDnaField(document.getElementById('loginDnaField'), 35);

(async function restoreSession(){
  if (!_accessToken) return;
  try {
    const me = await api.get('/auth/me/');
    USER.username     = me.username || USER.username;
    USER.email        = me.email || '';
    USER.is_superuser = !!me.is_superuser;
    USER.date_joined  = me.date_joined || USER.date_joined;
    await fetchCellTypes();
    go('overview');
    loadPatients();
  } catch(e){ clearTokens(); }
})();