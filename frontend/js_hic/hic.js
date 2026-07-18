// ══ globals ══
let scene,camera,renderer;
let meshes={tube:null,glow:null,dots:null,bounds:null,rmsdTube:null};
let sph={theta:.4,phi:1.2,r:80},pan={x:0,y:0};
let drag=false,rDrag=false,prev={x:0,y:0};
let autoRot=true,rotSpd=.0002;
let clrMode='plasma',tubeR=.7;
let effects={glow:true,bounds:false,rmsd:false};
let rawPts=[],smoothPts=[],viewMode='smooth';
let globalData=null;
let raycaster,mouse;
let isoScene,isoCamera,isoRenderer,isoRunning=false;

// ══ Init ══
function initThree(){
  const c=document.getElementById('cv');
  scene=new THREE.Scene();
  scene.background=new THREE.Color(0x160A0D); // wine background
  scene.fog=new THREE.FogExp2(0x160A0D,.003);
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
  s.add(new THREE.AmbientLight(0x241016, 1.2)); // warm ambient light
  const dl=new THREE.DirectionalLight(0xEFE2D0, 2.2); // main key light (cream)
  dl.position.set(2,3,2); s.add(dl);
  const dl2=new THREE.DirectionalLight(0x818cf8, 0.8); // subtle blue rim light for contrast
  dl2.position.set(-2,-1,3); s.add(dl2);
  const dl3=new THREE.DirectionalLight(0xD8C6A8, 0.6); // taupe fill light from below
  dl3.position.set(0,-3,-1); s.add(dl3);
  const pl=new THREE.PointLight(0xD8C6A8, 0.5, 300);
  pl.position.set(0,0,0); s.add(pl);
}

function addStars(s){
  const g=new THREE.BufferGeometry(),pos=[];
  for(let i=0;i<1500;i++)
    pos.push((Math.random()-.5)*1500,(Math.random()-.5)*1500,(Math.random()-.5)*1500);
  g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  s.add(new THREE.Points(g,new THREE.PointsMaterial({color:0xD8C6A8,size:.3,transparent:true,opacity:.3}))); // dim taupe particles
}

// ══ Load JSON ══
function loadJSON(input){
  const file=input.files[0]; if(!file) return;
  document.getElementById('load-msg').textContent=tr('Analyzing and processing data...');
  document.getElementById('loading').style.display='flex';
  const reader=new FileReader();
  reader.onload=e=>{
    try{
      const d=JSON.parse(e.target.result);
      globalData=d;
      rawPts=d.coords_raw||[];
      smoothPts=d.coords_smooth||[];
      if(rawPts.length<2) throw new Error(tr('Not enough point data to render the structure'));

      // تحديث panel
      document.getElementById('p-chrom').textContent=d.chrom||'—';
      document.getElementById('p-start').textContent=d.start?(d.start/1e6).toFixed(2)+'M':'—';
      document.getElementById('p-end').textContent  =d.end  ?(d.end/1e6).toFixed(2)+'M'  :'—';
      document.getElementById('p-res').textContent  =d.resolution?(d.resolution/1000)+'kb':'—';
      document.getElementById('p-pts').textContent  =rawPts.length+' | '+smoothPts.length;
      document.getElementById('p-tads').textContent =(d.n_tads||'—')+tr(' regions');
      document.getElementById('hdr-info').textContent=
        `${d.chrom} ${(d.start/1e6).toFixed(1)}M → ${(d.end/1e6).toFixed(1)}M`;

      if(d.stress){
        const pct=Math.max(5,100-Math.log10(d.stress)*8);
        document.getElementById('stress-bar').style.width=pct+'%';
        document.getElementById('stress-val').textContent='Stress: '+d.stress.toFixed(2);
      }

      buildTADList(d);
      buildScene();
    }catch(err){alert(tr('File error: ')+err.message);console.error(err);}
    document.getElementById('loading').style.display='none';
  };
  reader.readAsText(file,'utf-8');
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
    const tColor = d.tad_colors[i] || '#D8C6A8'; 
    div.innerHTML=
      `<div class="tad-dot" style="background:${tColor}"></div>`+
      `<span class="tad-label">TAD ${i+1}</span>`+
      `<span class="tad-size">${pts.length}b · ${avgDen}%</span>`;
    div.onclick=()=>isolateTAD(i);
    container.appendChild(div);
  }
}

