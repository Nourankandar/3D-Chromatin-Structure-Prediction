/* ============================================================
   11. WIRING
   مستمعو الأحداث، تسجيل الدخول، استعادة الجلسة
   ============================================================ */
document.querySelectorAll('.js-theme').forEach(b=>b.onclick=()=>{ theme = theme==='dark'?'light':'dark'; applyTheme(); if(['settings','chromatin','protein'].includes(S.route)) renderRoute(); });
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

applyTheme(); applyLocale(); applyAccent();

/*  DNA حقن أشكال */
injectDnaField(document.getElementById('loginDnaField'), 14);

/* استعادة الجلسة: لو في توكن مخزّن وصالح، ادخل مباشرة بدل شاشة الترحيب/الدخول */
(async function restoreSession(){
  if (!_accessToken) return;
  try {
    const me = await api.get('/auth/MyAccountAPIView/');
    USER.username     = me.username || USER.username;
    USER.email        = me.email || '';
    USER.is_superuser = !!me.is_superuser;
    USER.date_joined  = me.date_joined || USER.date_joined;
    await fetchCellTypes();
    go('overview');
    loadPatients();
  } catch(e){ clearTokens(); }
})();
