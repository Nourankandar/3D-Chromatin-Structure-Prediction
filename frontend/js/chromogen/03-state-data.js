/* ============================================================
    أنواع الخلايا، المرضى، متابعة حالة التحاليل الجارية 
   ============================================================ */

/* ============================================================
   STATUS 
   ============================================================ */
const STATUS_GROUP = {
  pending:               'pending',
  predicting_dnase:      'running',
  generating_hic:        'running',
  generating_hic_coords: 'running',
  scanning_motifs:       'running',
  cancelling:            'running',
  cancelled:             'cancelled',
  completed:             'completed',
  failed:                'failed',
};

const RUNNING_SET  = Object.keys(STATUS_GROUP).filter(s => ['pending','running'].includes(STATUS_GROUP[s]));

const TERMINAL_SET = ['completed','failed','cancelled'];

function statusGroup(s){ return STATUS_GROUP[s] || 'pending'; }
function statusLabel(s){ return t('status_'+s) || s; }





let CELL_TYPES = [];

async function fetchCellTypes(){
  try {
    const data = await api.get('/genomics/cell-types/');
    const raw = data.cell_types || data.results || data || [];
    CELL_TYPES = raw.map(c=>({
      id: c.id,
      name: c.name,
      eid: c.target_basset_track_id,
      desc: c.description || ''
    }));
  } catch(e){
    console.error('[cell-types]', e.response ? e.response.data : e);
    CELL_TYPES = [];
  }
}
/* عمليات أنواع الخلايا —( CRUD ) */
async function createCellType(payload){
  return api.post('/genomics/cell-types/', payload);
}
async function updateCellType(id, payload){
  return api.patch(`/genomics/cell-types/${id}/`, payload);
}
async function deleteCellType(id){
  return api.del(`/genomics/cell-types/${id}/`);
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
  expanded:null, editing:null, activeTest:null, activeProtein:null, activePatient:null, proteinSearching:false,
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

    // 2) تحاليل كل مريض   
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

/*  استعلام دوري عن  حتى الاكتمال */
const _pollTimers = {};
function stopPolling(inputId){
  if (_pollTimers[inputId]) { clearInterval(_pollTimers[inputId]); delete _pollTimers[inputId]; }
}
function pollTestStatus(inputId){
  stopPolling(inputId);
  _pollTimers[inputId] = setInterval(async ()=>{
    try {
      const st = await api.get(`/genomics/test-status/${inputId}/`);
      S.patients.forEach(p=>p.genomic_inputs.forEach(g=>{
        if (g.id===inputId){ g.status = st.status; if (st.output_data_id) g.output_data_id = st.output_data_id; }
      }));
      if (S.route==='dashboard') renderRoute();
      if (st.status==='completed' || st.status==='failed'){
        stopPolling(inputId);
        if (st.status==='completed') toast(t('toast_test_completed') || 'اكتمل التحليل بنجاح');
        else toast('فشل التحليل — راجعي السيرفر','error');
      }
    } catch(e){
      if (e.response && e.response.status===404){ stopPolling(inputId); return; }
      /* خطأ مؤقت — منكمّل الاستعلام */
    }
  }, 4000);
}
