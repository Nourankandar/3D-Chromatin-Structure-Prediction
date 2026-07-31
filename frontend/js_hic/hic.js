/* ══════════════════════════════════════════════════════════════════════
     API  إعدادات الـ  
   ══════════════════════════════════════════════════════════════════════ */
const CHROMO_DEFAULT_VIZ_PATH = id => `/genomics/output/${id}/full/`;

function chromoVizURL(outputId){
  const base = (window.CHROMO_API_BASE || '/api').replace(/\/$/, '');
  const path = (window.CHROMO_VIZ_PATH || CHROMO_DEFAULT_VIZ_PATH)(outputId);
  return base + path;
}

/* ══════════════════════════════════════════════════════════════════════
   محاذاة Procrustes  (Kabsch عبر رباعيات Horn)
   ─────────────────────────────────────────────────────────────────────
   ليش هاد ضروري:
   الـ MDS بيحسب الإحداثيات من مصفوفة مسافات، والحل مش وحيد — أي دوران
   أو انعكاس بيعطي نفس المسافات بالضبط. المريض والسليم انبنوا كل واحد
   بعملية MDS مستقلة، فاتجاههم بالفضاء عشوائي وما إلو أي علاقة ببعض.
   عرضهم فوق بعض بدون محاذاة = خيطين ملفوفين عشوائياً، والمقارنة
   البصرية بتصير بلا أي معنى.

   الطريقة: منلاقي الدوران R اللي بيقلّل Σ|R·control − patient|² عبر
   أكبر متجه ذاتي لمصفوفة Horn الرباعية 4×4 (power iteration — كافية
   ومستقرة لمصفوفة 4×4، وبتتجنّب الحاجة لمكتبة SVD).

   بالانعكاس: منجرّب النسختين (أصلية + معكوسة) ومناخد اللي RMSD أقل،
   لأنه الانعكاس التقني تبع MDS مش فرق بيولوجي.
   ══════════════════════════════════════════════════════════════════════ */

/* أكبر متجه ذاتي لمصفوفة متناظرة 4×4 عبر power iteration مع إزاحة قطرية
   (الإزاحة بتضمن إن كل القيم الذاتية موجبة فبتتقارب للأكبر) */
function largestEigenVec4(N){
  let shift = 0;
  for(let i=0;i<4;i++){
    let rowSum = 0;
    for(let j=0;j<4;j++) rowSum += Math.abs(N[i][j]);
    if(rowSum > shift) shift = rowSum;
  }
  const M = N.map((row,i)=> row.map((v,j)=> i===j ? v + shift : v));

  let v = [1,0,0,0];
  for(let iter=0; iter<200; iter++){
    const w = [0,0,0,0];
    for(let i=0;i<4;i++)
      for(let j=0;j<4;j++) w[i] += M[i][j]*v[j];

    let norm = Math.hypot(w[0],w[1],w[2],w[3]);
    if(!isFinite(norm) || norm < 1e-12) break;
    for(let i=0;i<4;i++) w[i] /= norm;

    let diff = 0;
    for(let i=0;i<4;i++) diff += Math.abs(w[i]-v[i]);
    v = w;
    if(diff < 1e-10) break;
  }
  return v; // [w, x, y, z]
}

/* يرجّع THREE.Quaternion بيدوّر مجموعة A لتطابق مجموعة B.
   A و B لازم يكونوا موسّطين (centered) ومتقابلين نقطة بنقطة. */
function kabschQuaternion(A, B){
  // مصفوفة التغاير 3×3
  let Sxx=0,Sxy=0,Sxz=0, Syx=0,Syy=0,Syz=0, Szx=0,Szy=0,Szz=0;
  for(let k=0;k<A.length;k++){
    const a=A[k], b=B[k];
    Sxx+=a.x*b.x; Sxy+=a.x*b.y; Sxz+=a.x*b.z;
    Syx+=a.y*b.x; Syy+=a.y*b.y; Syz+=a.y*b.z;
    Szx+=a.z*b.x; Szy+=a.z*b.y; Szz+=a.z*b.z;
  }
  // مصفوفة Horn المتناظرة 4×4
  const N=[
    [ Sxx+Syy+Szz,  Syz-Szy,      Szx-Sxz,      Sxy-Syx     ],
    [ Syz-Szy,      Sxx-Syy-Szz,  Sxy+Syx,      Szx+Sxz     ],
    [ Szx-Sxz,      Sxy+Syx,     -Sxx+Syy-Szz,  Syz+Szy     ],
    [ Sxy-Syx,      Szx+Sxz,      Syz+Szy,     -Sxx-Syy+Szz ]
  ];
  const q = largestEigenVec4(N); // [w,x,y,z]
  return new THREE.Quaternion(q[1], q[2], q[3], q[0]).normalize();
}

function rmsdOf(A, B){
  let s=0;
  for(let k=0;k<A.length;k++) s += A[k].distanceToSquared(B[k]);
  return Math.sqrt(s / Math.max(A.length,1));
}

/* يقابل نقاط المريض بنقاط السليم.
   الأفضل: المطابقة عبر `region` (لأنه عدد النقاط ممكن يختلف بين الجهتين
   بسبب حذف الـ bins الفاضية بشكل مستقل بكل جهة).
   الاحتياطي: المطابقة بالفهرس مع القص لأقصر الاثنين. */
function pairPoints(pPts, cPts){
  const haveRegions = pPts[0]?.region && cPts[0]?.region;
  if(haveRegions){
    const cByRegion = new Map();
    cPts.forEach(p => { if(p.region && !cByRegion.has(p.region)) cByRegion.set(p.region, p); });
    const P=[], C=[];
    for(const p of pPts){
      const c = cByRegion.get(p.region);
      if(c){ P.push(p); C.push(c); }
    }
    if(P.length >= 3) return {P, C, mode:'region'};
  }
  const n = Math.min(pPts.length, cPts.length);
  return { P: pPts.slice(0,n), C: cPts.slice(0,n), mode:'index' };
}

/* آخر نتيجة محاذاة — بتنعرض بلوحة التفاصيل */
let alignInfo = null;

/* ══════════════════════════════════════════════════════════════════════
   تزامن الكاميرا بين شاشتي المقارنة
   ─────────────────────────────────────────────────────────────────────
   المشكلة: كل pane هو iframe مستقل بمشهد Three.js خاص فيه. بعد ما
   حاذينا البنيتين رياضياً، ما بتبيّن المحاذاة إذا كل شاشة بزاوية نظر
   مختلفة — لازم الاثنين يتحرّكوا سوا.

   التصميم (قائد/تابع) — بيمنع مشكلتين:
     1. الحلقة اللانهائية: التابع بيطبّق الكاميرا بدون ما يعيد بثّها
        (عبر علم applyingRemoteCam).
     2. الدوران المضاعف: لو الاثنين شغّالين autoRot، كل واحد بيزيد
        theta لحالو + بياخد theta من التاني = سرعة مضاعفة وارتجاف.
        الحل: التابع ما بيدوّر نفسه إطلاقاً، بس بيتبع.

   القيادة بتنتقل لأي شاشة المستخدم بيلمسها (mouseenter/mousedown).
   ══════════════════════════════════════════════════════════════════════ */
let camSync = false;            // مفعّل؟ (بتحدده الصفحة الحاضنة)
let camLeader = false;          // هل هالعارض هو القائد حالياً؟
let camDirty = false;           // تغيّرت الكاميرا من آخر بثّ؟
let applyingRemoteCam = false;  // عم نطبّق كاميرا جاية من برّا؟

function camPost(msg){
  try{ if(window.parent && window.parent!==window) window.parent.postMessage(msg,'*'); }catch(e){}
}

/* بتنادى لما المستخدم يلمس هالشاشة — بتاخد القيادة */
function claimCamLeadership(){
  if(!camSync || camLeader) return;
  camLeader = true;
  camPost({type:'chromo-cam-claim'});
}

/* بثّ حالة الكاميرا — منادى من loop() بمعدّل إطار واحد كحد أقصى
   (بدل ما ينبعت مع كل حدث mousemove) */
function broadcastCam(){
  if(!camSync || !camLeader || !camDirty) return;
  camDirty = false;
  camPost({
    type:'chromo-cam',
    cam:{ theta:sph.theta, phi:sph.phi, r:sph.r,
          px:pan.x, py:pan.y, autoRot }
  });
}

function applyRemoteCam(c){
  if(!c) return;
  camTween = null;              // كاميرا القائد أولى من أي طيران محلي
  applyingRemoteCam = true;
  sph.theta=c.theta; sph.phi=c.phi; sph.r=c.r;
  pan.x=c.px; pan.y=c.py;
  autoRot = !!c.autoRot;                 // للعرض فقط — التابع ما بيدوّر لحالو
  const b=document.getElementById('btnR');
  if(b){ b.textContent = autoRot?'⏸':'▶'; b.classList.toggle('on', autoRot); }
  updateCam();
  applyingRemoteCam = false;
}

/* ══════════════════════════════════════════════════════════════════════
   بروتينات الارتباط (binding_proteins)
   ─────────────────────────────────────────────────────────────────────
   بيجوا بالمستوى الأعلى من الـ payload (شقيق patient/control)، بالشكل:
     "CTCF": {
        protein_name, position_index, delta_score, is_missing,
        patient: { present, binding_score, position_index } | null,
        control: { present, binding_score, position_index } | null
     }

   طبقة الترجمة — من موقع البروتين لفهرس نقطة 3D:
     1. لو الباك بعت `coord_index` → منستعملو مباشرة (الأدق).
     2. وإلا منحسب الموقع الجينومي المطلق من position_index (حقل باك
        حقيقي)، ومنطابقو مباشرة مع حقل `region` الحقيقي لكل نقطة —
        بلا أي افتراض عن استمرارية أو حذف الـ bins. clean_matrix()
        بالباك فعلاً بيحذف bins فاضية، فـ "bin == فهرس المصفوفة" تخمين
        مش مضمون كان ممكن يحط البروتين بنقطة غلط بصمت. region حقل
        حقيقي مبعوت لكل نقطة، فمطابقته بتلغي التخمين تماماً.
     3. لو ما لقينا نقطة بتغطي هالموقع → منرجّع null صراحة: البروتين
        بيضل ظاهر باللستة مع سبب واضح، بس بدون marker على الخيط. ما منهار،
        وما منخترع رقم.
   ══════════════════════════════════════════════════════════════════════ */
let bindingProteins = null;     // القاموس الخام من الباك
let activeSide = 'patient';     // أي جهة معروضة بهالعارض
let proteinGroup = null;        // THREE.Group فيه كل الـ markers
let showProteins = true;
/* التكبير المعروض للبنى الذرية. القيمة الحقيقية بالمقياس رح تكون كسراً
   ضئيلاً (~0.5% من امتداد المشهد) فالبنية بتصير ٣ بكسل وما بتبيّن.
   لهيك منكبّر صراحةً ومنعرض الوسم بالواجهة — أمانة علمية مش تجميل. */
let proteinMagnify = 60;
function setProteinMagnify(v){ proteinMagnify=Math.max(1,+v||1); buildProteinMarkers(); }
let sceneCenter = null;         // مركز المشهد المعروض (بينحدد ببناء المشهد)
let alignTransform = null;      // {quat, mirror, cCenter, pCenter} من المحاذاة

/* يرجّع {index, reason} — index=null يعني ما قدرنا نحدد نقطة على الخيط */
function resolveProteinCoordIndex(sideEntry, sideData, coords){
  if(!sideEntry) return {index:null, reason:'غير موجود بهذه الجهة'};
  if(!coords || !coords.length) return {index:null, reason:'لا توجد إحداثيات'};

  // (1) الباك بعت الفهرس جاهز
  if(Number.isInteger(sideEntry.coord_index)){
    const i = sideEntry.coord_index;
    if(i>=0 && i<coords.length) return {index:i, reason:'coord_index'};
    return {index:null, reason:`coord_index=${i} خارج المدى (${coords.length})`};
  }

  // (2) الموقع الجينومي المطلق من position_index (حقل باك حقيقي).
  // القيم السالبة بتيجي من الخيط العكسي بـ JASPAR — منعتمد المسافة.
  const posRaw = sideEntry.position_index;
  if(posRaw==null || !isFinite(posRaw)) return {index:null, reason:'لا يوجد position_index'};

  const start = Number(sideData?.start);
  if(!isFinite(start)) return {index:null, reason:'start غير معروف'};

  const abs = start + Math.abs(Number(posRaw));

  // (3) مطابقة مباشرة مع region الحقيقي لكل نقطة — بلا أي تخمين
  for(let i=0;i<coords.length;i++){
    const m = /^(\d+)kb-(\d+)kb$/.exec(coords[i].region || '');
    if(!m) continue;
    const startBp = Number(m[1])*1000, endBp = Number(m[2])*1000;
    if(abs>=startBp && abs<endBp) return {index:i, reason:`مطابقة region (${coords[i].region})`};
  }
  return {index:null, reason:`لا توجد نقطة إحداثيات تغطي الموقع ${abs.toLocaleString()}bp`};
}

