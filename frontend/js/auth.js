// ══ المحرك الصوتي الذكي (Web Audio API) ══
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playTechSound(type) {
    // المتصفحات بتطلب تفاعل المستخدم أولاً لتشغيل الصوت، هاد السطر بيضمن إنو يشتغل
    if (audioCtx.state === 'suspended') audioCtx.resume();
    
    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    
    if (type === 'click') {
        // نغمة "Blip" رقمية ناعمة ومريحة للأذن
        oscillator.type = 'sine';
        // تردد عالي بالبداية وبينزل بسرعة ليعطي إحساس اللمس الناعم
        oscillator.frequency.setValueAtTime(1500, audioCtx.currentTime); 
        oscillator.frequency.exponentialRampToValueAtTime(800, audioCtx.currentTime + 0.03); 
        // مستوى الصوت (خافت جداً)
        gainNode.gain.setValueAtTime(0.01, audioCtx.currentTime); 
        gainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.03);
        
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.03); // مدة أقصر بكثير (0.03 ثانية)
    } else if (type === 'success') {
        // رنة نجاح قصيرة
        oscillator.type = 'triangle';
        oscillator.frequency.setValueAtTime(400, audioCtx.currentTime);
        oscillator.frequency.setValueAtTime(600, audioCtx.currentTime + 0.1);
        gainNode.gain.setValueAtTime(0.02, audioCtx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 0.3);
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.3);
    } else if (type === 'error') {
        // نغمة خطأ تنبيهية
        oscillator.type = 'sawtooth';
        oscillator.frequency.setValueAtTime(150, audioCtx.currentTime);
        gainNode.gain.setValueAtTime(0.02, audioCtx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 0.3);
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.3);
    }
}

// مراقب ذكي بيشغل صوت "كليك" لما تضغطي على أي زر أو كرت بالنظام بدون ما نعدل الـ HTML
document.addEventListener('click', (e) => {
    if (e.target.closest('button') || e.target.closest('.patient-item-card') || e.target.closest('.sidebar-btn')) {
        playTechSound('click');
    }
});


// ══ دالة الإشعارات الفخمة (المحدثة لتشغيل الصوت) ══
window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    // تشغيل الصوت المناسب للإشعار
    playTechSound(type);
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '💡';
    if(type === 'success') icon = '✓';
    if(type === 'error') icon = '⚠';
    
    toast.innerHTML = `<span class="toast-icon">${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'fadeOutToast 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards';
        setTimeout(() => toast.remove(), 400); 
    }, 3500);
}

// ══ قراءة قيمة الكوكي (مستخدمة لجلب رمز CSRF من Django) ══
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// ══ نظام التحميل الذكي (Axios Interceptors) ══
// هاد الكود بيشتغل تلقائياً مع أي Request بيطلع للسيرفر
axios.interceptors.request.use(function (config) {
    const loader = document.getElementById('dna-loader-overlay');
    if(loader) loader.classList.add('active');

    // 🌟 إرسال رمز CSRF تلقائياً مع كل طلب (مطلوب من Django لطلبات POST/PATCH/DELETE)
    const csrfToken = getCookie('csrftoken');
    if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
    }

    return config;
}, function (error) {
    const loader = document.getElementById('dna-loader-overlay');
    if(loader) loader.classList.remove('active');
    return Promise.reject(error);
});

// وهاد الكود بيطفي التحميل فوراً لما يوصل الرد
axios.interceptors.response.use(function (response) {
    const loader = document.getElementById('dna-loader-overlay');
    if(loader) loader.classList.remove('active');
    return response;
}, function (error) {
    const loader = document.getElementById('dna-loader-overlay');
    if(loader) loader.classList.remove('active');
    return Promise.reject(error);
});

// تفعيل الكوكيز للتعامل مع جلسات جانغو
axios.defaults.withCredentials = true;

async function handleLogin() {
    console.log("جاري محاولة تسجيل الدخول...");
    
    const user = document.getElementById('adminUser').value;
    const pass = document.getElementById('adminPass').value;

    if (!user || !pass) {
        showToast("الرجاء إدخال اسم المستخدم وكلمة المرور أولاً!", "error");
        return;
    }

    try {
        const response = await axios.post('http://127.0.0.1:8000/api/auth/login/', {
            username: user,
            password: pass
        }, {
            headers: {
                'Content-Type': 'application/json'
            }
        });

        // داخل ملف js/auth.js
        if (response.data.status === 'success') {
            console.log("تم الدخول بنجاح!");
            
            // 1. إخفاء واجهة الدخول تماماً
            document.getElementById('login-container').style.display = 'none';
            
            // 2. إظهار حاوية الداشبورد الكبرى
            const dashContainer = document.getElementById('dashboard-container');
            dashContainer.style.display = 'block';
            
            // 3. تنظيف الواجهات القديمة وتفعيل البروفايل فقط عند الدخول
            // إزالة التفعيل عن كل الشاشات
            document.querySelectorAll('.sub-view').forEach(view => view.classList.remove('active'));
            // إزالة التفعيل عن كل أزرار القائمة الجانبية
            document.querySelectorAll('.sidebar-btn').forEach(btn => btn.classList.remove('active'));

            // تفعيل شاشة الملف الشخصي
            const profileView = document.getElementById('profile-subview');
            if (profileView) profileView.classList.add('active');

            // تفعيل زر الملف الشخصي في القائمة الجانبية ليتغير لونه
            const profileBtn = document.querySelector('button[onclick*="profile-subview"]');
            if (profileBtn) profileBtn.classList.add('active');

            // 4. جلب البيانات فوراً
            if (typeof fetchPatients === "function") {
                fetchPatients(); 
            }
        }
        else {
            alert("اسم المستخدم أو كلمة المرور غير صحيحة.");
        }
        
    } catch (error) {
        console.error("تفاصيل الخطأ:", error.response ? error.response.data : error);
       showToast("فشل الدخول. تأكد من اسم المستخدم وكلمة السر، أو أن سيرفر جانغو يعمل.", "error");
    }
    
}

async function handleLogout() {
    try {
        const response = await axios.post('http://127.0.0.1:8000/api/auth/logout/');

        if (response.data.status === 'success') {
            // 🌟 توحيد استخدام الـ containers لتجنب الشاشة البيضاء
            document.getElementById('dashboard-container').style.display = 'none';
            document.getElementById('login-container').style.display = 'flex';
            
            console.log("تم تسجيل الخروج بنجاح من السيرفر");
        }
    } catch (error) {
        console.error("حدث خطأ أثناء محاولة تسجيل الخروج:", error);
        alert("حدث خطأ ما، يرجى المحاولة لاحقاً.");
    }
}

function togglePasswordReset(show) {
    document.getElementById('login-form-block').style.display = show ? 'none' : 'block';
    document.getElementById('reset-form-block').style.display = show ? 'block' : 'none';
}

function handleResetPassword() {
    alert("تم إرسال رابط إعادة تعيين كلمة المرور إلى البريد الإلكتروني المدخل بنجاح.");
    togglePasswordReset(false);
}