/* ============================================================
   -1. BACKEND  
   ============================================================ */
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
  const skip = url.includes('/auth/login') || url.includes('/auth/token/refresh') || url.includes('/auth/logout');

  if (status === 401 && !orig._retried && !skip && _refreshToken){
    orig._retried = true;
    try {
      const rr = await axios.post(API_BASE + '/auth/token/refresh/', { refresh: _refreshToken });
      saveTokens(rr.data.access, rr.data.refresh || _refreshToken);
      orig.headers = orig.headers || {};
      orig.headers['Authorization'] = 'Bearer ' + _accessToken;
      return axios(orig);   
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
   0. ICONS
   ============================================================ */
const I = (p,extra="") => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ${extra}>${p}</svg>`;
const ICON = {
  dna:      I('<path d="M6 3c0 6 12 6 12 12M6 21c0-6 12-6 12-12"/><path d="M7 6h10M7 18h10M8.5 9.5h7M8.5 14.5h7" stroke-width="1.1"/>'),
  file:     I('<path d="M14 3v5h5M6 3h9l5 5v13H6z"/><path d="M9 13h6M9 17h6"/>'),
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
  edit:     I('<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
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