/* تصنيف حالة البروتين — بيحدد اللون والوصف */
function classifyProtein(entry){
  const hasP = !!(entry.patient && entry.patient.present !== false);
  const hasC = !!(entry.control && entry.control.present !== false);
  const d = Number(entry.delta_score);

  if(entry.is_missing || (!hasP && hasC))
    return {key:'missing',  label:'مفقود عند المريض', color:'#e5766f'};
  if(hasP && !hasC)
    return {key:'gained',   label:'مكتسب عند المريض', color:'#7aa2f7'};
  if(hasP && hasC && isFinite(d) && d <= -0.15)
    return {key:'weakened', label:'ارتباط أضعف',       color:'#e0b24d'};
  if(hasP && hasC && isFinite(d) && d >= 0.15)
    return {key:'stronger', label:'ارتباط أقوى',       color:'#6fd3c0'};
  if(hasP && hasC)
    return {key:'stable',   label:'مستقر',             color:'#8eb69b'};
  return {key:'unknown',    label:'غير محدد',          color:'#8a9a94'};
}

/* ══════════════════════════════════════════════════════════════════════
   المعايرة والاتجاه — الطبقة العلمية
   ══════════════════════════════════════════════════════════════════════ */

/* أكبر متجه ذاتي لمصفوفة متناظرة 3×3 (power iteration).
   نفس فكرة largestEigenVec4 بس بثلاثة أبعاد. */
function largestEigenVec3(M){
  let shift=0;
  for(let i=0;i<3;i++){
    let s=0; for(let j=0;j<3;j++) s+=Math.abs(M[i][j]);
    if(s>shift) shift=s;
  }
  const A = M.map((row,i)=> row.map((v,j)=> i===j ? v+shift : v));
  let v=[1,0,0];
  for(let it=0; it<200; it++){
    const w=[0,0,0];
    for(let i=0;i<3;i++) for(let j=0;j<3;j++) w[i]+=A[i][j]*v[j];
    const n=Math.hypot(w[0],w[1],w[2]);
    if(!isFinite(n)||n<1e-12) break;
    for(let i=0;i<3;i++) w[i]/=n;
    let diff=0; for(let i=0;i<3;i++) diff+=Math.abs(w[i]-v[i]);
    v=w;
    if(diff<1e-11) break;
  }
  return new THREE.Vector3(v[0],v[1],v[2]).normalize();
}

/* المحور الرئيسي لسحابة نقاط عبر PCA — أول مركّبة رئيسية */
function principalAxis(pts){
  if(!pts || pts.length<3) return null;
  let cx=0,cy=0,cz=0;
  pts.forEach(p=>{cx+=p.x;cy+=p.y;cz+=p.z;});
  cx/=pts.length; cy/=pts.length; cz/=pts.length;

  let xx=0,xy=0,xz=0,yy=0,yz=0,zz=0;
  pts.forEach(p=>{
    const dx=p.x-cx, dy=p.y-cy, dz=p.z-cz;
    xx+=dx*dx; xy+=dx*dy; xz+=dx*dz; yy+=dy*dy; yz+=dy*dz; zz+=dz*dz;
  });
  return largestEigenVec3([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]]);
}

/* ══ محور اللولب من البلورة المشتركة ══
   معظم بنى عوامل النسخ بالـ PDB هي بروتين + DNA مع بعض. ذرات الفوسفور
   (P) بتقع على العمود الفقري للولب، فالمحور الرئيسي إلها = محور اللولب.
   هاد استنتاج من قياس بلوري حقيقي، مش تخمين.

   بلا DNA بالملف: منرتد للمحور الرئيسي للبروتين نفسه — تقريب أضعف
   بكتير، ومنعلّمه بالواجهة حتى ما يتلبّس على القارئ. */
function structureAxis(rec){
  if(rec.__axis !== undefined) return rec.__axis;   // محسوب مسبقاً

  const dnaP = rec.atoms.filter(a => a.isDNA && a.name === 'P');
  let axis = null, source = 'none';

  if(dnaP.length >= 4){
    axis = principalAxis(dnaP);
    source = 'dna';
  } else {
    const ca = rec.ca?.length >= 3 ? rec.ca : rec.atoms;
    axis = principalAxis(ca);
    source = ca === rec.ca ? 'protein' : 'atoms';
  }
  rec.__axis = axis ? {axis, source, nDna: dnaP.length} : null;
  return rec.__axis;
}

/* مماس الخيط عند نقطة — فرق مركزي على النقطتين المجاورتين */
function tangentAt(coords, idx){
  if(!coords || coords.length < 2) return null;
  const a = coords[Math.max(0, idx-1)];
  const b = coords[Math.min(coords.length-1, idx+1)];
  const v = new THREE.Vector3(b.x-a.x, b.y-a.y, b.z-a.z);
  return v.lengthSq() > 1e-12 ? v.normalize() : null;
}

/* ══ المعايرة: وحدات MDS → نانومتر ══
   إحداثيات MDS مشتقة من contacts^-alpha — أرقام مجرّدة بلا وحدة. حتى
   نعرف الحجم الحقيقي للبروتين نسبةً للمشهد لازم معامل تحويل.

   الطريقة: متوسط المسافة بين بِنين متتاليين بوحدات MDS يقابل المسافة
   الفيزيائية المتوقعة بينهم بالنانومتر.

   ⚠️ NM_PER_BIN_5KB تقدير من أدبيات تصوير الكروماتين، ومداه واسع
   (عشرات إلى ~150 nm حسب النوع الخلوي وحالة التراص). لهيك هو ثابت
   قابل للتعديل، والنتيجة تُعرض كتقدير لا كقياس. */
let NM_PER_BIN_5KB = 70;
let nmPerUnit = null;                 // نتيجة المعايرة الحالية

function calibrateScale(pts, resolution){
  if(!pts || pts.length < 2) return null;
  let sum=0, n=0;
  for(let i=1;i<pts.length;i++){
    const a=pts[i-1], b=pts[i];
    sum += Math.hypot(b.x-a.x, b.y-a.y, b.z-a.z); n++;
  }
  const meanStep = sum/Math.max(n,1);
  if(!(meanStep > 1e-9)) return null;

  const nmPerBin = NM_PER_BIN_5KB * ((resolution || 5000) / 5000);
  return nmPerBin / meanStep;          // نانومتر لكل وحدة MDS
}

/* الحجم الحقيقي للبروتين بوحدات المشهد.
   extentA بالأنغستروم (1 Å = 0.1 nm). */
function trueSceneRadius(rec){
  if(!nmPerUnit || !rec?.extentA) return null;
  const nm = rec.extentA * 0.1 / 2;    // نصف القطر بالنانومتر
  return nm / nmPerUnit;               // بوحدات MDS
}

// ══ globals ══
let scene,camera,renderer;
let meshes={tube:null,glow:null,dots:null,bounds:null,rmsdTube:null};
// ── حالة العرض المقارن (المريض + السليم) ──
let controlData=null;          // بيانات السليم (لو متوفرة)
let controlMesh=null;          // خيط السليم كطبقة منفصلة
let showControl=true;          // إظهار/إخفاء طبقة السليم
let sph={theta:.4,phi:1.2,r:80},pan={x:0,y:0};
let drag=false,rDrag=false,prev={x:0,y:0};
let autoRot=true,rotSpd=.0002;
let clrMode='emerald',tubeR=.6;
let effects={glow:false,bounds:false,rmsd:false};
let rawPts=[],smoothPts=[],viewMode='smooth';
let globalData=null;
let raycaster,mouse;
let isoScene,isoCamera,isoRenderer,isoRunning=false;

function sceneColor(){
  const c = getComputedStyle(document.documentElement).getPropertyValue('--scene').trim();
  return new THREE.Color(c || '#08201c');
}

// ══ Init ══
function initThree(){
  const c=document.getElementById('cv');
  scene=new THREE.Scene();
  const bg=sceneColor();
  scene.background=bg;                       // خلفية من الثيم (نفس البروتين تماماً)
  scene.fog=new THREE.FogExp2(bg.getHex(),.0016);
  camera=new THREE.PerspectiveCamera(55,c.clientWidth/c.clientHeight,.1,3000);
  updateCam();
  renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.setSize(c.clientWidth,c.clientHeight);
  c.appendChild(renderer.domElement);
  addLights(scene);
  addStars(scene);
  raycaster=new THREE.Raycaster();
  mouse=new THREE.Vector2();
  setupEvents(c);
  loop();
  document.getElementById('loading').style.display='none';
}

function addLights(s){
  s.add(new THREE.AmbientLight(0xffffff, .55));
  const dl=new THREE.DirectionalLight(0xffffff, 1.1);  dl.position.set(2,3,2);  s.add(dl);
  const dl2=new THREE.DirectionalLight(0x8eb69b, .7);   dl2.position.set(-2,-1,3); s.add(dl2);
  const dl3=new THREE.DirectionalLight(0xffffff, .35);  dl3.position.set(0,0,-3);  s.add(dl3);
}

function addStars(s){
  // بدون نجوم/جسيمات محيطة — خلفية نظيفة تماماً زي عارض البروتين
}

// ══ تطبيق البيانات على المشهد (مصدر موحّد: ملف يدوي أو API) ══
// بيستقبل object جاهز (مش نص) وبيعمل نفس منطق التحديث والرسم.
function applyData(d){
  if(!d || typeof d!=='object') throw new Error('صيغة بيانات غير صالحة');
  globalData=d;
  rawPts=d.coords_raw||[];
  smoothPts=d.coords_smooth||[];
  if(rawPts.length<2) throw new Error('بيانات النقاط غير كافية لرسم المجسم');

  const $=id=>document.getElementById(id);
  const set=(id,v)=>{ const el=$(id); if(el) el.textContent=v; };

  // لو ما في خيط ناعم (باك مبسّط) → نعرض النقاط الخام تلقائياً بدل مشهد فاضي
  if(smoothPts.length<2){
    viewMode='raw';
    $('btnSm')?.classList.remove('on');
    $('btnRw')?.classList.add('on');
  }

  // تحديث panel (مع حماية لو العنصر مش موجود بالنسخة المبسّطة)
  set('p-chrom', d.chrom||'—');
  set('p-start', d.start?(d.start/1e6).toFixed(2)+'M':'—');
  set('p-end',   d.end  ?(d.end/1e6).toFixed(2)+'M'  :'—');
  set('p-res',   d.resolution?(d.resolution/1000)+'kb':'—');
  set('p-pts',   rawPts.length+' | '+smoothPts.length);
  set('p-tads',  (d.n_tads||'—')+' TAD');
  if(d.chrom && d.start!=null && d.end!=null)
    set('hdr-info', `${d.chrom} · ${(d.start/1e6).toFixed(2)}M → ${(d.end/1e6).toFixed(2)}M`);

  // ── جودة إعادة البناء ──
  // كان: pct = max(5, 100 - log10(stress)*8) — لأي stress < 1 بيطلع log سالب
  // فالنتيجة أكبر من 100% والشريط بيفيض برا البوكس (stress=0.1984 → 105.6%).
  // الصح: stress منخفض = جودة عالية، والقيمة محصورة بين 5 و100.
  if(d.stress!=null && $('stress-bar')){
    const pct = Math.min(100, Math.max(5, (1 - Math.min(d.stress,1)) * 100));
    $('stress-bar').style.width = pct+'%';
    set('stress-val','Stress: '+Number(d.stress).toFixed(4));
  }
  // dscc: معامل ارتباط المسافات — كل ما قرب من 1 كانت إعادة البناء أوفى
  if(d.dscc!=null) set('p-dscc', Number(d.dscc).toFixed(4));
  // collapse_ratio: نسبة انطواء البنية (1.0 ≈ طبيعي)
  if(d.collapse_ratio!=null) set('p-collapse', Number(d.collapse_ratio).toFixed(2));

  buildTADList(d);
  buildScene();
  // بعد رسم المريض، لو في بيانات سليم منضيفها كطبقة مقارنة
  if(controlData) buildControlOverlay();
  // الماركرات آخر شي — بتحتاج sceneCenter (من buildScene) و
  // alignTransform (من buildControlOverlay) للماركرات الشبحية
  buildProteinMarkers();
}

