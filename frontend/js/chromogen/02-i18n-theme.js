/* ============================================================
   1. i18n
   قاموس عربي/إنجليزي، الثيم (فاتح/غامق)، الألوان، تنسيق الأرقام والتواريخ والمناطق الجينومية.
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
    nav_cells:'Cell types',
    cells_title:'Cell types', cells_desc:'Manage the cell types used in genomic analyses',
    cells_add:'Add cell type', cells_manage:'Manage cell types', cells_list:'Added types',
    cells_name:'Cell type name', cells_name_ph:'e.g. Liver', cells_eid:'Enformer track ID',
    cells_eid_ph:'0 - 163', cells_desc_f:'Description (optional)', cells_desc_ph:'Short description',
    cells_hint:'The track ID determines which cell type the model predicts.',
    cells_save:'Save', cells_update:'Update', cells_cancel:'Cancel', cells_empty:'No cell types yet.',
    cells_added:'Cell type added', cells_updated:'Cell type updated', cells_deleted:'Cell type deleted',
    cells_err_name:'Name is required', cells_err_eid:'Track ID must be between 0 and 163',
    cells_confirm_del:'Delete this cell type?', cells_err_save:'Could not save. Check the values and try again.',
    pw_title:'Change password', pw_desc:'Update the password you use to sign in',
    pw_old:'Current password', pw_old_ph:'Enter your current password',
    pw_new:'New password', pw_new_ph:'At least 6 characters',
    pw_confirm:'Confirm new password', pw_confirm_ph:'Re-enter the new password',
    pw_submit:'Update password', pw_saving:'Updating…',
    pw_ok:'Password changed', pw_err_required:'All fields are required',
    pw_err_short:'New password must be at least 6 characters',
    pw_err_match:'The new passwords do not match',
    pw_err_same:'The new password must differ from the current one',
    pw_err_wrong:'Current password is incorrect', pw_err_generic:'Could not change the password. Try again.',
    protein_predicted_note:'No experimental structure — showing an AlphaFold prediction',
    protein_predicted_badge:'Predicted structure (AlphaFold) — not experimentally determined',
    protein_source:'Structure source', viewer_open_alphafold:'Open in AlphaFold',
    ov_patients:'Patients', ov_tests:'Total tests', ov_completed:'Completed', ov_running:'Running', ov_failed:'Failed',
    ov_success:'Success rate', ov_avg:'Avg tests / patient', ov_recent:'Recent tests', ov_derived:'Derived in the browser — no extra API',
    pr_title:'Profile', pr_subtitle:'Your account details',
    pr_username:'Username', pr_email:'Email', pr_role:'Role', pr_joined:'Joined',
    pr_superuser:'Superuser', pr_staff:'Administrator',
    login_title:'Sign in', login_subtitle:'Access your genomic analysis workspace', username:'Username', password:'Password',
    login_button:'Sign in', login_error:'Login failed. Please check your credentials and try again.',
    logout:'Log out', login_hint:'Demo: any username and password will sign you in.',
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
    settings_title:'Settings',
    theme:'Theme', theme_light:'Light', theme_dark:'Dark', theme_desc:'Choose how the workspace looks.',
    language:'Language', lang_ar:'العربية', lang_en:'English', language_desc:'Switch the interface language and its direction.',
    chromatin_viewer_title:'3D Chromatin viewer', chromatin_viewer_desc:'Interactive view of the predicted chromatin structure.',
    protein_viewer_title:'3D Protein viewer', protein_viewer_desc:'Interactive view of the protein structure.',
    viewer_hint:'Drag to rotate · scroll to zoom', viewer_no_data:'No structure to display. Open a viewer from a completed result.',
    viewer_reset:'Reset view', viewer_autorotate:'Auto-rotate', viewer_points:'Analysis points',
    viewer_open_rcsb:'Open on RCSB', select_pdb:'PDB structure', summary:'Summary', region_size:'Region size',
    viewer_compare_control:'Compare with healthy control', viewer_report:'Report',
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
    nav_cells:'أنواع الخلايا',
    cells_title:'أنواع الخلايا', cells_desc:'إدارة أنواع الخلايا المستخدمة في التحاليل الجينومية',
    cells_add:'إضافة نوع خلية', cells_manage:'إدارة أنواع الخلايا', cells_list:'الأنواع المضافة',
    cells_name:'اسم نوع الخلية', cells_name_ph:'مثال: Liver', cells_eid:'Enformer track ID',
    cells_eid_ph:'0 - 163', cells_desc_f:'الوصف (اختياري)', cells_desc_ph:'وصف مختصر',
    cells_hint:'رقم الـ track يحدّد أي نوع خلية يتنبأ به الموديل.',
    cells_save:'حفظ', cells_update:'تحديث', cells_cancel:'إلغاء', cells_empty:'لا توجد أنواع خلايا بعد.',
    cells_added:'تمت إضافة نوع الخلية', cells_updated:'تم تحديث نوع الخلية', cells_deleted:'تم حذف نوع الخلية',
    cells_err_name:'الاسم مطلوب', cells_err_eid:'رقم الـ track يجب أن يكون بين 0 و 163',
    cells_confirm_del:'حذف نوع الخلية هذا؟', cells_err_save:'تعذّر الحفظ. تحقّق من القيم وحاولي مجدداً.',
    pw_title:'تغيير كلمة المرور', pw_desc:'تحديث كلمة المرور المستخدمة لتسجيل الدخول',
    pw_old:'كلمة المرور الحالية', pw_old_ph:'أدخل كلمة المرور الحالية',
    pw_new:'كلمة المرور الجديدة', pw_new_ph:'٦ أحرف على الأقل',
    pw_confirm:'تأكيد كلمة المرور الجديدة', pw_confirm_ph:'أعد إدخال كلمة المرور الجديدة',
    pw_submit:'تحديث كلمة المرور', pw_saving:'جاري التحديث…',
    pw_ok:'تم تغيير كلمة المرور', pw_err_required:'جميع الحقول مطلوبة',
    pw_err_short:'كلمة المرور الجديدة يجب أن تكون ٦ أحرف على الأقل',
    pw_err_match:'كلمتا المرور الجديدتان غير متطابقتين',
    pw_err_same:'كلمة المرور الجديدة يجب أن تختلف عن الحالية',
    pw_err_wrong:'كلمة المرور الحالية غير صحيحة', pw_err_generic:'تعذّر تغيير كلمة المرور. حاول مجدداً.',
    protein_predicted_note:'لا توجد بنية تجريبية — يُعرض تنبؤ AlphaFold',
    protein_predicted_badge:'بنية متوقّعة (AlphaFold) — غير محدّدة تجريبياً',
    protein_source:'مصدر البنية', viewer_open_alphafold:'فتح في AlphaFold',
    ov_patients:'المرضى', ov_tests:'إجمالي التحاليل', ov_completed:'مكتملة', ov_running:'قيد المعالجة', ov_failed:'فشل',
    ov_success:'نسبة النجاح', ov_avg:'متوسّط التحاليل لكل مريض', ov_recent:'آخر التحاليل', ov_derived:'محسوبة في المتصفّح — بدون أي API إضافي',
    pr_title:'الملف الشخصي', pr_subtitle:'تفاصيل حسابك',
    pr_username:'اسم المستخدم', pr_email:'البريد الإلكتروني', pr_role:'الصلاحية', pr_joined:'تاريخ الانضمام',
    pr_superuser:'مشرف عام', pr_staff:'مسؤول', 
    login_title:'تسجيل الدخول', login_subtitle:'ادخل إلى مساحة عمل التحليل الجينومي', username:'اسم المستخدم', password:'كلمة المرور',
    login_button:'تسجيل الدخول', login_error:'فشل تسجيل الدخول. يرجى التحقق من بياناتك والمحاولة مرة أخرى.',
    logout:'تسجيل الخروج', login_hint:'تجريبي: أي اسم مستخدم وكلمة مرور سيسجّلان الدخول.',
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
    settings_title:'الإعدادات',
    theme:'السمة', theme_light:'فاتح', theme_dark:'داكن', theme_desc:'اختر مظهر مساحة العمل.',
    language:'اللغة', lang_ar:'العربية', lang_en:'English', language_desc:'بدّل لغة الواجهة واتجاهها.',
    chromatin_viewer_title:'عارض الكروماتين ثلاثي الأبعاد', chromatin_viewer_desc:'عرض تفاعلي لبنية الكروماتين المتوقّعة.',
    protein_viewer_title:'عارض البروتين ثلاثي الأبعاد', protein_viewer_desc:'عرض تفاعلي لبنية البروتين.',
    viewer_hint:'اسحب للتدوير · مرّر للتكبير', viewer_no_data:'لا توجد بنية للعرض. افتح العارض من نتيجة مكتملة.',
    viewer_reset:'إعادة ضبط العرض', viewer_autorotate:'دوران تلقائي', viewer_points:'نقاط التحليل',
    viewer_open_rcsb:'فتح في RCSB', select_pdb:'بنية PDB', summary:'الملخص', region_size:'حجم المنطقة',
    viewer_compare_control:'قارن مع العيّنة السليمة', viewer_report:'التقرير',
    toast_patient_added:'تمت إضافة المريض.', toast_patient_updated:'تم تحديث المريض.', toast_patient_deleted:'تم حذف المريض.',
    toast_test_deleted:'تم حذف الاختبار.', toast_retry_started:'أُعيدت جدولة الاختبار.', toast_error:'حدث خطأ ما. يرجى المحاولة مرة أخرى.',
  }
};
let locale = 'en', theme = 'dark';
let accent = (()=>{ try{ return localStorage.getItem('chromogen-accent') || 'green'; }catch(e){ return 'green'; } })();
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

/* -- نظام الثيمات اللونية  --*/
const ACCENTS = [
  { id:'green',  label:'أخضر',   labelEn:'Green',  swatch:'#8eb69b' },   // الافتراضي
  { id:'blue',   label:'أزرق',   labelEn:'Blue',   swatch:'#7087bb' },
  { id:'purple', label:'بنفسجي', labelEn:'Purple', swatch:'#9f86c0' },
  { id:'lilac',  label:'ليلكي',  labelEn:'Lilac',  swatch:'#9c8ba9' },
  { id:'rose',   label:'زهري',   labelEn:'Rose',   swatch:'#c67c71' },
  { id:'wine',   label:'خمري',   labelEn:'Wine',   swatch:'#6d2932' },
  { id:'gold',   label:'ذهبي',   labelEn:'Gold',   swatch:'#c9a84c' },
  { id:'slate',  label:'رمادي',  labelEn:'Slate',  swatch:'#57707a' },
];
function applyAccent(){
  if(accent && accent!=='green') document.documentElement.setAttribute('data-accent', accent);
  else document.documentElement.removeAttribute('data-accent');
  try{ localStorage.setItem('chromogen-accent', accent); }catch(e){}
  scenes.forEach(s => s.refreshColors && s.refreshColors());
}

/* ---------- تنسيق ---------- */
const nf = () => new Intl.NumberFormat(locale==='ar'?'ar-EG':'en-US');
const fmtNum = n => nf().format(n);
const fmtDate = iso => new Intl.DateTimeFormat(locale==='ar'?'ar-EG':'en-US',{year:'numeric',month:'short',day:'numeric'}).format(new Date(iso));
const fmtRegion = bp => bp<=0 ? '—' : bp>=1e6 ? `${fmtNum(Math.round(bp/1e4)/100)} Mb` : `${fmtNum(Math.round(bp/100)/10)} kb`;
const estPoints = (s,e) => Math.max(1, Math.round((e-s)/5000));
