/* ══════════ STATE ══════════ */
var API='/api/passport';
var S={photo:null,photos:[],uploaded:[],imgV:0,bulk:false,view:'photo',sheetUrl:null,pool:[],gender:'male',clothing:'keep_original',bg:'light_blue',bgType:'solid',gradient:null,bgc:null,tpl:'thai_passport',cw:null,ch:null,sid:null,cropPreset:'standard',customClothing:null,customClothingUrl:null,customClothingName:null};
var CD={male:[],female:[]},BD=[],TD=[];
var FLAGS={Thailand:'🇹🇭',Japan:'🇯🇵',China:'🇨🇳','South Korea':'🇰🇷','United States':'🇺🇸','United Kingdom':'🇬🇧','European Union':'🇪🇺',Canada:'🇨🇦',Australia:'🇦🇺',India:'🇮🇳',Singapore:'🇸🇬',Malaysia:'🇲🇾',Philippines:'🇵🇭',Indonesia:'🇮🇩',Vietnam:'🇻🇳',Cambodia:'🇰🇭',Laos:'🇱🇦',Myanmar:'🇲🇲','Hong Kong':'🇭🇰',France:'🇫🇷',Germany:'🇩🇪'};
var SOLID_COLORS=[
  {key:'light_blue',name:'Sky Blue',hex:'#C4DCFF'},
  {key:'white',name:'White',hex:'#FFFFFF'},
  {key:'light_gray',name:'Gray',hex:'#D1D5DB'},
  {key:'blue',name:'Blue',hex:'#2563EB'},
  {key:'red',name:'Red',hex:'#DC2626'},
  {key:'green',name:'Green',hex:'#16A34A'},
  {key:'dark_blue',name:'Navy',hex:'#1E3A5F'},
  {key:'custom',name:'Custom',hex:null}
];

/* ══════════ HELPERS (must be early!) ══════════ */
function $(id){return document.getElementById(id)}
function $$(sel){return document.querySelectorAll(sel)}
function bumpImg(){S.imgV++} // bump ONLY when a stored file is overwritten → new URL busts caches
function updatePoolUI(){
  var el=$('poolN');if(el)el.textContent=S.pool.length;
}
function setView(v){
  S.view=v;
  if(v==='sheet'){$('btnDl').textContent='⬇️ Download Sheet';$('btnDlT').classList.add('hidden');}
  else{$('btnDl').textContent='⬇️ Download';}
}

/* ══════════ INIT ══════════ */
window.addEventListener('DOMContentLoaded',function(){
  loadOptions();loadBgs();
  $('fi').addEventListener('change',handleFiles);
  $('drop').addEventListener('click',function(e){if(e.target.tagName!=='BUTTON')$('fi').click()});
  $('clFi').addEventListener('change',uploadClothingFile);
  $('drop').addEventListener('dragover',function(e){e.preventDefault();this.style.borderColor='#6366f1'});
  $('drop').addEventListener('dragleave',function(){this.style.borderColor=''});
  $('drop').addEventListener('drop',function(e){e.preventDefault();this.style.borderColor='';handleFiles({target:{files:e.dataTransfer.files}})});
  ['bgColor1','bgColor2','bgAngle'].forEach(function(id){
    var el=document.getElementById(id);
    if(el)el.addEventListener('input',function(){
      S.bgc='custom';S.bg='custom';S.bgGrad=null;
      $$('.bg-d').forEach(function(x){x.classList.remove('on')});
      var live=document.getElementById('liveBG');
      if(live&&live.checked)refreshBGPreview();
    });
  });
  loadCustomClothing();
});

/* ══════════ API HELPERS ══════════ */
async function api(path,body){
  var r=await fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok)throw new Error('API error: '+r.status);
  return r.json();
}

/* ══════════ TOAST ══════════ */
function toast(msg,cls){
  var t=$('toast');t.textContent=msg;t.className='toast show '+(cls||'');
  setTimeout(function(){t.className='toast'},2500);
}