// ══ العرض المقارن: المريض + السليم فوق بعض ══
// side: 'both' (فوق بعض) | 'patient' (المريض فقط) | 'control' (السليم فقط)
// الوضع 'patient'/'control' يُستخدم في شاشتين منفصلتين (كل iframe جهة).
function applyDualData(payload, side='both'){
  if(!payload || typeof payload!=='object') throw new Error('صيغة بيانات غير صالحة');
  const patient = payload.patient ? normalizeBackendPayload(payload.patient) : normalizeBackendPayload(payload);
  const control = payload.control ? normalizeBackendPayload(payload.control) : null;

  // binding_proteins بالمستوى الأعلى — شقيق patient/control مش جوّاهم
  bindingProteins = payload.binding_proteins || null;
  activeSide = (side==='control') ? 'control' : 'patient';

  if(side==='control'){
    if(control){
      // شاشة السليم لحالها — نعرضه كأساس بدون overlay
      controlData=null;
      const btnC=document.getElementById('btnControl'); if(btnC) btnC.style.display='none';
      applyData(control);
    } else {
      // ما في بيانات "سليم" حقيقية بهالملف — ما منعرض بيانات المريض
      // بدل هيك وكأنها سليم (هيك كان عم يصير قبل: fallback صامت لـ "both"
      // كان يخلي هالشاشة تعرض بنية المريض نفسها موسومة "السليم" بالغلط).
      showError('لا توجد بيانات "سليم" بهذا الملف');
    }
    return;
  }
  if(side==='patient'){
    // شاشة المريض لحالها — بدون overlay
    controlData=null;
    const btnC=document.getElementById('btnControl'); if(btnC) btnC.style.display='none';
    applyData(patient);
    return;
  }

  // both: المريض أساس + السليم overlay (نفس السلوك القديم)
  controlData = control;
  const btnC=document.getElementById('btnControl');
  if(btnC) btnC.style.display = controlData ? 'inline-flex' : 'none';
  applyData(patient);
}

// يرسم خيط السليم كطبقة شفّافة (لون محايد) فوق مشهد المريض — للمقارنة البصرية
function buildControlOverlay(){
  removeControlOverlay();
  if(!controlData || !showControl) return;

  let cpts = (viewMode==='smooth' ? controlData.coords_smooth : controlData.coords_raw) || [];
  if(cpts.length<2) cpts = controlData.coords_raw || [];
  if(cpts.length<2) return;

  const ppts = viewMode==='smooth' ? smoothPts : rawPts;
  if(ppts.length<2) return;

  // ── 1) نقابل النقطتين ونوسّط كل مجموعة على مركزها هي ──
  const {P, C, mode} = pairPoints(ppts, cpts);
  const canAlign = P.length >= 3;

  const centroid = arr => {
    const c = new THREE.Vector3();
    arr.forEach(p => c.add(new THREE.Vector3(p.x, p.y, p.z)));
    return c.divideScalar(Math.max(arr.length,1));
  };

  // مركز المريض المعروض — buildScene() بيوسّط على مركز كل نقاط المريض
  const pCenter = centroid(ppts);
  const cCenter = centroid(canAlign ? C : cpts);

  let quat = new THREE.Quaternion();      // دوران المحاذاة
  let mirror = false;                     // هل احتجنا انعكاس

  if(canAlign){
    const Pc = P.map(p => new THREE.Vector3(p.x,p.y,p.z).sub(pCenter));
    const Cc = C.map(p => new THREE.Vector3(p.x,p.y,p.z).sub(cCenter));

    // (أ) دوران صرف
    const qDirect = kabschQuaternion(Cc, Pc);
    const rmsdDirect = rmsdOf(Cc.map(v => v.clone().applyQuaternion(qDirect)), Pc);

    // (ب) نفس الشي بعد انعكاس على محور z — انعكاس MDS تقني مش بيولوجي
    const Cm = Cc.map(v => new THREE.Vector3(v.x, v.y, -v.z));
    const qMirror = kabschQuaternion(Cm, Pc);
    const rmsdMirror = rmsdOf(Cm.map(v => v.clone().applyQuaternion(qMirror)), Pc);

    if(rmsdMirror < rmsdDirect){ quat = qMirror; mirror = true; }
    else                       { quat = qDirect; }

    // مقياس التشتّت تبع المريض — لتطبيع الـ RMSD لرقم قابل للقراءة
    let spread = 0;
    Pc.forEach(v => spread += v.lengthSq());
    spread = Math.sqrt(spread / Math.max(Pc.length,1)) || 1;

    const bestRmsd = Math.min(rmsdDirect, rmsdMirror);
    alignInfo = {
      rmsd: bestRmsd,
      rmsdNorm: bestRmsd / spread,   // 0 = تطابق تام، 1 = اختلاف بحجم البنية نفسها
      pairs: P.length,
      mode, mirror
    };
  } else {
    alignInfo = { rmsd:null, rmsdNorm:null, pairs:P.length, mode, mirror:false };
    console.warn('[hic] نقاط متقابلة غير كافية للمحاذاة — عرض بإزاحة فقط');
  }

  // ── 2) نطبّق: توسيط على مركز السليم ثم الدوران (والانعكاس لو لزم) ──
  const v3 = cpts.map(p => {
    const v = new THREE.Vector3(p.x, p.y, p.z).sub(cCenter);
    if(mirror) v.z = -v.z;
    return v.applyQuaternion(quat);
  });
  // منخزّنها حتى الماركرات الشبحية تستعمل نفس التحويل بالضبط
  alignTransform = { quat: quat.clone(), mirror, cCenter: cCenter.clone(), pCenter: pCenter.clone() };

  updateAlignPanel();

  const curve=new THREE.CatmullRomCurve3(v3,false,'catmullrom',.5);
  const segs=Math.min(v3.length*4,1800);
  const geo=buildRibbonGeometry(curve,segs,tubeR*.9);

  // السليم بلون محايد فاتح شفّاف — يتباين مع أخضر المريض بدون ما يطغى
  controlMesh=new THREE.Mesh(geo,new THREE.MeshPhongMaterial({
    color:0xcfd8dc, transparent:true, opacity:.45, shininess:80,
    specular:new THREE.Color(0x222222), depthWrite:false
  }));
  scene.add(controlMesh);
}

/* ══════════════════════════════════════════════════════════════════════
   طبقة البنى الذرية — تحميل كسول + مستويات تفصيل (LOD)
   ─────────────────────────────────────────────────────────────────────
   ليش LOD أصلاً: بروتين وسطي فيه ~2000 ذرة. سبع بروتينات = 14 ألف كرة،
   وخمسين بروتين = 100 ألف. لو حمّلنا الكل ورسمناه دفعة وحدة بيتجمّد
   المتصفح قبل ما نشوف إذا الاتجاه صح أصلاً.

   ثلاث مستويات حسب بُعد الكاميرا:
     0 · بعيد  → كرة ملوّنة (رخيصة، هي اللي عنا هلق)
     1 · وسط   → شريط يمرّ بذرات CA (مئات المثلثات)
     2 · قريب  → البنية الذرية كاملة عبر InstancedMesh (رسمة واحدة)

   التحميل كسول: ما منجيب ملف PDB إلا لما البروتين يدخل مدى المستوى 1،
   ومنخزّنه بـ cache محدود مع إزاحة الأقدم استعمالاً (LRU).
   ══════════════════════════════════════════════════════════════════════ */
const PDB_CACHE = new Map();          // key -> {status:'loading'|'ok'|'fail', atoms, ca, extentA}
const PDB_MAX_CACHED = 12;
let lodEnabled = true;
let lodAccum = 0;                     // مؤقّت لتقليل فحص المسافات

const ATOM_COLORS = { DNA:0xc9a84c, C:0xaaaaaa, N:0x4488ff, O:0xff4444, S:0xffdd44,
                      P:0xff8800, FE:0xff6600, ZN:0x8888ff, DEFAULT:0xcccccc };
const ATOM_RADII  = { DNA:1.1, C:1.0, N:0.95, O:0.9, S:1.2, P:1.15, FE:1.3, ZN:1.25, DEFAULT:0.9 };

/* تحليل PDB — نفس منطق protein_viewer.html، مع الاحتفاظ بنوع البقية
   (بروتين أم DNA) لأنه رح نحتاجه بخطوة الاتجاه لاحقاً */
const _DNA_RES = new Set(['DA','DT','DG','DC','A','T','G','C','U']);
function parsePDB(text){
  const atoms=[];
  for(const line of text.split('\n')){
    if(!(line.startsWith('ATOM') || line.startsWith('HETATM'))) continue;
    const x=parseFloat(line.slice(30,38)), y=parseFloat(line.slice(38,46)), z=parseFloat(line.slice(46,54));
    if(!isFinite(x)||!isFinite(y)||!isFinite(z)) continue;
    const res=line.slice(17,20).trim();
    atoms.push({
      x, y, z,
      name: line.slice(12,16).trim(),
      res,
      chain: line.slice(21,22).trim(),
      element: (line.slice(76,78).trim() || line.slice(12,14).trim()).toUpperCase(),
      isDNA: _DNA_RES.has(res)
    });
    if(atoms.length > 60000) break;   // حارس ضد البنى الضخمة جداً
  }
  return atoms;
}

/* ══════════════════════════════════════════════════════════════════════
   الحلّ بالاسم — نفس سلسلة الباك بالضبط
   ─────────────────────────────────────────────────────────────────────
   الباك بـ ProteinStructureFetcher بيعمل:  اسم الجين → UniProt →
   RCSB (تجريبي) → AlphaFold (تنبّؤي). منعيد نفس السلسلة هون حتى أي
   بروتين بيجي من الباك يلاقي بنية، حتى لو ما بعت pdb_url.

   ترتيب الأفضلية بالكامل:
     pdb_url (محفوظ عند الباك — أسرع وبلا CORS)
       → pdb_id (RCSB مباشرةً)
         → الاسم (السلسلة الكاملة هون)
           → كرة

   منسجّل كمان إذا البنية تجريبية ولا تنبّؤية — فرق جوهري بتطبيق طبي،
   وبينعرض بالوسم. */
const NAME_CACHE = new Map();          // gene → {kind,value,source} | null

/* أسماء JASPAR ممكن تكون ثنائيات متل "Arnt::Ahr" أو فيها رموز.
   منـاخد أول جزء ومننضّفه. */
function normalizeGene(name){
  return String(name||'').split(/::|:|\//)[0]
    .replace(/[^A-Za-z0-9-]/g,'').toUpperCase();
}

async function searchRCSBByAccession(acc){
  const body = {
    query: { type:'terminal', service:'text', parameters:{
      attribute:'rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession',
      operator:'exact_match', value:acc } },
    return_type:'entry',
    request_options:{ paginate:{ start:0, rows:1 } }
  };
  const r = await fetch('https://search.rcsb.org/rcsbsearch/v2/query', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body), signal: AbortSignal.timeout(15000)
  });
  if(!r.ok) return null;
  const j = await r.json();
  return j?.result_set?.[0]?.identifier || null;
}

