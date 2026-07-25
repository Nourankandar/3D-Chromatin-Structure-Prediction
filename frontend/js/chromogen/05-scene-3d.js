/* ============================================================
   4. خوارزمية الرسام لمعاينات الكروماتين/البروتين الصغيرة داخل البطاقات     
   ============================================================ */
const scenes = [];
const mulberry32 = a => () => { a|=0; a=a+0x6D2B79F5|0; let x=Math.imul(a^a>>>15,1|a); x=x+Math.imul(x^x>>>7,61|x)^x; return ((x^x>>>14)>>>0)/4294967296; };
const hashSeed = s => { let h=2166136261; for(const c of String(s)){h^=c.charCodeAt(0);h=Math.imul(h,16777619);} return h>>>0; };
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const hex2rgb = h => { const v=h.replace('#',''); return [parseInt(v.slice(0,2),16),parseInt(v.slice(2,4),16),parseInt(v.slice(4,6),16)]; };
const mix = (a,b,tt) => a.map((v,i)=>Math.round(v+(b[i]-v)*tt));
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;

/* حوّل أي لون CSS (hex / oklch / rgb / اسم) إلى [r,g,b] عبر رسمه على كانفس 1×1.
   يعمل مع oklch (متصفّحات حديثة)، ويرجع أخضر احتياطي لو اللون غير مدعوم. */
const _colCanvas = document.createElement('canvas'); _colCanvas.width = _colCanvas.height = 1;
const _colCtx = _colCanvas.getContext('2d', { willReadFrequently:true });
function resolveColor(v){
  _colCtx.fillStyle = '#8eb69b';
  try { if (v) _colCtx.fillStyle = v; } catch(e){}
  _colCtx.fillRect(0,0,1,1);
  const d = _colCtx.getImageData(0,0,1,1).data;
  return [d[0], d[1], d[2]];
}


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
    items.sort((a,b)=>b.z-a.z);   

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

/** اللولب الثنائي */
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