/* ══════════ OVERLAY ══════════ */
function showOv(t,s){$('ovt').textContent=t||'Generating...';$('ovs').textContent=s||'';$('ov').classList.add('show')}
function hideOv(){$('ov').classList.remove('show')}

/* ══════════ OPTIONS DATA ══════════ */
async function loadOptions(){
  try{
    var r=await fetch(API+'/options');
    var d=await r.json();
    CD=d.clothing||{male:[],female:[]};
    BD=d.backgrounds||[];
    TD=d.templates||[];
    renderClothing();renderCountrySelect();
  }catch(e){console.error('loadOptions:',e)}
}
async function loadBgs(){
  try{
    var r=await fetch(API+'/backgrounds');
    var d=await r.json();
    var list=d.options||d.backgrounds||d.solid||[];
    var el=$('bgPresets');el.innerHTML='';
    list.forEach(function(b){
      var div=document.createElement('div');
      div.className='bg-d'+(S.bgc===b.key?' on':'');
      if(b.type==='gradient'&&b.css){
        div.style.background=b.css;
      }else{
        div.style.background=b.hex||'#ccc';
      }
      div.title=b.name;
      div.onclick=function(){S.bgc=b.key;S.bg=b.key;S.bgGrad=b.type==='gradient'?(b.hex+','+b.hex2):null;if(b.type==='gradient'){previewBGColor('linear-gradient(180deg,'+(b.hex||'#C4DCFF')+','+(b.hex2||'#FFFFFF')+')')}else{previewBGColor(b.hex)};$$('.bg-d').forEach(function(x){x.classList.remove('on')});div.classList.add('on')};
      el.appendChild(div);
    });
  }catch(e){console.error('loadBgs:',e)}
}

/* ══════════ CLOTHING ══════════ */
function renderClothing(){
  var list=CD[S.gender]||[];
  if(S.customClothingUrl){
    list=list.concat([{id:'custom',name:S.customClothingName||'My Outfit',image:S.customClothingUrl}]);
  }
  var el=$('cl');el.innerHTML='';
  list.forEach(function(c){
    var d=document.createElement('div');
    d.className='citem'+(S.clothing===c.key?' on':'');
    var imgPath=c.image||('img/clothing/'+S.gender+'/'+c.key+'.png');
    var imgHtml='<img src="'+imgPath+'" loading="lazy" alt="'+c.name+'" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'"><div style="width:100%;height:84px;display:none;align-items:center;justify-content:center;background:#f1f5f9;font-size:1.5rem">👔</div>';
    d.innerHTML=imgHtml+'<div class="lb">'+c.name+'</div><div class="ck">✓</div>';
    d.onclick=function(){S.clothing=c.key;$$('.citem').forEach(function(x){x.classList.remove('on')});d.classList.add('on');$('genBtn').disabled=false};
    el.appendChild(d);
  });
  // Gender tabs
  var gt=$('gt');gt.innerHTML='';
  [{k:'male',l:'👨 Male'},{k:'female',l:'👩 Female'}].forEach(function(g){
    var d=document.createElement('div');
    d.className='gtab'+(S.gender===g.k?' on':'');
    d.textContent=g.l;
    d.onclick=function(){S.gender=g.k;$$('.gtab').forEach(function(x){x.classList.remove('on')});d.classList.add('on');S.clothing='keep_original';renderClothing()};
    gt.appendChild(d);
  });
  $('genBtn').disabled=false;
}

function scrollCar(id,dir){
  var el=$(id);el.scrollBy({left:dir*120,behavior:'smooth'});
}