async function resolveByGeneName(name){
  const gene = normalizeGene(name);
  if(!gene || gene.length < 2) return null;
  if(NAME_CACHE.has(gene)) return NAME_CACHE.get(gene);

  let out = null;
  try{
    // ── ١) اسم الجين → معرّف UniProt (بشري، مراجَع) ──
    const uq = 'https://rest.uniprot.org/uniprotkb/search'
      + `?query=gene_exact:${encodeURIComponent(gene)}+AND+organism_id:9606+AND+reviewed:true`
      + '&fields=accession&format=json&size=1';
    const ur = await fetch(uq, {signal: AbortSignal.timeout(12000)});
    const acc = ur.ok ? (await ur.json())?.results?.[0]?.primaryAccession : null;

    if(acc){
      // ── ٢) بنية تجريبية من RCSB ──
      let pdbId = null;
      try{ pdbId = await searchRCSBByAccession(acc); }catch(e){}
      if(pdbId){
        out = {kind:'id', value:pdbId, source:'experimental', accession:acc};
      } else {
        // ── ٣) احتياطي: بنية متنبَّأة من AlphaFold ──
        const ar = await fetch(`https://alphafold.ebi.ac.uk/api/prediction/${acc}`,
                               {signal: AbortSignal.timeout(12000)});
        if(ar.ok){
          const aj = await ar.json();
          const entry = Array.isArray(aj) ? aj[0] : aj;
          if(entry?.pdbUrl) out = {kind:'url', value:entry.pdbUrl,
                                   source:'predicted', accession:acc};
        }
      }
    }
  }catch(e){ /* الشبكة أو CORS — منرجع null ومنضل على الكرة */ }

  NAME_CACHE.set(gene, out);          // منخزّن حتى الفشل حتى ما نعيد المحاولة
  return out;
}

/* من وين نجيب البنية؟ */
function resolveStructureSource(key, entry){
  const cand = entry.pdb_url || entry.patient?.pdb_url || entry.control?.pdb_url;
  if(cand) return {kind:'url', value:cand, source: entry.structure_source || null};
  const id = entry.pdb_id || entry.pdb || entry.patient?.pdb_id || entry.control?.pdb_id;
  if(id) return {kind:'id', value:String(id).toUpperCase(), source: entry.structure_source || null};
  const gene = normalizeGene(entry.protein_name || key);
  if(gene.length >= 2) return {kind:'name', value:gene, source:null};
  return null;
}

/* الإزاحة من الكاش: ممنوع نشيل بنية مستعملة بالجولة الحالية.
   بدون هالشرط، لو عدد البروتينات بالمدى أكبر من حجم الكاش، بتنشال
   عناصر لسا معروضة فينعاد تحميلها بالجولة اللي بعدها — تحميل لا نهائي. */
let _lodPass = 0;
function _touchCache(key){
  const v = PDB_CACHE.get(key);
  if(!v) return;
  v.pass = _lodPass;
  PDB_CACHE.delete(key); PDB_CACHE.set(key, v);   // إعادة إدراج = الأحدث
}
function _evictCache(){
  if(PDB_CACHE.size <= PDB_MAX_CACHED) return;
  for(const [k, v] of [...PDB_CACHE]){
    if(PDB_CACHE.size <= PDB_MAX_CACHED) break;
    if(v.pass === _lodPass) continue;             // مستعمل الآن — نتخطاه
    PDB_CACHE.delete(k);
  }
}

/* سقف الطلبات المتزامنة — حتى ما نقصف RCSB بثلاثين طلب دفعة وحدة */
const PDB_MAX_INFLIGHT = 4;
let _inflight = 0;

async function loadStructure(key, src){
  if(PDB_CACHE.has(key)){ _touchCache(key); return PDB_CACHE.get(key); }
  if(_inflight >= PDB_MAX_INFLIGHT) return null;   // منأجّل لجولة جاية
  const rec = {status:'loading', pass:_lodPass};
  PDB_CACHE.set(key, rec); _touchCache(key);
  _inflight++;

  // الاسم لازم ينحلّ أول (UniProt → RCSB/AlphaFold) قبل ما نعرف الرابط
  let eff = src;
  if(src.kind === 'name'){
    const resolved = await resolveByGeneName(src.value);
    if(!resolved){
      rec.status = 'fail'; rec.reason = `تعذّر إيجاد بنية للجين ${src.value}`;
      _inflight--; return rec;
    }
    eff = resolved;
  }
  rec.structureSource = eff.source || null;   // experimental | predicted | null
  rec.accession = eff.accession || null;

  const urls = eff.kind==='url'
    ? [eff.value]
    : [`https://files.rcsb.org/download/${eff.value}.pdb`,
       `https://files.rcsb.org/view/${eff.value}.pdb`];

  for(const url of urls){
    try{
      const res = await fetch(url, {signal: AbortSignal.timeout(15000)});
      if(!res.ok) continue;
      const text = await res.text();
      if(!/^ATOM\s|\nATOM\s/.test(text)) continue;   // صفحة خطأ مش ملف
      const atoms = parsePDB(text);
      if(!atoms.length) continue;

      const ca = atoms.filter(a=>a.name==='CA');
      // أقصى امتداد بالأنغستروم — لازمنا لاحقاً بمعايرة المقياس الحقيقي
      let cx=0,cy=0,cz=0;
      atoms.forEach(a=>{cx+=a.x;cy+=a.y;cz+=a.z;});
      cx/=atoms.length; cy/=atoms.length; cz/=atoms.length;
      let maxD=0;
      atoms.forEach(a=>{ const d=Math.hypot(a.x-cx,a.y-cy,a.z-cz); if(d>maxD) maxD=d; });

      Object.assign(rec, {status:'ok', atoms, ca, centre:{cx,cy,cz}, extentA:maxD*2});
      _inflight--;
      return rec;
    }catch(e){ /* منجرّب الرابط التالي */ }
  }
  rec.status='fail';
  _inflight--;
  console.warn('[hic] تعذّر تحميل بنية', key);
  return rec;
}

/* مستوى 1 — شريط يمرّ بذرات CA لكل سلسلة */
function buildLOD1(rec, size, color){
  const g=new THREE.Group();
  if(!rec.ca?.length) return null;
  const chains={};
  rec.ca.forEach(a=>{ (chains[a.chain]||(chains[a.chain]=[])).push(a); });
  const {cx,cy,cz}=rec.centre;
  const s = size / (rec.extentA/2 || 1);
  for(const k in chains){
    const pts=chains[k].map(a=>new THREE.Vector3((a.x-cx)*s,(a.y-cy)*s,(a.z-cz)*s));
    if(pts.length<2) continue;
    const curve=new THREE.CatmullRomCurve3(pts);
    const geo=new THREE.TubeGeometry(curve, Math.min(200, pts.length*3), size*0.055, 6, false);
    g.add(new THREE.Mesh(geo, new THREE.MeshPhongMaterial({color, shininess:70})));
  }
  return g.children.length ? g : null;
}

/* مستوى 2 — كل الذرات برسمة واحدة (InstancedMesh لكل عنصر) */
function buildLOD2(rec, size){
  const g=new THREE.Group();
  const {cx,cy,cz}=rec.centre;
  const s = size / (rec.extentA/2 || 1);
  const byEl={};
  rec.atoms.forEach(a=>{
    // ذرات الحمض النووي بمجموعة لونية مستقلة — هيك بيبيّن اللولب
    // المزدوج وبالتالي بيبيّن اتجاه المحاذاة بالعين
    const el = a.isDNA ? 'DNA'
             : (ATOM_COLORS[a.element]!==undefined ? a.element : 'DEFAULT');
    (byEl[el]||(byEl[el]=[])).push(a);
  });
  const m=new THREE.Matrix4();
  for(const el in byEl){
    const list=byEl[el];
    const geo=new THREE.SphereGeometry((ATOM_RADII[el]||ATOM_RADII.DEFAULT)*s*1.05, 6, 5);
    const mat=new THREE.MeshPhongMaterial({color:ATOM_COLORS[el], shininess:70});
    const inst=new THREE.InstancedMesh(geo, mat, list.length);
    list.forEach((a,i)=>{ m.setPosition((a.x-cx)*s,(a.y-cy)*s,(a.z-cz)*s); inst.setMatrixAt(i,m); });
    inst.instanceMatrix.needsUpdate=true;
    g.add(inst);
  }
  return g;
}

function disposeGroup(g){
  if(!g) return;
  g.traverse(o=>{ o.geometry?.dispose(); o.material?.dispose(); });
}

/* ══════════════════════════════════════════════════════════════════════
   مدير الـ LOD — بينادى من loop() بمعدّل مخنوق (مش كل إطار)
   ══════════════════════════════════════════════════════════════════════ */
function updateLOD(){
  if(!proteinGroup || !camera) return;
  _lodPass++;
  let anyStruct=false, dnaCount=0, approxCount=0, expCount=0, predCount=0;

  proteinGroup.children.forEach(holder=>{
    const ud = holder.userData;
    if(!ud || !ud.protein || ud.isHalo) return;
    if(!holder.visible) return;      // المعزول مخفي → لا تحميل ولا رسم

    const dist = camera.position.distanceTo(holder.position);
    const rec  = ud.src ? PDB_CACHE.get(ud.cacheKey) : null;

    /* ── قرار المستوى بالحجم الظاهري، مش بمسافة مطلقة ──
       العتبات الثابتة كانت مربوطة بـ markerR وهو رقم ضئيل، فما كانت
       بتتحقّق إلا لما تدخل الكاميرا جوّا البنية. الحجم الظاهري
       (نصف القطر ÷ المسافة) مستقل عن مقياس البيانات وعن التكبير،
       فبيشتغل صح مع أي بنية. */
    const trueR = (rec?.status === 'ok') ? trueSceneRadius(rec) : null;
    const drawR = (trueR ? trueR : ud.baseR) * ud.magnify;
    const apparent = drawR / Math.max(dist, 1e-6);

    let want;
    if(reprMode === 'atoms')      want = 2;        // إجبار من الواجهة
    else if(reprMode === 'ribbon') want = 1;
    else want = ud.pinned ? 2                       // مثبّت بالضغط → ذرات دايماً
             : apparent > 0.030 ? 2
             : apparent > 0.010 ? 1 : 0;

    if(!lodEnabled || !ud.src) want = 0;

    if(want > 0){
      if(!rec){
        loadStructure(ud.cacheKey, ud.src).then(()=>{ ud.lod = -1; });
        want = 0;
      } else if(rec.status !== 'ok'){
        want = 0;
      } else {
        _touchCache(ud.cacheKey);
      }
    }

    if(want !== ud.lod){
      disposeGroup(ud.repr);
      if(ud.repr) holder.remove(ud.repr);
      ud.repr = null;

      if(want === 0){
        ud.repr = ud.sphere;
        ud.sphere.visible = true;
        holder.quaternion.identity();
      } else {
        // الكرة بتنخفي لما تبان البنية — وإلا بتحجبها
        ud.sphere.visible = false;

        const ax = structureAxis(rec);
        if(ax && ud.tangent){
          holder.quaternion.setFromUnitVectors(ax.axis.clone().normalize(), ud.tangent);
          ud.axisSource = ax.source;
          ud.nDna = ax.nDna;
        } else {
          holder.quaternion.identity();
          ud.axisSource = 'none';
        }

        ud.trueR = trueR; ud.drawR = drawR;
        ud.repr = (want === 1)
          ? (buildLOD1(rec, drawR, new THREE.Color(ud.cls.color)) || ud.sphere)
          : buildLOD2(rec, drawR);
      }

      if(ud.repr && ud.repr !== ud.sphere){
        if(ud.ghost) ud.repr.traverse(o=>{
          if(o.material){ o.material.transparent=true; o.material.opacity=.35; } });
        holder.add(ud.repr);
      }
      ud.lod = want;
    }

    if(ud.lod > 0){
      anyStruct=true;
      ud.axisSource==='dna' ? dnaCount++ : approxCount++;
      const src = PDB_CACHE.get(ud.cacheKey)?.structureSource;
      if(src==='experimental') expCount++; else if(src==='predicted') predCount++;
    }
    // الهالة كرة كبيرة ثابتة الحجم — بتحجب البنية لما نقرّب
    const halo = proteinGroup.children.find(x=>x.userData?.isHalo && x.userData.protein===ud.protein);
    if(halo) halo.visible = (ud.lod === 0);
  });

  updateScaleBadge(anyStruct, dnaCount, approxCount, expCount, predCount);
  _evictCache();
}

/* ══ الطيران لبروتين محدد ══
   المسار المضمون لعرض البنية الذرية: الضغط على البروتين. الـ LOD
   التلقائي بيشتغل أثناء التنقّل الحر، بس عند r=80 (نظرة عامة على بنية
   قطرها 56) ما بيمكن أي بنية بروتين تبان — الحجم الظاهري ضئيل جداً.
   لهيك الضغط بيقرّب الكاميرا وبيثبّت المستوى الذري. */
