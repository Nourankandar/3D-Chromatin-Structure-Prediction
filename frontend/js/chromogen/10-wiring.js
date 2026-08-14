/* ============================================================
   11. WIRING
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

/* ══════════════ نسيان / إعادة تعيين كلمة المرور ══════════════ */

document.querySelectorAll('#otpBoxes .otp-box').forEach((box,i,all)=>{
  box.addEventListener('input', ()=>{
    box.value = box.value.replace(/[^0-9]/g,'').slice(0,1);
    if(box.value && all[i+1]) all[i+1].focus();
  });
  box.addEventListener('keydown', e=>{
    if(e.key==='Backspace' && !box.value && all[i-1]) all[i-1].focus();
  });
});
function otpValue(){
  return [...document.querySelectorAll('#otpBoxes .otp-box')].map(b=>b.value).join('');
}

document.querySelectorAll('.js-eye').forEach(btn=>{
  const input = document.getElementById(btn.dataset.target);
  if(!input) return;
  btn.innerHTML = ICON.eye;
  btn.addEventListener('click', ()=>{
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.innerHTML = show ? ICON.eyeOff : ICON.eye;
  });
});

document.getElementById('newPassword')?.addEventListener('input', e=>{
  const v = e.target.value;
  let score = 0;
  if(v.length>=8) score=1;
  if(v.length>=8 && /[A-Z]/.test(v) && /[a-z]/.test(v)) score=2;
  if(v.length>=8 && /[A-Z]/.test(v) && /[a-z]/.test(v) && /[0-9]/.test(v) && /[!@#$%^&*(),.?":{}|<>\-_+=/\[\]~`]/.test(v)) score=3;
  const colors = ['#e5766f','#e0b24d','#8eb69b'];
  document.querySelectorAll('#pwStrength div').forEach((d,i)=>{
    d.style.height='4px'; d.style.borderRadius='2px';
    d.style.background = i<score ? colors[score-1] : 'var(--muted)';
  });
});

function apiErrorText(ex, fallback){
  const d = ex.response && ex.response.data;
  if(!d) return fallback;
  if(d.message) return d.message;
  const firstField = Object.values(d).find(v=>Array.isArray(v) && v.length);
  if(firstField) return firstField[0];
  return fallback;
}

let _resetEmail = '';

async function doForgotPassword(e){
  if(e) e.preventDefault();
  const err = document.getElementById('forgotError'), errText = document.getElementById('forgotErrorText');
  const btn = document.getElementById('forgotBtn');
  const email = (document.getElementById('forgotEmail').value||'').trim();
  err.hidden = true;
  if(!email){ err.hidden=false; errText.textContent = t('forgot_error'); return; }

  btn.disabled = true; btn.innerHTML = `<span class="spin"></span><span>${t('loading')}</span>`;
  try{
    await api.post('/auth/forgot-password/', { email });
    _resetEmail = email;
    document.getElementById('resetEmail').value = email;
    go('reset');
  }catch(ex){
    err.hidden = false; errText.textContent = apiErrorText(ex, t('forgot_error'));
  }finally{
    btn.disabled = false; btn.innerHTML = `<span>${t('forgot_button')}</span>`;
  }
}

async function doResetPassword(e){
  if(e) e.preventDefault();
  const err = document.getElementById('resetError'), errText = document.getElementById('resetErrorText');
  const btn = document.getElementById('resetBtn');
  const email = (document.getElementById('resetEmail').value||'').trim();
  const code = otpValue();
  const pw = document.getElementById('newPassword').value;
  const pw2 = document.getElementById('confirmPassword').value;
  err.hidden = true;

  const pwRule = /^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>\-_+=/\[\]~`]).{8,}$/;
  if(!pwRule.test(pw)){ err.hidden=false; errText.textContent = t('reset_tooshort'); return; }
  if(pw !== pw2){ err.hidden=false; errText.textContent = t('reset_mismatch'); return; }

  btn.disabled = true; btn.innerHTML = `<span class="spin"></span><span>${t('loading')}</span>`;
  try{
    await api.post('/auth/reset-password/', { email, code, new_password: pw });
    go('login');
    const le = document.getElementById('loginError');
    if(le){ le.hidden=false; le.classList.remove('error'); le.classList.add('info'); le.querySelector('span:last-child').textContent = t('reset_success'); }
  }catch(ex){
    err.hidden = false; errText.textContent = apiErrorText(ex, t('reset_error'));
  }finally{
    btn.disabled = false; btn.innerHTML = `<span>${t('reset_button')}</span>`;
  }
}

document.getElementById('forgotForm')?.addEventListener('submit', doForgotPassword);
document.getElementById('resetForm')?.addEventListener('submit', doResetPassword);

document.getElementById('signupPassword')?.addEventListener('input', e=>{
  const v = e.target.value;
  let score = 0;
  if(v.length>=8) score=1;
  if(v.length>=8 && /[A-Z]/.test(v) && /[a-z]/.test(v)) score=2;
  if(v.length>=8 && /[A-Z]/.test(v) && /[a-z]/.test(v) && /[0-9]/.test(v) && /[!@#$%^&*(),.?":{}|<>\-_+=/\[\]~`]/.test(v)) score=3;
  const colors = ['#e5766f','#e0b24d','#8eb69b'];
  document.querySelectorAll('#signupStrength div').forEach((d,i)=>{
    d.style.height='4px'; d.style.borderRadius='2px';
    d.style.background = i<score ? colors[score-1] : 'var(--muted)';
  });
});

