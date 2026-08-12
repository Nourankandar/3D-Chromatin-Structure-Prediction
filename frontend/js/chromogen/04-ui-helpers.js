/* ============================================================
   3. TOASTS + DIALOGS
   ============================================================ */
function toast(msg, kind='success'){
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.innerHTML = `${kind==='error'?ICON.alert:ICON.check}<span>${esc(msg)}</span>`;
  document.getElementById('toasts').append(el);
  setTimeout(()=>{ el.style.opacity='0'; el.style.transition='opacity .2s'; setTimeout(()=>el.remove(),200); }, 3200);
}
function confirmDialog(title, desc){
  return new Promise(resolve=>{
    const dlg = document.getElementById('confirmDialog');
    document.getElementById('cfTitle').textContent = title;
    document.getElementById('cfDesc').textContent = desc;
    const ok = document.getElementById('cfOk');
    const done = v => { dlg.close(); ok.onclick=null; resolve(v); };
    ok.onclick = ()=>done(true);
    dlg.querySelector('[data-close]').onclick = ()=>done(false);
    dlg.oncancel = ()=>resolve(false);
    dlg.showModal();
  });
  
}