let camTween = null;

function flyToProtein(key){
  if(!proteinGroup) return;
  const h = proteinGroup.children.find(m => m.userData?.protein===key && !m.userData?.isHalo);
  proteinGroup.children.forEach(m=>{ if(m.userData) m.userData.pinned = false; });
  if(!h){ camTween=null; return; }

  h.userData.pinned = true;
  const d = h.userData;
  const drawR = (d.trueR || d.baseR) * d.magnify;
  // مسافة تخلّي البنية تملا جزءاً معقولاً من الإطار
  const targetR = Math.max(drawR / 0.08, 4);

  camTween = {
    fromPan:{x:pan.x, y:pan.y}, fromR:sph.r,
    toPan:{x:h.position.x, y:h.position.y}, toR:targetR, t:0
  };
  autoRot = false;
}

function clearFocus(){
  if(proteinGroup) proteinGroup.children.forEach(m=>{ if(m.userData) m.userData.pinned=false; });
  camTween = null;
}

/* خطوة التنعيم — بتنادى من loop() */
function stepCamTween(){
  if(!camTween) return;
  // نفس منطق autoRot: التابع ما بيحرّك كاميرته لحالو، بيتبع القائد.
  // بدون هالحارس الشاشتان بتتعاركا — وحدة بتطيّر ووحدة بتدهس عليها.
  if(camSync && !camLeader){ camTween = null; return; }

  camTween.t = Math.min(1, camTween.t + 0.055);
  const e = 1 - Math.pow(1 - camTween.t, 3);          // ease-out cubic
  // استيفاء من نقطة البداية المحفوظة — الصيغة القديمة كانت تراكمية
  // (نسبة من الباقي × عامل متزايد) وبتطلع حركة متشنّجة
  pan.x = camTween.fromPan.x + (camTween.toPan.x - camTween.fromPan.x) * e;
  pan.y = camTween.fromPan.y + (camTween.toPan.y - camTween.fromPan.y) * e;
  sph.r = camTween.fromR     + (camTween.toR     - camTween.fromR)     * e;
  updateCam();
  if(camTween.t >= 1) camTween = null;
}

/* الوسم بيقول بالضبط شو معروض: التكبير، ومصدر الاتجاه لكل بنية.
   'محور DNA' = مستنتج من بلورة مشتركة حقيقية.
   'محور تقريبي' = ما في DNA بالملف، استعملنا محور البروتين نفسه. */
function updateScaleBadge(anyStruct, dna, approx, exper, pred){
  const el=document.getElementById('scaleBadge');
  if(!el) return;
  if(!anyStruct){ el.textContent = nmPerUnit
      ? `المقياس ≈ ${(1/nmPerUnit).toFixed(2)} وحدة/nm — تقديري`
      : 'قرّب لعرض البنى'; return; }
  const bits=[`×${proteinMagnify} — مكبّر، ليس بالمقياس`];
  if(exper) bits.push(`${exper} تجريبية`);
  if(pred)  bits.push(`${pred} متنبّأة (AlphaFold)`);
  if(dna)    bits.push(`${dna} بمحور DNA`);
  if(approx) bits.push(`${approx} بمحور تقريبي`);
  el.textContent = bits.join(' · ');
}

function toggleLOD(){
  lodEnabled = !lodEnabled;
  document.getElementById('btnLod')?.classList.toggle('on', lodEnabled);
}

/* ══════════════════════════════════════════════════════════════════════
   markers البروتينات على الخيط + لستة اللوحة
   ══════════════════════════════════════════════════════════════════════ */
function removeProteinMarkers(){
  if(!proteinGroup) return;
  proteinGroup.traverse(o=>{ o.geometry?.dispose(); o.material?.dispose(); });
  scene.remove(proteinGroup);
  proteinGroup = null;
}

function buildProteinMarkers(){
  removeProteinMarkers();
  if(!bindingProteins || !showProteins || !sceneCenter) return;

  proteinGroup = new THREE.Group();
  const coords = viewMode==='smooth' && smoothPts.length>1 ? smoothPts : rawPts;
  if(!coords.length){ return; }

  /* ══ فضاءان مختلفان للفهارس ══
     coord_index (أو مطابقة region) بيرجّعوا فهرس داخل coords_raw.
     بس الرسم بيستعمل coords_smooth اللي فيها نقاط أكتر بكتير
     (٧٨ مقابل ٢٤٠ بالعيّنة). استعمال الفهرس مباشرةً بيضغط كل
     البروتينات بأول جزء من الخيط.
     الحل: نحلّ الفهرس دايماً بفضاء raw، وبعدين نحوّله نسبياً. */
  const anchor = rawPts.length ? rawPts : coords;
  const toDisplay = iRaw => {
    if(iRaw==null) return null;
    if(coords === anchor) return iRaw;
    const u = anchor.length>1 ? iRaw/(anchor.length-1) : 0;
    return Math.min(coords.length-1, Math.max(0, Math.round(u*(coords.length-1))));
  };

  // حجم الـ marker نسبة لحجم البنية حتى يضل مرئي بأي تكبير
  const bbox = new THREE.Box3().setFromPoints(
    coords.map(p=>new THREE.Vector3(p.x,p.y,p.z)));
  const markerR = Math.max(bbox.getSize(new THREE.Vector3()).length()*0.012, tubeR*0.9);

  Object.entries(bindingProteins).forEach(([key, entry])=>{
    const cls  = classifyProtein(entry);
    if(proteinFilter!=='all' && cls.key!==proteinFilter) return;
    const name = entry.protein_name || key;

    // نقطة على الجهة المعروضة
    const side = activeSide==='control' ? 'control' : 'patient';
    // الحلّ بفضاء raw (اللي الباك بيشير إله)، والتحويل للعرض بعدين
    const r = resolveProteinCoordIndex(entry[side], globalData, anchor);

    let pos=null, ghost=false, tangent=null;

    if(r.index!=null){
      const p = coords[toDisplay(r.index)];
      pos = new THREE.Vector3(p.x,p.y,p.z).sub(sceneCenter);
      tangent = tangentAt(coords, toDisplay(r.index));
    }
    else if(side==='patient' && controlData && alignTransform){
      // البروتين مفقود عند المريض بس موجود بالسليم → marker شبحي
      // بموقعه من السليم، محوَّل لإطار المريض بنفس مصفوفة المحاذاة
      const cRaw    = controlData.coords_raw || [];
      const cCoords = (viewMode==='smooth' && controlData.coords_smooth?.length>1)
        ? controlData.coords_smooth : cRaw;
      const cTo = i => (cCoords===cRaw || cRaw.length<2) ? i
        : Math.min(cCoords.length-1, Math.round(i/(cRaw.length-1)*(cCoords.length-1)));
      const rc = resolveProteinCoordIndex(entry.control, controlData, cRaw);
      if(rc.index!=null && cCoords.length){
        const cp = cCoords[cTo(rc.index)];
        const v = new THREE.Vector3(cp.x,cp.y,cp.z).sub(alignTransform.cCenter);
        if(alignTransform.mirror) v.z = -v.z;
        pos = v.applyQuaternion(alignTransform.quat);
        // المماس من جهة السليم لازم يمرق بنفس تحويل المحاذاة
        const tRaw = tangentAt(cCoords, cTo(rc.index));
        if(tRaw){
          const tv = tRaw.clone();
          if(alignTransform.mirror) tv.z = -tv.z;
          tangent = tv.applyQuaternion(alignTransform.quat).normalize();
        }
        ghost = true;
      }
    }

    entry.__resolved = { index:r.index, reason:r.reason, placed: !!pos, ghost };
    if(!pos) return;   // بيضل باللستة بدون marker — ما منهار

    const color = new THREE.Color(cls.color);

    // حاوية لكل بروتين — بتسمح نبدّل التمثيل (كرة/شريط/ذرات) بدون
    // ما نلمس الموقع ولا نعيد بناء المجموعة كلها
    const holder = new THREE.Group();
    holder.position.copy(pos);

    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(markerR, 16, 12),
      new THREE.MeshPhongMaterial({
        color, emissive:color.clone().multiplyScalar(.35),
        shininess:80, transparent:ghost, opacity: ghost?.35:1,
        depthWrite: !ghost
      })
    );
    holder.add(sphere);

    holder.userData = {
      protein:key, name, cls, ghost, entry,
      sphere, repr:sphere, lod:0,
      baseR: markerR, tangent,
      magnify: proteinMagnify,
      src: resolveStructureSource(key, entry),
      cacheKey: key
    };
    proteinGroup.add(holder);

    // هالة خفيفة للمفقود/المكتسب حتى تلفت النظر
    if(cls.key==='missing' || cls.key==='gained'){
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(markerR*2.1, 16, 12),
        new THREE.MeshBasicMaterial({color, transparent:true, opacity:.13,
                                     side:THREE.BackSide, depthWrite:false})
      );
      halo.position.copy(pos);
      halo.userData={isHalo:true, protein:key};
      proteinGroup.add(halo);
    }
  });

  scene.add(proteinGroup);
  applyIsolation();
  buildProteinList();
}

function buildProteinList(){
  const box = document.getElementById('protein-list');
  const sec = document.getElementById('protein-sec');
  if(sec) sec.style.display = bindingProteins ? '' : 'none';
  if(!box || !bindingProteins) return;

  const entries = Object.entries(bindingProteins);
  // الترتيب: المفقود أولاً، بعدين الأضعف، وهكذا — الأهم سريرياً بالأول
  const rank = {missing:0, gained:1, weakened:2, stronger:3, stable:4, unknown:5};
  entries.sort((a,b)=>{
    const ra=rank[classifyProtein(a[1]).key], rb=rank[classifyProtein(b[1]).key];
    if(ra!==rb) return ra-rb;
    return (a[1].protein_name||a[0]).localeCompare(b[1].protein_name||b[0]);
  });

  const counts={};
  entries.forEach(([,e])=>{ const k=classifyProtein(e).key; counts[k]=(counts[k]||0)+1; });
  const sum=document.getElementById('protein-summary');
  if(sum){
    const bits=[];
    if(counts.missing)  bits.push(`<span style="color:#e5766f">${counts.missing} مفقود</span>`);
    if(counts.weakened) bits.push(`<span style="color:#e0b24d">${counts.weakened} أضعف</span>`);
    if(counts.gained)   bits.push(`<span style="color:#7aa2f7">${counts.gained} مكتسب</span>`);
    if(counts.stronger) bits.push(`<span style="color:#6fd3c0">${counts.stronger} أقوى</span>`);
    if(counts.stable)   bits.push(`<span style="color:#8eb69b">${counts.stable} مستقر</span>`);
    sum.innerHTML = bits.join(' · ') || `${entries.length} بروتين`;
  }

  box.innerHTML='';
  entries.forEach(([key, entry])=>{
    const cls=classifyProtein(entry);
    const name=entry.protein_name||key;
    const res=entry.__resolved||{};
    const d=Number(entry.delta_score);
    const dTxt=isFinite(d) ? (d>0?'+':'')+d.toFixed(2) : '—';

    const row=document.createElement('div');
    row.className='prot-item'+(res.placed?'':' unplaced');
    row.title = res.placed
      ? `الموقع: ${res.reason}${res.ghost?' (شبحي — من السليم)':''}`
      : `بدون علامة على الخيط — ${res.reason||'تعذّر تحديد الموقع'}`;

    row.innerHTML =
      `<span class="prot-dot" style="background:${cls.color}"></span>`+
      `<span class="prot-name">${name}</span>`+
      `<span class="prot-tag">${cls.label}</span>`+
      `<span class="prot-delta">${dTxt}</span>`+
      (res.placed ? '' : '<span class="prot-warn" title="بدون موقع">⚠</span>');

    if(res.placed) row.onclick=(ev)=>focusProtein(key, ev);
    box.appendChild(row);
  });
}

/* ══ إظهار/إخفاء البروتينات ══
   الواجهة الجديدة بتبعت قائمة المخفيين صراحةً (صندوق اختيار لكل بروتين)
   — أمرن من وضع العزل القديم: بتقدري تخفي مجموعة وتخلي مجموعة.
   المخفي ما بيحمّل بنيته إطلاقاً (شوف الحارس بـ updateLOD) فهاد توفير
   أداء حقيقي مش بس إخفاء بصري. */