/* ══════════ COUNTRY SELECT (now in sec3) ══════════ */
function renderCountrySelect(){
  var sel=$('cs');if(!sel)return;sel.innerHTML='';
  var countries=[{value:'thai_passport',label:'🇹🇭 Thailand (35×45mm)'},{value:'japan_passport',label:'🇯🇵 Japan (35×45mm)'},{value:'china_passport',label:'🇨🇳 China (33×48mm)'},{value:'korea_passport',label:'🇰🇷 South Korea (35×45mm)'},{value:'us_visa',label:'🇺🇸 US Visa (51×51mm)'},{value:'uk_passport',label:'🇬🇧 UK (35×45mm)'},{value:'eu_passport',label:'🇪🇺 EU (35×45mm)'},{value:'custom',label:'✏️ Custom Size'}];
  countries.forEach(function(c){
    var o=document.createElement('option');
    o.value=c.value;o.textContent=c.label;
    if(c.value===S.tpl)o.selected=true;
    sel.appendChild(o);
  });
  sel.onchange=function(){
    S.tpl=this.value;
    var map={thai_passport:[35,45],japan_passport:[35,45],china_passport:[33,48],korea_passport:[35,45],us_visa:[51,51],uk_passport:[35,45],eu_passport:[35,45]};
    var sz=map[S.tpl]||[35,45];
    $('customW').value=sz[0];$('customH').value=sz[1];
    S.cw=sz[0];S.ch=sz[1];
  };
}

/* ══════════ CUSTOM CLOTHING ══════════ */
function removeCustomClothing(){
  S.customClothing=null;S.customClothingUrl=null;S.customClothingName=null;S.clothing='keep_original';
  localStorage.removeItem('passport_custom_clothing');
  $('custPreviewWrap').classList.add('hidden');
  renderClothing();
}

/* ══════════ CUSTOM CLOTHING UPLOAD ══════════ */
function pickClothing(){ $('clFi').click() }

async function uploadClothingFile(e){
  var file=e.target.files&&e.target.files[0];
  if(!file)return;
  if(file.size>10*1024*1024){toast('File too large (max 10MB)','err');return}
  showOv('Uploading outfit...');
  try{
    var fd=new FormData();fd.append('file',file);
    var r=await fetch(API+'/upload-clothing',{method:'POST',body:fd});
    var d=await r.json();
    if(!d.ok)throw new Error(d.detail||'Upload failed');
    // store as data URL for keep-alive across reload (server URL works too, but data URL survives session-only storage)
    var reader=new FileReader();
    reader.onload=function(ev){
      var dataUrl=ev.target.result;
      S.customClothing=d.clothing_id;
      S.customClothingUrl=dataUrl;
      S.customClothingName=file.filename;
      $('custPreviewWrap').classList.remove('hidden');
      $('custPreviewImg').src=dataUrl;
      $('custPreviewName').textContent=file.filename;
      localStorage.setItem('passport_custom_clothing',JSON.stringify({id:d.clothing_id,url:dataUrl,name:file.filename}));
      S.clothing='custom';$('genBtn').disabled=false;
      renderClothing();
      toast('Outfit uploaded ✓','ok');
    };
    reader.readAsDataURL(file);
  }catch(err){toast('Upload failed: '+err.message,'err');console.error(err)}
  finally{hideOv();e.target.value=''}
}

function loadCustomClothing(){
  var saved=localStorage.getItem('passport_custom_clothing');
  if(saved){
    try{
      var d=JSON.parse(saved);
      S.customClothing=d.id;S.customClothingUrl=d.url;S.customClothingName=d.name;
      $('custPreviewWrap').classList.remove('hidden');
      $('custPreviewImg').src=d.url;
      $('custPreviewName').textContent=d.name||'Custom';
      renderClothing();
    }catch(e){}
  }
}

/* ══════════ FILE UPLOAD ══════════ */
function pickFile(){$('fi').click()}

