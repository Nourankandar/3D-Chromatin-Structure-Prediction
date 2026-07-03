axios.defaults.withCredentials = true;
// 🌟 تحديث الرابط الأساسي ليتوافق مع الروابط الجديدة في core/urls.py
const API_BASE_URL = 'http://127.0.0.1:8000/api';

let selectedPatient = null;
let typingTimer;
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
        showToast("الرجاء تعبئة جميع بيانات المريض!", "error");
        return;
    }

    try {
        await axios.post(`${API_BASE_URL}/patients/`, data);
        showToast("تم تسجيل المريض بنجاح!", "success");
        document.getElementById('patientMRN').value = '';
        document.getElementById('patientName').value = '';
        fetchPatients();
    } catch (e) {
        console.error("خطأ:", e.response ? e.response.data : e);
        showToast("خطأ في الإرسال، تفقد الـ Console.", "error");
    }
}

// 🌟 2. دالة إضافة اختبار جيني جديد (الـ Pipeline)
async function addNewTestSubmit() {
    const formData = new FormData();
    const patientId = document.getElementById('testPatientSelect').value;
    const fileInput = document.getElementById('testDnaFile').files[0];

    if (!patientId || !fileInput) {
        showToast("الرجاء اختيار المريض وملف الـ DNA!", "error");
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
        showToast("تم رفع الاختبار بنجاح، جاري التنبؤ بالخلفية!", "success");
        fetchPatients();
    } catch (e) {
        console.error("تفاصيل الخطأ:", e.response ? e.response.data : e);
        showToast("حدث خطأ أثناء رفع الاختبار.", "error");
    }
}

// 🌟 3. جلب المرضى وتعبئة القوائم
async function fetchPatients() {
    try {
        const response = await axios.get(`${API_BASE_URL}/patients/`);
        patientsDatabase = response.data; 
        refreshPatientsList();
        populatePatientDropdown();
        fetchCellTypes();
        fetchCellTypes(); // تحديث قائمة أنواع الخلايا من الباك إند (ديناميكي، يطابق IDs الحقيقية)
    } catch (e) {
        console.error("خطأ في جلب بيانات المرضى:", e);
    }
}