/* ══════════════ تسجيل حساب جديد — 3 خطوات (initiate → verify → complete) ══════════════ */
const SU = {email:'', photo:null};

function signupShowStep(n){
  document.getElementById('signupStep1Form').hidden = n!==1;
  document.getElementById('signupStep2Form').hidden = n!==2;
  document.getElementById('signupStep3Form').hidden = n!==3;
}

// أرقام كود التحقق — نفس سلوك otpBoxes بشاشة استعادة كلمة المرور، بحاوية مستقلة
document.querySelectorAll('#signupOtpBoxes .signup-otp-box').forEach((box,i,all)=>{
  box.addEventListener('input', ()=>{
    box.value = box.value.replace(/[^0-9]/g,'').slice(0,1);
    if(box.value && all[i+1]) all[i+1].focus();
  });
  box.addEventListener('keydown', e=>{
    if(e.key==='Backspace' && !box.value && all[i-1]) all[i-1].focus();
  });
});
function signupOtpValue(){
  return [...document.querySelectorAll('#signupOtpBoxes .signup-otp-box')].map(b=>b.value).join('');
}
function signupOtpClear(){
  document.querySelectorAll('#signupOtpBoxes .signup-otp-box').forEach(b=> b.value='');
}

/* خطوة 1: إرسال الكود للإيميل */
async function doSignupInitiate(e){
  if(e) e.preventDefault();
  const err = document.getElementById('signupStep1Error'), errText = document.getElementById('signupStep1ErrorText');
  const btn = document.getElementById('signupStep1Btn');
  const email = (document.getElementById('signupInitEmail').value||'').trim();
  err.hidden = true;

  const emailRule = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if(!emailRule.test(email)){ err.hidden=false; errText.textContent = t('signup_email_required'); return; }

  btn.disabled = true; btn.innerHTML = `<span class="spin"></span><span>${t('loading')}</span>`;
  try{
    await api.post('/auth/signup/initiate/', { email });
    SU.email = email;
    document.getElementById('signupStep2Email').textContent = email;
    signupOtpClear();
    signupShowStep(2);
  }catch(ex){
    err.hidden = false; errText.textContent = apiErrorText(ex, t('signup_error'));
  }finally{
    btn.disabled = false; btn.innerHTML = `<span>${t('signup_step1_button')}</span>`;
  }
}
document.getElementById('signupStep1Form')?.addEventListener('submit', doSignupInitiate);