async function handleFiles(e){
  var files=Array.from(e.target.files||[]);
  if(!files.length)return;
  S.bulk=files.length>1;S.photos=[];
  S.fileName=S.bulk?(files.length+' photos'):files[0].name;
  $('upErr').classList.add('hidden');
  showOv('Uploading...');
  try{
    // first file = main session (single & bulk share the same path)
    var fd=new FormData();fd.append('file',files[0]);
    var r=await fetch(API+'/upload',{method:'POST',body:fd});
    var d=await r.json();
    if(!d.ok)throw new Error(d.detail||'Upload failed');
    S.sid=d.session_id;S.gender=d.gender||'male';
    // remaining files (bulk mode)
    for(var i=1;i<files.length;i++){
      var ffd=new FormData();ffd.append('file',files[i]);
      var rr=await fetch(API+'/upload',{method:'POST',body:ffd});
      var dd=await rr.json();
      if(dd.ok)S.photos.push({sid:dd.session_id,gender:dd.gender});
    }
    S.uploaded=[{sid:S.sid,gender:S.gender}].concat(S.photos);
    goOptions();
  }catch(err){
    $('upErr').textContent='Upload failed: '+err.message;$('upErr').classList.remove('hidden');
  }
  hideOv();
}

/* ══════════ NAVIGATION ══════════ */
function goOptions(){
  // uploaded-photo thumbnail card removed — preview box is now the single place that shows the photo
  $('sec1').classList.add('hidden');
  $('sec3').classList.remove('hidden');
  $('previewCard').classList.remove('hidden');
  renderUploadedPreview();
  if(S.uploaded.length>1){
    renderUploadStrip();
    $('genAllBtn').classList.remove('hidden');
    if(S.pool.indexOf(S.sid)<0){S.pool.push(S.sid);updatePoolUI();}
  }else{
    $('batchPreview').classList.add('hidden');
    $('genAllBtn').classList.add('hidden');
  }
  renderClothing();
  setTimeout(function(){$('sec3').scrollIntoView({behavior:'smooth',block:'start'})},200);
}

function renderUploadStrip(){
  // owner rule: bulk upload must show ALL uploaded photos here, click to switch active for manual edit
  $('batchPreview').classList.remove('hidden');
  var sh='';
  for(var i=0;i<S.uploaded.length;i++){
    var u=S.uploaded[i];
    sh+='<div class="slide-item'+(u.sid===S.sid?' active':'')+'" onclick="setActiveUpload(\''+u.sid+'\','+i+')">';
    sh+='<img src="'+API+'/download/'+u.sid+'_passport.jpg?size=sm&v='+S.imgV+'" loading="lazy">';
    sh+='<div style="font-size:.55rem;color:#64748b;margin-top:4px">'+(i+1)+'</div></div>';
  }
  $('sliderWrap').innerHTML=sh;
}

function setActiveUpload(sid,i){
  S.sid=sid;
  if(S.uploaded[i]&&S.uploaded[i].gender)S.gender=S.uploaded[i].gender;
  renderUploadedPreview();
  $$('.slide-item').forEach(function(el,idx){el.classList.toggle('active',idx===i)});
  renderClothing();
}

function renderUploadedPreview(){
  setView('photo');
  $('ri').src=API+'/download/'+S.sid+'_passport.jpg?v='+S.imgV;
  updatePreviewAspect(null);
  $('previewBg').style.background='';
  // no detail text under preview — that slot belongs to the batch thumbnail slider
  // downloads appear only after the first generation
  $('btnDl').classList.add('hidden');$('btnDlT').classList.add('hidden');
}

function newPhoto(){
  clearAll();
  window.scrollTo(0,0);
}

function clearAll(){
  S.photo=null;S.photos=[];S.uploaded=[];S.bulk=false;S.sid=null;S.customClothing=null;S.customClothingUrl=null;S.customClothingName=null;S.fileName=null;
  $('fi').value='';
  $('sec1').classList.remove('hidden');
  $('upErr').classList.add('hidden');
  $('sec3').classList.add('hidden');
  $('previewCard').classList.add('hidden');
  $('batchPreview').classList.add('hidden');
  $('genAllBtn').classList.add('hidden');
  $('custPreviewWrap').classList.add('hidden');
  $('genBtn').disabled=false;
  localStorage.removeItem('passport_custom_clothing');
}