let hiddenProteins = new Set();
let focusedProtein = null;

function applyIsolation(){
  if(!proteinGroup) return;
  proteinGroup.children.forEach(m=>{
    const key = m.userData?.protein;
    if(!key) return;
    const show = !hiddenProteins.has(key);
    m.visible = show;
    if(!show && m.userData.pinned) m.userData.pinned = false;
  });
}

function setProteinVisibility(hiddenList){
  hiddenProteins = new Set(Array.isArray(hiddenList) ? hiddenList : []);
  applyIsolation();
}

/* ══ تجاوز مستوى التمثيل ══
   'auto' = القرار حسب الحجم الظاهري (السلوك التلقائي)
   'ribbon' / 'atoms' = إجبار، بلا انتظار التقريب */
let reprMode = 'auto';
function setReprMode(m){
  reprMode = (m==='atoms' || m==='ribbon') ? m : 'auto';
  if(proteinGroup) proteinGroup.children.forEach(h=>{ if(h.userData) h.userData.lod = -1; });
}

/* تكبير/إبراز بروتين محدد — بتنادى محلياً أو من صفحة المقارنة عبر postMessage.
   key=null بيرجّع كل شي لحجمه الطبيعي. */
function focusProtein(key, ev){
  if(!proteinGroup) return;
  focusedProtein = key || null;
  key ? flyToProtein(key) : clearFocus();
  proteinGroup.children.forEach(m=>{
    if(!m.userData?.protein) return;
    const on = key!=null && m.userData.protein===key;
    m.scale.setScalar(on?2.2:1);
    const sp = m.userData.sphere;
    if(sp?.material?.emissive)
      sp.material.emissive.setHex(on?0xffffff:new THREE.Color(m.userData.cls.color)
        .multiplyScalar(.35).getHex());
  });
  applyIsolation();
  document.querySelectorAll('.prot-item').forEach(el=>el.classList.remove('active'));
  ev?.currentTarget?.classList?.add('active');
}

/* فلترة الماركرات حسب الحالة — مربوطة بشرائح المسار الجينومي */
let proteinFilter='all';
function setProteinFilter(f){ proteinFilter=f||'all'; buildProteinMarkers(); }

function toggleProteins(){
  showProteins=!showProteins;
  document.getElementById('btnProt')?.classList.toggle('on', showProteins);
  if(showProteins) buildProteinMarkers(); else removeProteinMarkers();
}

function removeControlOverlay(){
  if(controlMesh){ scene.remove(controlMesh); controlMesh.geometry?.dispose(); controlMesh=null; }
}

/* يعرض نتيجة المحاذاة بلوحة التفاصيل (لو العناصر موجودة بالصفحة) */
function updateAlignPanel(){
  const set=(id,v)=>{ const el=document.getElementById(id); if(el) el.textContent=v; };
  const sec=document.getElementById('align-sec');
  if(sec) sec.style.display = alignInfo ? '' : 'none';
  if(!alignInfo) return;

  set('a-pairs', alignInfo.pairs + ' نقطة');
  set('a-mode',  alignInfo.mode==='region' ? 'حسب المنطقة' : 'حسب الفهرس');
  set('a-mirror', alignInfo.mirror ? 'نعم' : 'لا');
  set('a-rmsd',  alignInfo.rmsd==null ? '—' : alignInfo.rmsd.toFixed(4));

  const el=document.getElementById('a-dev');
  if(el && alignInfo.rmsdNorm!=null){
    const pct=(alignInfo.rmsdNorm*100);
    el.textContent = pct.toFixed(1)+'%';
    // أخضر = بنيتان متقاربتان · أصفر = انحراف ملحوظ · أحمر = اختلاف كبير
    el.style.color = pct<15 ? 'var(--primary)' : pct<35 ? 'var(--warn)' : 'var(--danger)';
  }
}

// زر التبديل: إظهار/إخفاء طبقة السليم
function toggleControl(){
  showControl=!showControl;
  document.getElementById('btnControl')?.classList.toggle('on', showControl);
  if(showControl) buildControlOverlay(); else removeControlOverlay();
}

function showLoading(msg){
  const L=document.getElementById('loading'); if(!L) return;
  const m=document.getElementById('load-msg'); if(m && msg) m.textContent=msg;
  L.style.display='flex';
}
function hideLoading(){ const L=document.getElementById('loading'); if(L) L.style.display='none'; }
function showError(msg){
  const m=document.getElementById('load-msg');
  if(m){ m.textContent='✕ '+msg; m.classList.add('err'); }
  const sp=document.querySelector('#loading .spin'); if(sp) sp.style.display='none';
  const L=document.getElementById('loading'); if(L) L.style.display='flex';
}

// ══ تحميل يدوي من ملف (fallback — يظل شغّال دايماً) ══
function loadJSON(input){
  const file=input.files[0]; if(!file) return;
  showLoading('جاري التحليل ومعالجة البيانات...');
  const reader=new FileReader();
  reader.onload=e=>{
    try{
      const parsed=JSON.parse(e.target.result);
      // لو الملف فيه patient/control → عرض مقارن، وإلا عرض مفرد
      if(parsed && (parsed.patient || parsed.control)) applyDualData(parsed);
      else applyData(parsed);
    }
    catch(err){ alert('خطأ في الملف: '+err.message); console.error(err); }
    hideLoading();
  };
  reader.readAsText(file,'utf-8');
}

// ══ تحميل تلقائي من الباك عبر ?output_id=<id> ══
// شكل الاستجابة المتوقّع = نفس شكل chr21_features.json
// (coords_raw, coords_smooth, tad_colors, tad_boundaries, chrom, start, end,
//  resolution, stress, n_tads). لو الباك رجّع شكل مبسّط (coordinates+edges بس)،
//  بنطبّعه هون لنفس الشكل عبر normalizeBackendPayload().
async function loadFromAPI(outputId, opts){
  opts=opts||{};
  showLoading('جاري جلب بيانات التحليل من الخادم…');
  try{
    const url = chromoVizURL(outputId);
    const headers={'Accept':'application/json'};
    const token = opts.token || localStorage.getItem('chromogen-token');
    if(token) headers['Authorization']='Bearer '+token;

    const res = await fetch(url, { headers });
    if(!res.ok){
      const txt = await res.text().catch(()=> '');
      throw new Error(`HTTP ${res.status} — ${txt.slice(0,120) || 'تعذّر جلب البيانات'}`);
    }
    const payload = await res.json();
    // لو الاستجابة فيها patient/control → عرض مقارن، وإلا عرض مفرد (توافق خلفي)
    if(payload && (payload.patient || payload.control)) applyDualData(payload, opts.side || 'both');
    else applyData(normalizeBackendPayload(payload));
    hideLoading();
    return true;
  }catch(err){
    console.error('[hic] API load failed:', err);
    // fallback: منخلّي المستخدم يرفع ملف يدوياً بدل ما نفشل بصمت
    showError((err.message||'فشل الجلب من الخادم') + ' — تقدر تستورد ملف JSON يدوياً.');
    return false;
  }
}

// يحوّل أي شكل باك (غني أو مبسّط) لنفس شكل الراسم.
// - لو أصلاً فيه coords_raw ككائنات {x,y,z} → منرجّعه كما هو.
// - لو فيه coordinates كمصفوفات [x,y,z] (شكل coords_service الحالي) → منحوّلها.
function normalizeBackendPayload(p){
  if(!p || typeof p!=='object') return p;
  // شكل غني جاهز
  if(Array.isArray(p.coords_raw) && p.coords_raw.length && typeof p.coords_raw[0]==='object')
    return p;

  const out = Object.assign({}, p);
  const arr = p.coordinates || p.coords || null; // [[x,y,z],...]
  if(Array.isArray(arr) && arr.length){
    out.coords_raw = arr.map((c,i)=>({
      x:+c[0], y:+c[1], z:+c[2],
      region:(p.regions && p.regions[i]) || '',
      density:0.6, deviation:0, tad_id:0, is_boundary:false
    }));
    // ما في خيط ناعم من الباك المبسّط → منخلّي الراسم يستعمل raw
    out.coords_smooth = out.coords_smooth || [];
    out.n_tads    = out.n_tads    || 1;
    out.tad_colors= out.tad_colors|| ['#8eb69b'];
    out.tad_boundaries = out.tad_boundaries || [];
  }
  return out;
}

// ══ TAD List ══
function buildTADList(d){
  const container=document.getElementById('tad-list');
  container.innerHTML='';
  if(!d.tad_colors||!d.n_tads) return;
  for(let i=0;i<d.n_tads;i++){
    const pts=rawPts.filter(p=>p.tad_id===i);
    const avgDen=(pts.reduce((s,p)=>s+(p.density||0),0)/Math.max(pts.length,1)*100).toFixed(0);
    const div=document.createElement('div');
    div.className='tad-item';
    div.id='tad-item-'+i;
    const tColor = d.tad_colors[i] || '#c9a84c'; 
    div.innerHTML=
      `<div class="tad-dot" style="background:${tColor}"></div>`+
      `<span class="tad-label">TAD ${i+1}</span>`+
      `<span class="tad-size">${pts.length}b · ${avgDen}%</span>`;
    div.onclick=()=>isolateTAD(i);
    container.appendChild(div);
  }
}

// ══ Build Scene ══
/* ── هندسة الشريط (Ribbon) ──
   بدل مقطع دائري (أنبوب)، نبني مقطعاً مستطيلاً مسطّحاً: عريض ورفيع.
   نستعمل إطارات Frenet من المنحنى نفسه حتى لا يلتوي الشريط عشوائياً.

   مهم: العرض يُقاس **نسبةً إلى حجم البنية** لا بوحدات ثابتة، لأن مقاييس
   المجسّمات تختلف كثيراً (نصف قطر 0.7 مقابل 24). العرض الثابت يجعل
   الشريط يبتلع البنية الصغيرة ويصير كتلة صلبة. */