/* خطوة 2: التحقق من الكود */
async function doSignupVerify(e){
  if(e) e.preventDefault();
  const err = document.getElementById('signupStep2Error'), errText = document.getElementById('signupStep2ErrorText');
  const btn = document.getElementById('signupStep2Btn');
  const code = signupOtpValue();
  err.hidden = true;

  if(code.length !== 6){ err.hidden=false; errText.textContent = t('signup_code_error'); return; }

  btn.disabled = true; btn.innerHTML = `<span class="spin"></span><span>${t('loading')}</span>`;
  try{
    await api.post('/auth/signup/verify/', { email: SU.email, code });
    signupShowStep(3);
  }catch(ex){
    err.hidden = false; errText.textContent = apiErrorText(ex, t('signup_error'));
  }finally{
    btn.disabled = false; btn.innerHTML = `<span>${t('signup_step2_button')}</span>`;
  }
}
document.getElementById('signupStep2Form')?.addEventListener('submit', doSignupVerify);

document.getElementById('signupBackTo1')?.addEventListener('click', e=>{ e.preventDefault(); signupShowStep(1); });

document.getElementById('signupResendBtn')?.addEventListener('click', async e=>{
  e.preventDefault();
  const link = e.currentTarget;
  const original = link.textContent;
  try{
    await api.post('/auth/signup/initiate/', { email: SU.email });
    link.textContent = t('signup_resend_sent');
    setTimeout(()=>{ link.textContent = original; }, 2500);
  }catch(ex){
    const err = document.getElementById('signupStep2Error'), errText = document.getElementById('signupStep2ErrorText');
    err.hidden = false; errText.textContent = apiErrorText(ex, t('signup_error'));
  }
});

/* رفع/معاينة الصورة الشخصية (اختياري) */
document.getElementById('signupPhotoBtn')?.addEventListener('click', ()=> document.getElementById('signupPhotoInput').click());
document.getElementById('signupPhotoInput')?.addEventListener('change', e=>{
  const file = e.target.files[0];
  if(!file) return;
  SU.photo = file;
  const reader = new FileReader();
  reader.onload = ev=>{
    const box = document.getElementById('signupPhotoPreview');
    box.style.backgroundImage = `url(${ev.target.result})`;
    box.querySelector('[data-icon]')?.remove();
  };
  reader.readAsDataURL(file);
});

/* خطوة 3: بيانات الحساب النهائية + الصورة */
async function doSignupComplete(e){
  if(e) e.preventDefault();
  const err = document.getElementById('signupStep3Error'), errText = document.getElementById('signupStep3ErrorText');
  const btn = document.getElementById('signupBtn');
  const username = (document.getElementById('signupUsername').value||'').trim();
  const pw = document.getElementById('signupPassword').value;
  const pw2 = document.getElementById('signupConfirm').value;
  err.hidden = true;

  const pwRule = /^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>\-_+=/\[\]~`]).{8,}$/;
  if(!username){ err.hidden=false; errText.textContent = t('signup_error'); return; }
  if(!pwRule.test(pw)){ err.hidden=false; errText.textContent = t('reset_tooshort'); return; }
  if(pw !== pw2){ err.hidden=false; errText.textContent = t('reset_mismatch'); return; }

  btn.disabled = true; btn.innerHTML = `<span class="spin"></span><span>${t('loading')}</span>`;
  try{
    const fd = new FormData();
    fd.append('email', SU.email);
    fd.append('username', username);
    fd.append('password', pw);
    if(SU.photo) fd.append('profile_image', SU.photo);

    await api.post('/auth/signup/complete/', fd);

    go('login');
    signupShowStep(1);
    const le = document.getElementById('loginError');
    if(le){ le.hidden=false; le.classList.remove('error'); le.classList.add('info'); le.querySelector('span:last-child').textContent = t('signup_success'); }
    document.getElementById('username').value = username;
  }catch(ex){
    err.hidden = false; errText.textContent = apiErrorText(ex, t('signup_error'));
  }finally{
    btn.disabled = false; btn.innerHTML = `<span>${t('signup_step3_button')}</span>`;
  }
}
document.getElementById('signupStep3Form')?.addEventListener('submit', doSignupComplete);

applyTheme(); applyLocale(); applyAccent();

/*  DNA حقن أشكال */
injectDnaField(document.getElementById('loginDnaField'), 14);

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