/* ══════════ GENERATE ══════════ */
async function generate(){
  if(!S.sid)return;
  showOv('Generating passport photo...','AI processing your photo');
  try{
    var body={session_id:S.sid,clothing:S.clothing,gender:S.gender,bg:S.bgc||S.bg||'light_blue',template:S.tpl};
    if(S.cw)body.custom_width=S.cw;
    if(S.ch)body.custom_height=S.ch;
    if(S.cropPreset)body.crop_preset=S.cropPreset;
    var p=($('promptField')&&$('promptField').value||'').trim();
    if(p)body.prompt=p;
    if(S.customClothingUrl&&S.customClothingUrl.startsWith('data:')){
      body.custom_clothing_base64=S.customClothingUrl.split(',')[1];
    }

    // Generate = ACTIVE photo only (manual edit) — use ⚡ Generate ทั้งหมด for batch
    var d=await api('/generate',body);
    if(d.ok){
      showResult(d,false);
    }else{
      throw new Error(d.detail||'Generation failed');
    }
  }catch(e){
    toast('Error: '+e.message,'err');
    $('upErr').textContent='Error: '+e.message;
    $('upErr').classList.remove('hidden');
  }
  hideOv();
}

async function generateAll(){
  if(!S.uploaded||S.uploaded.length<2)return;
  showOv('Batch generating '+S.uploaded.length+' photos...','AI processing all uploaded photos');
  try{
    var body={session_id:S.sid,clothing:S.clothing,gender:S.gender,bg:S.bgc||S.bg||'light_blue',template:S.tpl};
    if(S.cw)body.custom_width=S.cw;
    if(S.ch)body.custom_height=S.ch;
    if(S.cropPreset)body.crop_preset=S.cropPreset;
    var p=($('promptField')&&$('promptField').value||'').trim();
    if(p)body.prompt=p;
    body.bulk_sessions=S.uploaded.map(function(u){return u.sid});
    var d=await api('/bulk-generate',body);
    if(d.ok){
      showResult(d,true);
    }else{
      throw new Error(d.detail||'Generation failed');
    }
  }catch(e){
    toast('Error: '+e.message,'err');
    $('upErr').textContent='Error: '+e.message;$('upErr').classList.remove('hidden');
  }
  hideOv();
}

function showResult(d,isBulk){
  // no detail rows under preview (owner) — thumbnails/results slider is the only thing below
  bumpImg();
  setView('photo');
  $('ri').src=API+'/download/'+S.sid+'_passport.jpg?v='+S.imgV;
  $('sec3').classList.remove('hidden');
  $('previewCard').classList.remove('hidden');
    // Owner flow: preview always square, full image, no forced crop
  updatePreviewAspect(null);
  $('btnDl').classList.remove('hidden');$('btnDlT').classList.remove('hidden');
  if(isBulk&&d.results&&d.results.length>1){
    S.pool=d.results.map(function(r){return r.session_id});
    updatePoolUI();
    $('batchPreview').classList.remove('hidden');
    var sh='';
    for(var i=0;i<d.results.length;i++){
      var res=d.results[i];
      if(!res.ok)continue;
      var imgUrl=(res.download_passport?location.origin+res.download_passport:API+'/download/'+res.session_id+'_passport.jpg')+'?size=sm&v='+S.imgV;
      sh+='<div class="slide-item" onclick="selectBatchResult(\''+res.session_id+'\','+i+')">';
      sh+='<img src="'+imgUrl+'" style="border-color:'+(res.session_id===S.sid?'#6366f1':'#334155')+'">';
      sh+='<div style="font-size:.55rem;color:#64748b;margin-top:4px">'+(i+1)+'</div></div>';
    }
    $('sliderWrap').innerHTML=sh;
  }else if(S.uploaded&&S.uploaded.length>1){
    // manual edit with multiple uploads — KEEP strip so other photos stay selectable
    renderUploadStrip();
    $('genAllBtn').classList.remove('hidden');
    if(S.pool.indexOf(S.sid)<0){S.pool.push(S.sid);updatePoolUI();}
  }else{
    $('batchPreview').classList.add('hidden');
  }
  autoRemoveBG();
  toast('Done! Photo ready 🎉');
}