function buildRibbonGeometry(curve, segments, width){
  const frames = curve.computeFrenetFrames(segments, false);
  // نعاير العرض على نصف قطر البنية (لا على طول الشريحة) — أثبت عبر
  // المجسّمات ذات المقاييس المختلفة جداً (نصف قطر 0.7 مقابل 24).
  const pts = curve.getPoints(Math.min(segments, 200));
  const cx = pts.reduce((s,p)=>s+p.x,0)/pts.length;
  const cy = pts.reduce((s,p)=>s+p.y,0)/pts.length;
  const cz = pts.reduce((s,p)=>s+p.z,0)/pts.length;
  let radius = 0;
  for(const p of pts){
    const d = Math.hypot(p.x-cx, p.y-cy, p.z-cz);
    if(d > radius) radius = d;
  }
  if(!(radius > 0)) radius = 1;

  const halfW = width * radius * 0.022;   // ~3% من نصف القطر عند السماكة 1.4
  const halfT = Math.max(halfW * 0.13, radius * 0.0008);
  const pos=[], idx=[], uvs=[];
  const P=new THREE.Vector3();

  for(let i=0;i<=segments;i++){
    curve.getPointAt(i/segments, P);
    const N = frames.normals[i], B = frames.binormals[i];
    const corners = [[halfW,halfT],[halfW,-halfT],[-halfW,-halfT],[-halfW,halfT]];
    for(const [w,t] of corners){
      pos.push(P.x + B.x*w + N.x*t, P.y + B.y*w + N.y*t, P.z + B.z*w + N.z*t);
      uvs.push(i/segments, 0);
    }
  }
  for(let i=0;i<segments;i++){
    const a=i*4, b=(i+1)*4;
    for(let k=0;k<4;k++){
      const k2=(k+1)%4;
      idx.push(a+k, b+k, a+k2, a+k2, b+k, b+k2);
    }
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos,3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs,2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/* تلوين الشريط حسب الموقع على الخيط (4 رؤوس لكل مقطع) */
function colorRibbon(geo, segments, pts){
  const cols=[];
  for(let i=0;i<=segments;i++){
    const t=i/segments;
    const p=pts[Math.floor(t*(pts.length-1))]||pts[pts.length-1];
    const c=getClr(t, p.density||.5, p.tad_id||0, p.deviation||0);
    for(let k=0;k<4;k++) cols.push(c.r,c.g,c.b);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(cols,3));
}

function buildScene(){
  clearMeshes();
  const pts=viewMode==='smooth'?smoothPts:rawPts;
  if(!pts||pts.length<2) return;

  const cx=pts.reduce((s,p)=>s+p.x,0)/pts.length;
  const cy=pts.reduce((s,p)=>s+p.y,0)/pts.length;
  const cz=pts.reduce((s,p)=>s+p.z,0)/pts.length;
  // markers البروتينات لازم تنرسم بنفس إطار الخيط بالضبط
  sceneCenter=new THREE.Vector3(cx,cy,cz);
  // معايرة وحدات MDS → نانومتر (لازمة للحجم الحقيقي للبروتينات)
  nmPerUnit = calibrateScale(pts, globalData?.resolution);
  const v3=pts.map(p=>new THREE.Vector3(p.x-cx,p.y-cy,p.z-cz));
  const curve=new THREE.CatmullRomCurve3(v3,false,'catmullrom',.5);
  const segs=Math.min(v3.length*4,1800);

  // ── الشريط الرئيسي (بدل الأنبوب الدائري) ──
  const geo=buildRibbonGeometry(curve,segs,tubeR);
  colorRibbon(geo,segs,pts);
  meshes.tube=new THREE.Mesh(geo,new THREE.MeshPhongMaterial(
    {vertexColors:true,shininess:110,specular:new THREE.Color(0x3a3530),side:THREE.DoubleSide}));
  scene.add(meshes.tube);

  // ── Glow ──
  if(effects.glow){
    const geoG=new THREE.TubeGeometry(curve,segs/2,tubeR*3.5,8,false);
    const cgCnt=geoG.getAttribute('position').count;
    const gc=[];
    for(let i=0;i<cgCnt;i++){
      const t=i/cgCnt;
      const idx=Math.floor(t*(pts.length-1));
      const p=pts[idx]||pts[pts.length-1];
      const c=getClr(t,p.density||.5,p.tad_id||0,0);
      gc.push(c.r,c.g,c.b);
    }
    geoG.setAttribute('color',new THREE.Float32BufferAttribute(gc,3));
    meshes.glow=new THREE.Mesh(geoG,new THREE.MeshBasicMaterial(
      {vertexColors:true,transparent:true,opacity:.07,side:THREE.BackSide}));
    scene.add(meshes.glow);
  }

  // ── حدود TAD ──
  if(effects.bounds && globalData?.tad_boundaries){
    const bGeo=new THREE.BufferGeometry();
    const bPos=[];
    globalData.tad_boundaries.forEach(bi=>{
      if(bi<rawPts.length){
        const p=rawPts[bi];
        bPos.push(p.x-cx,p.y-cy,p.z-cz);
      }
    });
    if(bPos.length>0){
      bGeo.setAttribute('position',new THREE.Float32BufferAttribute(bPos,3));
      meshes.bounds=new THREE.Points(bGeo,new THREE.PointsMaterial(
        {color:0xc9a84c,size:4.5,transparent:true,opacity:.95,sizeAttenuation:true})); 
      scene.add(meshes.bounds);
    }
  }

  // ── RMSD highlighting ──
  if(effects.rmsd){
    const hiGeo=new THREE.BufferGeometry();
    const hiPos=[],hiCol=[];
    rawPts.forEach((p,i)=>{
      if((p.deviation||0)>.5){
        hiPos.push(p.x-cx,p.y-cy,p.z-cz);
        const intensity=(p.deviation-.5)*2;
        hiCol.push(1,1-intensity*.8,0);
      }
    });
    if(hiPos.length>0){
      hiGeo.setAttribute('position',new THREE.Float32BufferAttribute(hiPos,3));
      hiGeo.setAttribute('color',new THREE.Float32BufferAttribute(hiCol,3));
      meshes.rmsdTube=new THREE.Points(hiGeo,new THREE.PointsMaterial(
        {vertexColors:true,size:4,transparent:true,opacity:.9,sizeAttenuation:true}));
      scene.add(meshes.rmsdTube);
    }
  }

  // ── نقاط hover ──
  const rCx=rawPts.reduce((s,p)=>s+p.x,0)/rawPts.length;
  const rCy=rawPts.reduce((s,p)=>s+p.y,0)/rawPts.length;
  const rCz=rawPts.reduce((s,p)=>s+p.z,0)/rawPts.length;
  const dg=new THREE.BufferGeometry();
  const dp=[],dc=[];
  rawPts.forEach((p,i)=>{
    dp.push(p.x-rCx,p.y-rCy,p.z-rCz);
    const col=globalData?.tad_colors?.[p.tad_id||0]||'#c9a84c';
    const rgb=hexToRgb(col);
    dc.push(rgb.r,rgb.g,rgb.b);
  });
  dg.setAttribute('position',new THREE.Float32BufferAttribute(dp,3));
  dg.setAttribute('color',new THREE.Float32BufferAttribute(dc,3));
  // بوضع الخيط الناعم: النقاط شبه شفّافة (تبقى للـ hover/raycasting بس ما توسّخ المنظر).
  // بوضع "نقاط": تظهر واضحة.
  const dotsVisible = viewMode==='raw';
  meshes.dots=new THREE.Points(dg,new THREE.PointsMaterial(
    {vertexColors:true,size:dotsVisible?3:2,transparent:true,
     opacity:dotsVisible?.85:.0,sizeAttenuation:true,depthWrite:false}));
  scene.add(meshes.dots);

  // ضبط كاميرا
  const maxR=Math.max(...pts.map(p=>Math.abs(p.x-cx)),
                       ...pts.map(p=>Math.abs(p.y-cy)),
                       ...pts.map(p=>Math.abs(p.z-cz)));
  sph.r=Math.max(maxR*3,30); updateCam();
}

function clearMeshes(){
  Object.values(meshes).forEach(m=>{if(m){scene.remove(m);m.geometry?.dispose();}});
  Object.keys(meshes).forEach(k=>meshes[k]=null);
}

// ══ Colors ══
function getClr(t,density,tadId,deviation){
  switch(clrMode){
    case 'emerald':{
      // متدرّج أخضر أنيق واحد (فاتح → غامق) بروح البروتين — من داكن مخضرّ لفاتح مينت
      const a=new THREE.Color(0x2f6b57), b=new THREE.Color(0x8eb69b), c=new THREE.Color(0xdaf1de);
      return t<.5 ? new THREE.Color().lerpColors(a,b,t*2)
                  : new THREE.Color().lerpColors(b,c,(t-.5)*2);
    }
    case 'plasma':
      return new THREE.Color(.1+t*.9,Math.sin(t*Math.PI)*.55,Math.max(0,1-t*1.1));
    case 'cool':
      return new THREE.Color().setHSL(.55+t*.25,.9,.4+t*.2);
    case 'health':{
      const a=new THREE.Color(0x22c55e),b=new THREE.Color(0xeab308),c2=new THREE.Color(0xef4444);
      return t<.5?new THREE.Color().lerpColors(a,b,t*2):new THREE.Color().lerpColors(b,c2,(t-.5)*2);
    }
    case 'density':
      return new THREE.Color().setHSL(.13,.6+density*.4, .2+density*.6);
    case 'tad':{
      const pal=globalData?.tad_colors||['#c9a84c'];
      const hex=pal[tadId%pal.length]||'#c9a84c';
      return new THREE.Color(hex);
    }
    default: return new THREE.Color(0xc9a84c);
  }
}

function hexToRgb(hex){
  const r=parseInt(hex.slice(1,3),16)/255;
  const g=parseInt(hex.slice(3,5),16)/255;
  const b=parseInt(hex.slice(5,7),16)/255;
  return {r,g,b};
}

// ══ Isolate TAD ══
async function isolateTAD(tadId){
  if(!globalData) return;
  const pts=rawPts.filter(p=>p.tad_id===tadId);
  if(pts.length<3) return;

  document.querySelectorAll('.tad-item').forEach(el=>el.classList.remove('active'));
  document.getElementById('tad-item-'+tadId)?.classList.add('active');

  const overlay=document.getElementById('isolate-overlay');
  const color=globalData.tad_colors?.[tadId]||'#c9a84c';

  document.getElementById('iso-title').textContent=`TAD ${tadId+1}`;
  document.getElementById('iso-title').style.color=color;
  document.getElementById('iso-pts').textContent=pts.length+' نقطة';
  const avgDen=(pts.reduce((s,p)=>s+(p.density||0),0)/pts.length*100).toFixed(0);
  document.getElementById('iso-den').textContent=avgDen+'% كثافة';

  overlay.classList.add('visible');

  await new Promise(r=>requestAnimationFrame(r));
  await new Promise(r=>setTimeout(r,30));

  isoRunning=false;
  await new Promise(r=>setTimeout(r,50));

  const freshCanvas=document.getElementById('isolate-canvas');
  const cw=freshCanvas.clientWidth||window.innerWidth-220;
  const ch=freshCanvas.clientHeight||window.innerHeight-52;

  isoScene=new THREE.Scene();
  isoScene.background=new THREE.Color(0x080808);
  addLights(isoScene);

  isoCamera=new THREE.PerspectiveCamera(55, cw/ch, 0.1, 1000);

  if(isoRenderer){ isoRenderer.dispose(); }
  isoRenderer=new THREE.WebGLRenderer({canvas:freshCanvas, antialias:true, preserveDrawingBuffer:true});
  isoRenderer.setPixelRatio(Math.min(devicePixelRatio,2));
  isoRenderer.setSize(cw, ch);

  const cx=pts.reduce((s,p)=>s+p.x,0)/pts.length;
  const cy=pts.reduce((s,p)=>s+p.y,0)/pts.length;
  const cz=pts.reduce((s,p)=>s+p.z,0)/pts.length;
  const v3=pts.map(p=>new THREE.Vector3(p.x-cx,p.y-cy,p.z-cz));

  let maxR=10;
  if(v3.length>=2){
    const curve=new THREE.CatmullRomCurve3(v3,false,'catmullrom',.5);
    const geo=buildRibbonGeometry(curve,v3.length*8,tubeR*1.4);
    const mat=new THREE.MeshPhongMaterial({color:new THREE.Color(color),shininess:140,
      specular:new THREE.Color(0x3a3530),side:THREE.DoubleSide});
    isoScene.add(new THREE.Mesh(geo,mat));

    const geoG=new THREE.TubeGeometry(curve,v3.length*4,tubeR*4.5,8,false);
    isoScene.add(new THREE.Mesh(geoG,new THREE.MeshBasicMaterial(
      {color:new THREE.Color(color),transparent:true,opacity:.08,side:THREE.BackSide})));

    const dg=new THREE.BufferGeometry();
    const dp=[];
    v3.forEach(p=>dp.push(p.x,p.y,p.z));
    dg.setAttribute('position',new THREE.Float32BufferAttribute(dp,3));
    isoScene.add(new THREE.Points(dg,new THREE.PointsMaterial(
      {color:0xffffff,size:2.5,transparent:true,opacity:.8,sizeAttenuation:true})));

    maxR=Math.max(...v3.map(p=>Math.abs(p.x)),
                   ...v3.map(p=>Math.abs(p.y)),
                   ...v3.map(p=>Math.abs(p.z)));
  }

  let isoSph={theta:.4,phi:1.2,r:Math.max(maxR*3,15)};
  let isoPan={x:0,y:0};
  let isoDrag=false,isoRDrag=false,isoPrev={x:0,y:0};
  let isoAutoRot=true;

  isoCamera.aspect=freshCanvas.clientWidth/freshCanvas.clientHeight;
  isoCamera.updateProjectionMatrix();

  function updateIsoCam(){
    const{theta,phi,r}=isoSph;
    isoCamera.position.set(
      r*Math.sin(phi)*Math.cos(theta)+isoPan.x,
      r*Math.cos(phi)+isoPan.y,
      r*Math.sin(phi)*Math.sin(theta));
    isoCamera.lookAt(isoPan.x,isoPan.y,0);
  }
  updateIsoCam();

  freshCanvas.addEventListener('mousedown',e=>{
    isoDrag=true; isoRDrag=e.button===2;
    isoPrev={x:e.clientX,y:e.clientY};
    isoAutoRot=false;
    document.getElementById('iso-rot').textContent='▶ تشغيل الدوران';
    document.getElementById('iso-rot').classList.remove('on');
    e.stopPropagation();
  });
  window.addEventListener('mousemove',isoMouseMove=e=>{
    if(!isoDrag) return;
    const dx=e.clientX-isoPrev.x, dy=e.clientY-isoPrev.y;
    if(isoRDrag){isoPan.x-=dx*.04;isoPan.y+=dy*.04;}
    else{
      isoSph.theta-=dx*.005;
      isoSph.phi=Math.max(.04,Math.min(Math.PI-.04,isoSph.phi+dy*.005));
    }
    updateIsoCam();
    isoPrev={x:e.clientX,y:e.clientY};
  });
  window.addEventListener('mouseup',()=>isoDrag=false);

  freshCanvas.addEventListener('wheel',e=>{
    isoSph.r=Math.max(2,Math.min(300,isoSph.r+e.deltaY*.03));
    updateIsoCam();
    e.preventDefault();
    e.stopPropagation();
  },{passive:false});
  freshCanvas.addEventListener('contextmenu',e=>e.preventDefault());

  const isoRotBtn=document.getElementById('iso-rot');
  const isoResetBtn=document.getElementById('iso-reset');
  const isoPngBtn=document.getElementById('iso-png');

  isoRotBtn.onclick=()=>{
    isoAutoRot=!isoAutoRot;
    isoRotBtn.textContent=isoAutoRot?'⏸ إيقاف الدوران':'▶ تشغيل الدوران';
    isoRotBtn.classList.toggle('on',isoAutoRot);
  };
  isoResetBtn.onclick=()=>{
    isoSph={theta:.4,phi:1.2,r:Math.max(maxR*3,15)};
    isoPan={x:0,y:0};
    updateIsoCam();
  };
  isoPngBtn.onclick=()=>{
    isoRenderer.render(isoScene,isoCamera);
    const a=document.createElement('a');
    a.download=`Chromogen_TAD_${tadId+1}_${Date.now()}.png`;
    a.href=freshCanvas.toDataURL('image/png',1.0);
    a.click();
  };

  isoRunning=true;
  function isoLoop(){
    if(!isoRunning) return;
    requestAnimationFrame(isoLoop);
    if(isoAutoRot){ isoSph.theta+=.003; updateIsoCam(); }
    isoRenderer.render(isoScene,isoCamera);
  }
  isoLoop();
}

function exitIsolate(){
  isoRunning=false;
  document.getElementById('isolate-overlay').classList.remove('visible');
  document.querySelectorAll('.tad-item').forEach(el=>el.classList.remove('active'));
}

// ══ UI ══
function switchMode(m){
  viewMode=m;
  document.getElementById('btnSm').classList.toggle('on',m==='smooth');
  document.getElementById('btnRw').classList.toggle('on',m==='raw');
  buildScene();
  if(controlData) buildControlOverlay();   // نعيد رسم طبقة السليم بنفس الوضع
}

function setClr(m,btn){
  clrMode=m;
  document.querySelectorAll('.clr').forEach(b=>b.style.borderColor='transparent');
  btn.style.borderColor='#fff';
  buildScene();
}

function setRadius(v){ tubeR=v/10; buildScene(); }

function toggleEffect(key){
  effects[key]=!effects[key];
  const ids={glow:'btnGlow',bounds:'btnBound',rmsd:'btnRmsd'};
  document.getElementById(ids[key])?.classList.toggle('on',effects[key]);
  buildScene();
}

function toggleRot(){
  autoRot=!autoRot;
  const b=document.getElementById('btnR');
  b.textContent=autoRot?'⏸':'▶';
  b.classList.toggle('on',autoRot);
}

function resetCam(){sph={theta:.4,phi:1.2,r:80};pan={x:0,y:0};updateCam();}

function exportPNG(){
  renderer.render(scene,camera);
  const a=document.createElement('a');
  a.download='Chromogen_3D_'+Date.now()+'.png';
  a.href=renderer.domElement.toDataURL('image/png',1.0);
  a.click();
}

// ══ Camera ══
function updateCam(){
  const{theta,phi,r}=sph;
  camera.position.set(
    r*Math.sin(phi)*Math.cos(theta)+pan.x,
    r*Math.cos(phi)+pan.y,
    r*Math.sin(phi)*Math.sin(theta));
  camera.lookAt(pan.x,pan.y,0);
  // ما منعلّم dirty لو التغيير أصلاً جاي من شاشة تانية (منع الحلقة)
  if(!applyingRemoteCam) camDirty = true;
}

// ══ Events ══
function setupEvents(c){
  // أي لمسة على هالشاشة بتخليها القائدة
  renderer.domElement.addEventListener('mouseenter', claimCamLeadership);
  renderer.domElement.addEventListener('mousedown',e=>{
    claimCamLeadership();
    if(camTween) camTween=null;          // السحب بيوقف الطيران فوراً
    drag=true;rDrag=e.button===2;
    prev={x:e.clientX,y:e.clientY};
    autoRot=false;
    document.getElementById('btnR').textContent='▶';
    document.getElementById('btnR').classList.remove('on');
  });
  window.addEventListener('mousemove',e=>{
    if(!drag){doHover(e,c);return;}
    const dx=e.clientX-prev.x,dy=e.clientY-prev.y;
    if(rDrag){pan.x-=dx*.05;pan.y+=dy*.05;}
    else{sph.theta-=dx*.004;sph.phi=Math.max(.04,Math.min(Math.PI-.04,sph.phi+dy*.004));}
    updateCam();prev={x:e.clientX,y:e.clientY};
  });
  window.addEventListener('mouseup',()=>drag=false);
  renderer.domElement.addEventListener('wheel',e=>{
    sph.r=Math.max(2,Math.min(500,sph.r+e.deltaY*.04));
    updateCam();e.preventDefault();
  },{passive:false});
  renderer.domElement.addEventListener('contextmenu',e=>e.preventDefault());
  window.addEventListener('resize',()=>{
    camera.aspect=c.clientWidth/c.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(c.clientWidth,c.clientHeight);
  });
}

function doHover(e,c){
  if(!meshes.dots||rawPts.length===0) return;
  const rect=c.getBoundingClientRect();
  mouse.x=((e.clientX-rect.left)/rect.width)*2-1;
  mouse.y=-((e.clientY-rect.top)/rect.height)*2+1;
  raycaster.setFromCamera(mouse,camera);
  raycaster.params.Points.threshold=2.5;
  const hits=raycaster.intersectObject(meshes.dots);
  const tip=document.getElementById('tip');
  if(hits.length>0){
    const idx=hits[0].index;
    const p=rawPts[idx];
    const reg=p.region||`نقطة ${idx}`;
    const den=p.density!=null?(p.density*100).toFixed(0)+'%':'—';
    const dev=p.deviation!=null?(p.deviation*100).toFixed(0)+'%':'—';
    const tadColor=globalData?.tad_colors?.[p.tad_id||0]||'#c9a84c';
    const devNum=p.deviation||0;
    const devClass=devNum>.7?'warn':devNum>.4?'gold':'ok';

    tip.style.display='block';
    tip.style.left=(e.clientX+14)+'px';
    tip.style.top =(e.clientY-10)+'px';
    tip.innerHTML=
      `<strong style="color:var(--gold); font-family:var(--font-display); font-size:14px; letter-spacing:1px;">${reg}</strong><br>`+
      `<div style="height:1px; background:linear-gradient(90deg,var(--border),transparent); margin:6px 0;"></div>`+
      `<span style="color:var(--ivory-muted)">المجموعة: </span>`+
      `<span style="color:${tadColor}; font-weight:bold;">■ ${(p.tad_id||0)+1}</span>`+
      (p.is_boundary?` <span style="color:#fbbf24; font-size:10px;">(حد فاصِل)</span>`:'')+`<br>`+
      `<span style="color:var(--ivory-muted)">الكثافة: </span><span style="color:${devNum>.5?'#e06060':'#6abf8a'}">${den}</span><br>`+
      `<span style="color:var(--ivory-muted)">الانحراف: </span><span class="${devClass}" style="color:${devNum>.7?'#e06060':devNum>.4?'#eab308':'#6abf8a'}">${dev}</span>`;

    document.getElementById('s-reg').textContent=reg;
    document.getElementById('s-tad').textContent='TAD '+((p.tad_id||0)+1);
    document.getElementById('s-den').textContent=den;
    document.getElementById('s-dev').textContent=dev;
    document.getElementById('s-x').textContent=p.x.toFixed(2);
    document.getElementById('s-y').textContent=p.y.toFixed(2);
    document.getElementById('s-z').textContent=p.z.toFixed(2);
  } else { tip.style.display='none'; }
}

// ══ Loop ══
function loop(){
  requestAnimationFrame(loop);
  // التابع ما بيدوّر نفسه — بيتبع theta الجاي من القائد، وإلا بيصير
  // الدوران مضاعف ومرتجف
  if(autoRot && (!camSync || camLeader)){ sph.theta+=rotSpd; updateCam(); }
  stepCamTween();
  if(++lodAccum % 6 === 0) updateLOD();   // فحص المسافات مش كل إطار
  broadcastCam();
  renderer.render(scene,camera);
}

// ══ Boot ══
// 1) نهيّئ المحرك  2) لو في ?output_id بالرابط منجيب البيانات من الباك تلقائياً
//    وإلا منترك واجهة الرفع اليدوي شغّالة (fallback).
window.addEventListener('load', ()=>{
  initThree();
  try{
    const params = new URLSearchParams(location.search);
    const outputId = (params.get('output_id') || params.get('output') || '').trim();
    const token = params.get('token') || '';
    const side = params.get('side') || 'both';   // both | patient | control
    // وضع مدمج: لما العارض داخل صفحة المقارنة (شاشة مفردة)، نخفي التولبار
    // وبطاقة العنوان لأن صفحة المقارنة أصلاً بتعرض تسمية المريض/السليم.
    if(side==='patient' || side==='control'){
      document.documentElement.classList.add('embedded');
    }
    if(outputId){
      loadFromAPI(outputId, { token, side });
    } else {
      const sp=document.querySelector('#loading .spin'); if(sp) sp.style.display='none';
      const m=document.getElementById('load-msg');
      if(m) m.textContent='استورد ملف JSON للعرض، أو افتح العارض من صفحة التحليل.';
    }
  }catch(e){ console.error('[hic] boot error', e); }
});

// استقبال البيانات من صفحة المقارنة (compare_viewer.html) عبر postMessage.
// النوع 'chromo-load' يحمل {payload, side} — side: both|patient|control
window.addEventListener('message', (ev)=>{
  const d=ev.data;
  if(!d || !d.type) return;

  // ── تزامن الكاميرا ──
  if(d.type==='chromo-cam-init'){        // الصفحة الحاضنة بتفعّل التزامن
    camSync = !!d.sync;
    camLeader = !!d.leader;
    return;
  }
  if(d.type==='chromo-cam-yield'){       // شاشة تانية أخدت القيادة
    camLeader = false;
    return;
  }
  if(d.type==='chromo-ctl'){          // تحكّم موحّد من صفحة المقارنة
    const c=d.ctl||{};
    if(c.view)              switchMode(c.view);
    if(c.reset)             resetCam();
    if(c.rot!=null)       { autoRot=!!c.rot; }
    if(c.proteins!=null)  { showProteins=!!c.proteins;
                            showProteins?buildProteinMarkers():removeProteinMarkers(); }
    if(c.lod!=null)         lodEnabled=!!c.lod;
    if(c.repr)              setReprMode(c.repr);
    if(c.magnify!=null)     setProteinMagnify(c.magnify);
    return;
  }
  if(d.type==='chromo-protein-visibility'){ setProteinVisibility(d.hidden); return; }
  if(d.type==='chromo-protein-focus'){ focusProtein(d.protein||null); return; }
  if(d.type==='chromo-protein-filter'){ setProteinFilter(d.filter); return; }
  if(d.type==='chromo-cam'){             // حالة كاميرا من القائد
    if(!camSync || camLeader) return;    // القائد ما بيتبع حالو
    applyRemoteCam(d.cam);
    return;
  }

  if(d.type!=='chromo-load' || !d.payload) return;
  try{
    hideLoading();
    if(d.payload.patient || d.payload.control) applyDualData(d.payload, d.side||'both');
    else applyData(normalizeBackendPayload(d.payload));
  }catch(err){ console.error('[hic] message load failed', err); }
});