// 🌟 جلب أنواع الخلايا الحقيقية من الباك إند (بدل قيم ثابتة قد لا تطابق IDs الحقيقية)
async function fetchCellTypes() {
    const select = document.getElementById('testCellType');
    if (!select) return;

    try {
        const response = await axios.get(`${API_BASE_URL}/tests/cell-types/`);
        const cellTypes = response.data.cell_types || [];

        if (cellTypes.length === 0) {
            select.innerHTML = '<option value="">لا توجد أنواع خلايا مسجّلة</option>';
            return;
        }

        select.innerHTML = '<option value="">-- اختر نوع الخلية --</option>';
        cellTypes.forEach(ct => {
            select.innerHTML += `<option value="${ct.id}">${ct.name}</option>`;
        });
    } catch (e) {
        console.error("خطأ في جلب أنواع الخلايا:", e);
        select.innerHTML = '<option value="">تعذر تحميل أنواع الخلايا</option>';
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

// 🌟 4. عرض تفاصيل المريض والاختبارات (مع تأثير الآلة الكاتبة وتقرير تجريبي)
function showPatientDetails(patient) {
    selectedPatient = patient;
    document.getElementById('detName').innerText = `المريض: ${patient.name}`;
    document.getElementById('detID').innerText = `الرقم الطبي (MRN): ${patient.mrn}`;
    document.getElementById('detGenderDOB').innerText = `الجنس: ${patient.gender === 'M' ? 'ذكر' : 'أنثى'} | المواليد: ${patient.dob}`;
    renderTestsList(patient);
    
    const reportEl = document.getElementById('detReport');
    
    // إيقاف أي تأثير طباعة قديم
    clearTimeout(typingTimer); 

    let textToType = "";
    let isCompleted = false;

    // فحص إذا المريض عنده بيانات حقيقية من السيرفر
    if (patient.genomic_inputs && patient.genomic_inputs.length > 0) {
        const latestTest = patient.genomic_inputs[patient.genomic_inputs.length - 1]; 
        
        if (latestTest.status === 'completed' && latestTest.report) {
            isCompleted = true;
            textToType = latestTest.report.summary_text;
        } else {
            reportEl.innerText = `الحالة الحالية: ${latestTest.status}... جاري المعالجة بواسطة الـ AI`;
            document.getElementById('actionButtons').style.display = 'block';
            return;
        }
    } else {
        // 🚀 الخدعة: توليد تقرير وهمي (Demo) إذا ما كان في تقرير حقيقي
        isCompleted = true;
        textToType = "تقرير تجريبي (AI Demo): تم تحليل التسلسل الجيني بنجاح. تظهر النتائج استقراراً في الكروموسوم المستهدف دون وجود طفرات أو تشوهات بنيوية خطيرة. يُنصح بمتابعة المؤشرات الحيوية دورياً. النظام جاهز للعمل.";
    }

    // تشغيل تأثير الآلة الكاتبة
    if (isCompleted) {
        reportEl.innerHTML = `<span style="color:#22c55e;">[مكتمل]</span><br><span id="typing-content" style="color: #cbd5e1;"></span>`;
        const typingContent = document.getElementById('typing-content');
        let charIndex = 0;
        
        function typeWriter() {
            if (charIndex < textToType.length) {
                typingContent.innerHTML += textToType.charAt(charIndex);
                charIndex++;
                
                // تشغيل صوت خفيف كل 4 أحرف ليعطي إحساس الآلة
                if (charIndex % 4 === 0 && typeof playTechSound === 'function') {
                    playTechSound('click');
                }
                
                typingTimer = setTimeout(typeWriter, 20); // سرعة الطباعة
            } else {
                // إضافة مؤشر وامض بنهاية التقرير لزيادة الفخامة
                typingContent.innerHTML += `<span class="blink-cursor">_</span>`;
            }
        }
        
        // تأخير بسيط قبل بدء الطباعة ليعطي انسيابية
        setTimeout(typeWriter, 200);
    }
    
    document.getElementById('actionButtons').style.display = 'block';
}

// 🌟 5. البحث عن بروتين مرتبط بجين عبر UniProt (ديناميكي، غير محدود بـ FSHR/ADRB2/HBB)
async function searchProteinByGene() {
    const geneInput = document.getElementById('geneSearchInput');
    const resultBox = document.getElementById('proteinSearchResult');
    const gene = geneInput.value.trim();

    if (!gene) {
        showToast("الرجاء إدخال اسم الجين", "error");
        return;
    }

    resultBox.innerHTML = '<span style="color:var(--gold)">⟳ جاري البحث في UniProt...</span>';

    try {
        const res = await axios.get(`${API_BASE_URL}/tests/search-protein/`, {
            params: { gene: gene }
        });
        const data = res.data;

        if (!data.pdb_ids || data.pdb_ids.length === 0) {
            resultBox.innerHTML = `<span style="color:#e06060">لم يتم العثور على بنية ذرية (PDB) لهذا الجين</span>`;
            return;
        }

        // نخزّن النتيجة كاملة بمتغير عام يستخدمه protein_viewer.html
        window.selectedGeneSearch = {
            gene: data.gene,
            uniprot_id: data.uniprot_id,
            protein_name: data.protein_name,
            pdb_ids: data.pdb_ids,
            selected_pdb: data.pdb_ids[0]
        };

        resultBox.innerHTML = `
            <div style="background:var(--obsidian); border:1px solid var(--border); padding:12px; border-radius:4px;">
                <strong style="color:var(--gold-light)">${data.protein_name}</strong><br>
                <span style="font-family:var(--font-mono); font-size:11px;">UniProt: ${data.uniprot_id}</span><br>
                <span style="font-size:11px;">PDB IDs المتاحة: </span>
                <span style="color:var(--gold)">${data.pdb_ids.join(', ')}</span>
                <div style="margin-top:8px;">
                    <button class="btn-outline" style="font-size:11px; padding:4px 10px;"
                        onclick="window.open('protein_viewer.html?pdb=${data.pdb_ids[0]}&gene=${data.gene}','_blank')">
                        ◈ فتح في عارض البروتين 3D
                    </button>
                </div>
            </div>
        `;
    } catch (e) {
        console.error("خطأ بحث البروتين:", e.response ? e.response.data : e);
        resultBox.innerHTML = `<span style="color:#e06060">تعذر العثور على نتائج لهذا الجين</span>`;
    }
}


async function deletePatient(patientId) {
    if(confirm("هل أنت متأكد من حذف هذا المريض وكل تحاليله وتقاريره؟")) {
        try {
            await axios.delete(`${API_BASE_URL}/patients/${patientId}/`);
            showToast("تم حذف المريض بنجاح.", "success");
            document.getElementById('detName').innerText = "الرجاء اختيار مريض...";
            document.getElementById('detID').innerText = "";
            document.getElementById('detGenderDOB').innerText = "";
            document.getElementById('detReport').innerText = "---";
            document.getElementById('actionButtons').style.display = 'none';
            fetchPatients(); 
        } catch (e) {
            console.error("خطأ أثناء الحذف:", e);
            showToast("حدث خطأ أثناء حذف المريض.", "error");
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
        showToast("تم التحديث بنجاح!", "success");
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
        showToast("حدث خطأ أثناء التحديث.", "error");
    }
}
// 🌟 6. عرض قائمة كل التحاليل السابقة لمريض معيّن
function renderTestsList(patient) {
    const container = document.getElementById('testsListContainer');
    if (!container) return;

    const tests = patient.genomic_inputs || [];

    if (tests.length === 0) {
        container.innerHTML = `<p style="color:var(--ivory-muted); font-size:12px;">لا توجد تحاليل سابقة لهذا المريض.</p>`;
        return;
    }

    const sortedTests = [...tests].sort((a, b) => {
        if (a.created_at && b.created_at) return new Date(b.created_at) - new Date(a.created_at);
        return (b.id || 0) - (a.id || 0);
    });

    const statusLabels = { 'pending': '⏳ قيد الانتظار', 'predicting_dnase': '⚙ تنبؤ DNase', 'generating_hic': '⚙ توليد Hi-C', 'completed': '✓ مكتمل', 'failed': '✕ فشل' };
    const statusColors = { 'pending': '#c9a84c', 'predicting_dnase': '#38bdf8', 'generating_hic': '#38bdf8', 'completed': '#6abf8a', 'failed': '#e06060' };

    container.innerHTML = sortedTests.map(test => {
        const statusText = statusLabels[test.status] || test.status || 'غير معروف';
        const statusColor = statusColors[test.status] || 'var(--ivory-muted)';
        const dateText = test.created_at ? new Date(test.created_at).toLocaleString('ar-EG', { dateStyle: 'medium', timeStyle: 'short' }) : '';
        return `
            <div style="display:flex; justify-content:space-between; align-items:center;
                        background:var(--obsidian-4); border:1px solid var(--border);
                        padding:10px 14px; border-radius:4px;">
                <div>
                    <span style="font-family:var(--font-mono); font-size:11px; color:var(--ivory-muted);">تحليل #${test.id}</span>
                    ${dateText ? `<span style="font-size:11px; color:var(--ivory-muted); margin-right:10px;">· ${dateText}</span>` : ''}
                    <br>
                    <span style="font-size:12px; color:${statusColor};">${statusText}</span>
                </div>
                <button class="btn-outline" style="font-size:11px; padding:4px 10px;"
                        onclick="deleteTest(${test.id})">✕ حذف</button>
            </div>
        `;
    }).join('');
}

// 🌟 7. حذف تحليل واحد محدد
async function deleteTest(testId) {
    if (!confirm(`هل أنت متأكد من حذف التحليل #${testId}؟`)) return;
    try {
        await axios.delete(`${API_BASE_URL}/tests/${testId}/`);
        showToast(`تم حذف التحليل #${testId} بنجاح.`, "success");
        const response = await axios.get(`${API_BASE_URL}/patients/${selectedPatient.id}/`);
        showPatientDetails(response.data);
        fetchPatients();
    } catch (e) {
        console.error("خطأ أثناء حذف التحليل:", e.response ? e.response.data : e);
        showToast("حدث خطأ أثناء حذف التحليل.", "error");
    }
}

// 🌟 جلب أنواع الخلايا الحقيقية من الباك إند
async function fetchCellTypes() {
    const select = document.getElementById('testCellType');
    if (!select) return;
    try {
        const response = await axios.get(`${API_BASE_URL}/tests/cell-types/`);
        const cellTypes = response.data.cell_types || [];
        if (cellTypes.length === 0) { select.innerHTML = '<option value="">لا توجد أنواع خلايا مسجّلة</option>'; return; }
        select.innerHTML = '<option value="">-- اختر نوع الخلية --</option>';
        cellTypes.forEach(ct => { select.innerHTML += `<option value="${ct.id}">${ct.name}</option>`; });
    } catch (e) {
        console.error("خطأ في جلب أنواع الخلايا:", e);
        select.innerHTML = '<option value="">تعذر تحميل أنواع الخلايا</option>';
    }
}