function selectBatchResult(sid,i){
  S.sid=sid;setView('photo');
  $('ri').src=API+'/download/'+sid+'_passport.jpg?v='+S.imgV;
  $$('.slide-item').forEach(function(el,idx){
    el.querySelector('img').style.borderColor=idx===i?'#6366f1':'#334155';
  });
  autoRemoveBG();
}

/* ══════════ CUSTOM BG MODE (single / linear / radial) ══════════ */
var bgMode='single'; // 'single' | 'linear' | 'radial'
function setBGMode(m){
  bgMode=m;
  $$('.bgmode').forEach(function(x){x.classList.toggle('active',x.dataset.bgmode===m)});
  var g2=document.getElementById('bgColor2Wrap');
  var aw=document.getElementById('bgAngleWrap');
  var l1=document.getElementById('bgColor1Lbl');
  var l2=document.getElementById('bgColor2Lbl');
  if(m==='single'){
    g2.style.display='none';aw.style.display='none';
    l1.textContent='สี';
  }else if(m==='linear'){
    g2.style.display='flex';aw.style.display='flex';
    l1.textContent='สีที่ 1';l2.textContent='สีที่ 2';
  }else{ // radial
    g2.style.display='flex';aw.style.display='none';
    l1.textContent='กลาง';l2.textContent='ขอบ';
  }
  refreshBGPreview();
}

/* Build the color string sent to backend:
   single -> "#HEX"
   linear -> "linear-gradient(<angle>deg,#c1,#c2)"
   radial -> "radial-gradient(circle,#center,#edge)" */
function getBGColorString(){
  var c1=document.getElementById('bgColor1').value||'#C4DCFF';
  if(bgMode==='single')return c1;
  var c2=document.getElementById('bgColor2').value||'#FFFFFF';
  if(bgMode==='linear'){
    var ang=parseInt(document.getElementById('bgAngle').value)||180;
    return 'linear-gradient('+ang+'deg,'+c1+','+c2+')';
  }
  return 'radial-gradient(circle,'+c1+','+c2+')';
}

/* Live preview background (before applying to server) */
function refreshBGPreview(){
  var color=getBGColorString();
  var pb=document.getElementById('previewBg');
  if(pb)pb.style.background=gradCss(color);
}

/* Map our color string to a CSS background value for the preview div */
function gradCss(color){
  if(color&&color.indexOf('gradient')!==-1)return color;
  return color; // solid hex works as CSS color
}

/* ══════════ AUTO REMOVE BG ══════════ */
async function autoRemoveBG(){
  if(!S.sid)return;
  try{
    var color=getBGColorString();
    var resp=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
    var d=await resp.json();
    if(d.ok){
      bumpImg();
      var url=location.origin+(d.download_transparent||'');
      $('ri').src=url+'?v='+S.imgV+'&fmt=webp';
      refreshBGPreview();
      toast('✂️ Background removed');
    }
  }catch(e){console.error('autoRemoveBG:',e)}
}

/* ══════════ LIVE BG COLOR PREVIEW (kept for presets) ══════════ */
function previewBGColor(hex){
  var pb=document.getElementById('previewBg');
  if(pb)pb.style.background=hex||'transparent';
}