// ══ Build Scene ══
function buildScene(){
  clearMeshes();
  const pts=viewMode==='smooth'?smoothPts:rawPts;
  if(!pts||pts.length<2) return;

  const cx=pts.reduce((s,p)=>s+p.x,0)/pts.length;
  const cy=pts.reduce((s,p)=>s+p.y,0)/pts.length;
  const cz=pts.reduce((s,p)=>s+p.z,0)/pts.length;
  const v3=pts.map(p=>new THREE.Vector3(p.x-cx,p.y-cy,p.z-cz));
  const curve=new THREE.CatmullRomCurve3(v3,false,'catmullrom',.5);
  const segs=Math.min(v3.length*4,1800);

  // ── أنبوب رئيسي ──
  const geo=new THREE.TubeGeometry(curve,segs,tubeR,16,false);
  const cnt=geo.getAttribute('position').count;
  const cols=[];
  for(let i=0;i<cnt;i++){
    const t=i/cnt;
    const idx=Math.floor(t*(pts.length-1));
    const p=pts[idx]||pts[pts.length-1];
    const c=getClr(t,p.density||.5,p.tad_id||0,p.deviation||0);
    cols.push(c.r,c.g,c.b);
  }
  geo.setAttribute('color',new THREE.Float32BufferAttribute(cols,3));
  meshes.tube=new THREE.Mesh(geo,new THREE.MeshPhongMaterial(
    {vertexColors:true,shininess:130,specular:new THREE.Color(0x3A1820)}));
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
        {color:0xD8C6A8,size:4.5,transparent:true,opacity:.95,sizeAttenuation:true})); 
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
    const col=globalData?.tad_colors?.[p.tad_id||0]||'#D8C6A8';
    const rgb=hexToRgb(col);
    dc.push(rgb.r,rgb.g,rgb.b);
  });
  dg.setAttribute('position',new THREE.Float32BufferAttribute(dp,3));
  dg.setAttribute('color',new THREE.Float32BufferAttribute(dc,3));
  meshes.dots=new THREE.Points(dg,new THREE.PointsMaterial(
    {vertexColors:true,size:3,transparent:true,opacity:.7,sizeAttenuation:true}));
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
      const pal=globalData?.tad_colors||['#D8C6A8'];
      const hex=pal[tadId%pal.length]||'#D8C6A8';
      return new THREE.Color(hex);
    }
    default: return new THREE.Color(0xD8C6A8);
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
  const color=globalData.tad_colors?.[tadId]||'#D8C6A8';

  document.getElementById('iso-title').textContent=`TAD ${tadId+1}`;
  document.getElementById('iso-title').style.color=color;
  document.getElementById('iso-pts').textContent=pts.length+tr(' points');
  const avgDen=(pts.reduce((s,p)=>s+(p.density||0),0)/pts.length*100).toFixed(0);
  document.getElementById('iso-den').textContent=avgDen+tr('% density');

  overlay.classList.add('visible');

  await new Promise(r=>requestAnimationFrame(r));
  await new Promise(r=>setTimeout(r,30));

  isoRunning=false;
  await new Promise(r=>setTimeout(r,50));

  const freshCanvas=document.getElementById('isolate-canvas');
  const cw=freshCanvas.clientWidth||window.innerWidth-220;
  const ch=freshCanvas.clientHeight||window.innerHeight-52;

  isoScene=new THREE.Scene();
  isoScene.background=new THREE.Color(0x160A0D);
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
    const geo=new THREE.TubeGeometry(curve,v3.length*8,tubeR*1.4,16,false);
    const mat=new THREE.MeshPhongMaterial({color:new THREE.Color(color),shininess:160,
      specular:new THREE.Color(0x3A1820)});
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
    document.getElementById('iso-rot').textContent=tr('▶ Start rotation');
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
    isoRotBtn.textContent=isoAutoRot?tr('⏸ Stop rotation'):tr('▶ Start rotation');
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
}

// ══ Events ══
function setupEvents(c){
  renderer.domElement.addEventListener('mousedown',e=>{
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
    sph.r=Math.max(5,Math.min(500,sph.r+e.deltaY*.04));
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
    const reg=p.region||`${tr('Point ')}${idx}`;
    const den=p.density!=null?(p.density*100).toFixed(0)+'%':'—';
    const dev=p.deviation!=null?(p.deviation*100).toFixed(0)+'%':'—';
    const tadColor=globalData?.tad_colors?.[p.tad_id||0]||'#D8C6A8';
    const devNum=p.deviation||0;
    const devClass=devNum>.7?'warn':devNum>.4?'gold':'ok';

    tip.style.display='block';
    tip.style.left=(e.clientX+14)+'px';
    tip.style.top =(e.clientY-10)+'px';
    tip.innerHTML=
      `<strong style="color:var(--gold); font-family:var(--font-display); font-size:14px; letter-spacing:1px;">${reg}</strong><br>`+
      `<div style="height:1px; background:linear-gradient(90deg,var(--border),transparent); margin:6px 0;"></div>`+
      `<span style="color:var(--ivory-muted)">${tr('Group: ')}</span>`+
      `<span style="color:${tadColor}; font-weight:bold;">■ ${(p.tad_id||0)+1}</span>`+
      (p.is_boundary?` <span style="color:#fbbf24; font-size:10px;">${tr('(Boundary)')}</span>`:'')+`<br>`+
      `<span style="color:var(--ivory-muted)">${tr('Density: ')}</span><span style="color:${devNum>.5?'#e06060':'#6abf8a'}">${den}</span><br>`+
      `<span style="color:var(--ivory-muted)">${tr('Deviation: ')}</span><span class="${devClass}" style="color:${devNum>.7?'#e06060':devNum>.4?'#eab308':'#6abf8a'}">${dev}</span>`;

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
  if(autoRot){sph.theta+=rotSpd;updateCam();}
  renderer.render(scene,camera);
}

window.addEventListener('load',initThree);