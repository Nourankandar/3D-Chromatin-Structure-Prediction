axios.defaults.withCredentials = true;
// 🌟 تحديث الرابط الأساسي ليتوافق مع الروابط الجديدة في core/urls.py
const API_BASE_URL = 'http://127.0.0.1:8000/api';

let selectedPatient = null;
let patientsDatabase = []; 

function switchSubView(viewId, btnElement) {
    document.querySelectorAll('.sub-view').forEach(view => view.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');

    document.querySelectorAll('.sidebar-btn').forEach(btn => btn.classList.remove('active'));
    btnElement.classList.add('active'); // تم تصحيح btnElement.add إلى classList.add

    if (viewId === 'patients-list-subview' || viewId === 'new-test-subview') {
        fetchPatients(); // تحديث القوائم
    }
}

// 🌟 1. دالة إضافة المريض (بدون ملفات، بيانات فقط)
async function addNewPatientSubmit() {
    const data = {
        mrn: document.getElementById('patientMRN').value,
        name: document.getElementById('patientName').value,
        gender: document.getElementById('patientGender').value,
        dob: document.getElementById('patientDOB').value
    };

    if (!data.mrn || !data.name || !data.dob) {
        alert("الرجاء تعبئة جميع بيانات المريض!");
        return;
    }

    try {
        await axios.post(`${API_BASE_URL}/patients/`, data);
        alert("تم تسجيل المريض بنجاح!");
        document.getElementById('patientMRN').value = '';
        document.getElementById('patientName').value = '';
        fetchPatients();
    } catch (e) {
        console.error("خطأ:", e.response ? e.response.data : e);
        alert("خطأ في الإرسال، تفقد الـ Console.");
    }
}

// 🌟 2. دالة إضافة اختبار جيني جديد (الـ Pipeline)
async function addNewTestSubmit() {
    const formData = new FormData();
    const patientId = document.getElementById('testPatientSelect').value;
    const fileInput = document.getElementById('testDnaFile').files[0];

    if (!patientId || !fileInput) {
        alert("الرجاء اختيار المريض وملف الـ DNA!");
        return;
    }

    formData.append('patient', patientId); // ربط الاختبار بالمريض
    formData.append('cell_type', document.getElementById('testCellType').value);
    formData.append('chromosome', document.getElementById('testChromosome').value);
    formData.append('start_pos', document.getElementById('testStartPos').value);
    formData.append('end_pos', document.getElementById('testEndPos').value);
    formData.append('dna_sequence_file', fileInput);

    try {
        await axios.post(`${API_BASE_URL}/tests/`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        alert("تم رفع الاختبار بنجاح، جاري التنبؤ بالخلفية!");
        fetchPatients();
    } catch (e) {
        console.error("تفاصيل الخطأ:", e.response ? e.response.data : e);
        alert("حدث خطأ أثناء رفع الاختبار.");
    }
}

// 🌟 3. جلب المرضى وتعبئة القوائم
async function fetchPatients() {
    try {
        const response = await axios.get(`${API_BASE_URL}/patients/`);
        patientsDatabase = response.data; 
        refreshPatientsList();
        populatePatientDropdown(); // تحديث قائمة الـ Select في شاشة إضافة الاختبار
    } catch (e) {
        console.error("خطأ في جلب بيانات المرضى:", e);
    }
}

function populatePatientDropdown() {
    const select = document.getElementById('testPatientSelect');
    if (!select) return;
    select.innerHTML = '<option value="">-- اختر مريضاً --</option>';
    patientsDatabase.forEach(p => {
        select.innerHTML += `<option value="${p.id}">${p.name} (${p.mrn})</option>`;
    });
}

function refreshPatientsList() {
    const container = document.getElementById('patients-cards-container');
    if (!container) return; 
    container.innerHTML = "";

    if (!Array.isArray(patientsDatabase) || patientsDatabase.length === 0) {
        container.innerHTML = "<p style='color:var(--text-muted); padding:10px;'>لا يوجد مرضى مسجلين حالياً.</p>";
        return;
    }

    patientsDatabase.forEach(p => {
        const card = document.createElement('div');
        card.className = "patient-item-card";
        card.style.cursor = "pointer"; 
        card.innerHTML = `
            <h4 style="margin:0 0 5px 0; color:#38bdf8;">${p.name || 'مريض غير مسمى'}</h4>
            <span style="font-size:12px; color:var(--text-muted);">الرقم (MRN): ${p.mrn}</span>
        `;
        card.onclick = () => showPatientDetails(p);
        container.appendChild(card);
    });
}

// 🌟 4. عرض تفاصيل المريض والاختبارات المرتبطة به
function showPatientDetails(patient) {
    selectedPatient = patient;
    document.getElementById('detName').innerText = `المريض: ${patient.name}`;
    document.getElementById('detID').innerText = `الرقم الطبي (MRN): ${patient.mrn}`;
    document.getElementById('detGenderDOB').innerText = `الجنس: ${patient.gender === 'M' ? 'ذكر' : 'أنثى'} | المواليد: ${patient.dob}`;
    
    // فحص ما إذا كان لديه اختبارات (حسب الـ related_name في الجانغو)
    // افترضنا أن الـ serializer يرجع الـ tests تحت اسم genomic_inputs أو مشابه
    if (patient.genomic_inputs && patient.genomic_inputs.length > 0) {
        const latestTest = patient.genomic_inputs[patient.genomic_inputs.length - 1]; // أحدث اختبار
        
        if (latestTest.status === 'completed' && latestTest.report) {
            document.getElementById('detReport').innerHTML = `
                <span style="color:#22c55e;">[مكتمل]</span><br>
                ${latestTest.report.summary_text}
            `;
        } else {
            document.getElementById('detReport').innerText = `الحالة الحالية: ${latestTest.status}... جاري المعالجة بواسطة الـ AI`;
        }
    } else {
        document.getElementById('detReport').innerText = "لا توجد أي تحاليل (Tests) مرتبطة بهذا المريض حتى الآن.";
    }
    
    document.getElementById('actionButtons').style.display = 'block';
}

async function deletePatient(patientId) {
    if(confirm("هل أنت متأكد من حذف هذا المريض وكل تحاليله وتقاريره؟")) {
        try {
            await axios.delete(`${API_BASE_URL}/patients/${patientId}/`);
            alert("تم حذف المريض بنجاح.");
            document.getElementById('detName').innerText = "الرجاء اختيار مريض...";
            document.getElementById('detID').innerText = "";
            document.getElementById('detGenderDOB').innerText = "";
            document.getElementById('detReport').innerText = "---";
            document.getElementById('actionButtons').style.display = 'none';
            fetchPatients(); 
        } catch (e) {
            console.error("خطأ أثناء الحذف:", e);
        }
    }
}

function updatePatientSubmit(patientId) {
    if (!patientId || !selectedPatient) return;
    const nameHeader = document.getElementById('detName');
    if (nameHeader.querySelector('input')) {
        savePatientNameSubmit(patientId);
        return;
    }
    const currentName = selectedPatient.name || "";
    nameHeader.innerHTML = `<input type="text" id="editPatientNameInput" value="${currentName}" style="background: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; padding: 5px; border-radius: 4px; font-size: 18px; width: 80%;">`;
    const editBtn = document.querySelector("button[onclick*='updatePatientSubmit']");
    if (editBtn) {
        editBtn.innerText = "حفظ التعديل ✔️";
        editBtn.style.backgroundColor = "var(--color-green)";
    }
}

async function savePatientNameSubmit(patientId) {
    const inputElement = document.getElementById('editPatientNameInput');
    if (!inputElement) return;
    const newName = inputElement.value.trim();
    if (newName === "") return;

    try {
        await axios.patch(`${API_BASE_URL}/patients/${patientId}/`, { name: newName });
        alert("تم التحديث بنجاح!");
        selectedPatient.name = newName;
        document.getElementById('detName').innerText = `المريض: ${newName}`;
        const editBtn = document.querySelector("button[onclick*='updatePatientSubmit']");
        if (editBtn) {
            editBtn.innerText = "تعديل الاسم";
            editBtn.style.backgroundColor = "#38bdf8";
        }
        fetchPatients(); 
    } catch (e) {
        console.error("خطأ التعديل:", e);
    }
}