/* ══════════ APPLY BG ══════════ */
async function applyBG(){
  if(!S.sid)return;
  var color=getBGColorString();
  previewBGColor(color);
  try{
    var resp=await fetch(API+'/apply-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
    var d=await resp.json();
    if(d.ok){
      bumpImg();
      $('ri').src=location.origin+d.download_bg+'?v='+S.imgV+'&fmt=webp';
      $('previewBg').style.backgroundColor='transparent';
      toast('Background applied! 🎨','ok');
    }else{
      throw new Error((d&&(d.detail||d.error))||'apply-bg failed');
    }
  }catch(e){
    try{
      var resp2=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
      var d2=await resp2.json();
      if(d2.ok){
        bumpImg();
        $('ri').src=location.origin+d2.download_bg+'?v='+S.imgV+'&fmt=webp';
        $('previewBg').style.backgroundColor='transparent';
        toast('Background applied! 🎨','ok');
      }
    }catch(e2){toast('Apply BG failed','err')}
  }
}

/* ══════════ CROP ══════════ */
function setCrop(preset){
  S.cropPreset=preset;
  $$('.crop-opt').forEach(function(el){el.classList.toggle('active',el.dataset.preset===preset)});
}

/* ══════════ SIZE ══════════ */
function setCustomSize(w,h,el){
  S.cw=w;S.ch=h;
  $('customW').value=w;$('customH').value=h;
  $$('.sz-p').forEach(function(x){x.classList.remove('active')});
  if(el)el.classList.add('active');
}

async function applySize(){
  if(!S.sid)return;
  var w=parseInt($('customW').value)||35;
  var h=parseInt($('customH').value)||45;
  S.cw=w;S.ch=h;
  showOv('Resizing...');
  try{
    var d=await api('/recrop',{session_id:S.sid,custom_width:w,custom_height:h});
    if(d.ok){
      bumpImg();
      setView('photo');
      $('ri').src=location.origin+d.download_url+'?v='+S.imgV;
      updatePreviewAspect(w/h);
      toast('Size applied: '+w+'×'+h+'mm 📐','ok');
    }
  }catch(e){toast('Resize failed','err')}
  hideOv();
}

/* ══════════ PRINT SHEET ══════════ */
function switchOptTab(idx){
  for(var i=0;i<4;i++){
    var pane=$('optPane'+i);
    var tab=document.querySelectorAll('.opt-tab')[i];
    if(pane)pane.classList.toggle('act',i===idx);
    if(tab)tab.classList.toggle('active',i===idx);
  }
  // scroll preview into view on tab switch
  var box=$('previewBox');
  if(box)box.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function setPaper(type,el){
  S.paper=type;
  $$('.pap-p').forEach(function(x){x.classList.remove('active')});
  if(el)el.classList.add('active');
}

/* Print sheet is handled entirely on print.html (full settings UI).
   This step just hands off the generated session_ids so we avoid duplicate
   print logic living in two places. */
function genPrintSheet(){
  if(!S.sid)return;
  var sids=[S.sid];
  for(var i=0;i<S.pool.length;i++){if(sids.indexOf(S.pool[i])<0)sids.push(S.pool[i]);}
  window.location.href='print.html?session_ids='+sids.join(',');
}

/* ══════════ PREVIEW ASPECT (owner flow) ══════════ */
/* Preview always shows the square image full. When a size/ratio is chosen,
   we adapt the display ratio but the image stays unchanged (no re-gen). */
function updatePreviewAspect(ratio){
  var box=$('previewBox');
  if(!box)return;
  if(ratio && ratio>0){
    box.style.aspectRatio=ratio;
  }else{
    box.style.aspectRatio='1/1';
  }
  var bg=$('previewBg');
  if(bg){
    bg.style.width='100%';
    bg.style.height='100%';
    bg.style.aspectRatio=box.style.aspectRatio;
  }
}

/* ══════════ DOWNLOADS ══════════ */
function dl(type){
  var a=document.createElement('a');a.download='';document.body.appendChild(a);
  if(S.view==='sheet'&&S.sheetUrl){a.href=S.sheetUrl;}   // print sheet file
  else{
    if(!S.sid)return;
    a.href=API+'/download/'+S.sid+(type==='transparent'?'_transparent.png':'_passport.jpg');
  }
  a.click();document.body.removeChild(a);
}

function dlTransparent(){
  if(!S.sid)return;
  dl('transparent');
}
