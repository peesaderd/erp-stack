/* ══════════ STATE ══════════ */
var API='/api/passport';
var S={photo:null,photos:[],bulk:false,gender:'male',clothing:'keep_original',bg:'light_blue',bgType:'solid',gradient:null,bgc:null,tpl:'thai_passport',cw:null,ch:null,sid:null,cropPreset:'standard',customClothing:null,customClothingUrl:null,customClothingName:null};
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

/* ══════════ INIT ══════════ */
window.addEventListener('DOMContentLoaded',function(){
  loadOptions();loadBgs();
  $('fi').addEventListener('change',handleFiles);
  $('drop').addEventListener('click',function(e){if(e.target.tagName!=='BUTTON')$('fi').click()});
  $('drop').addEventListener('dragover',function(e){e.preventDefault();this.style.borderColor='#6366f1'});
  $('drop').addEventListener('dragleave',function(){this.style.borderColor=''});
  $('drop').addEventListener('drop',function(e){e.preventDefault();this.style.borderColor='';handleFiles({target:{files:e.dataTransfer.files}})});
  $('bgColorPick').addEventListener('input',function(){previewBGColor(this.value)});
  loadCustomClothing();
});

function $(id){return document.getElementById(id)}

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
    var d=await api('/options',{});
    CD=d.clothing||{male:[],female:[]};
    BD=d.backgrounds||[];
    TD=d.templates||[];
    renderClothing();renderCountrySelect();
  }catch(e){console.error('loadOptions:',e)}
}
async function loadBgs(){
  try{
    var d=await fetch(API+'/backgrounds').then(function(r){return r.json()});
    var el=$('bgPresets');el.innerHTML='';
    (d.backgrounds||d.solid||[]).forEach(function(b){
      if(b.type!=='solid')return;
      var div=document.createElement('div');
      div.className='bg-d'+(S.bgc===b.key?' on':'');
      div.style.background=b.hex;
      div.title=b.name;
      div.onclick=function(){S.bgc=b.key;S.bg=b.key;previewBGColor(b.hex);$$('.bg-d').forEach(function(x){x.classList.remove('on')});div.classList.add('on')};
      el.appendChild(div);
    });
  }catch(e){console.error('loadBgs:',e)}
}

/* ══════════ CLOTHING ══════════ */
function renderClothing(){
  var list=CD[S.gender]||[];
  // Add custom at end if exists
  if(S.customClothingUrl){
    list=list.concat([{id:'custom',name:S.customClothingName||'My Outfit',image:S.customClothingUrl}]);
  }
  var el=$('cl');el.innerHTML='';
  list.forEach(function(c){
    var d=document.createElement('div');
    d.className='citem'+(S.clothing===c.id?' on':'');
    d.innerHTML='<img src="'+c.image+'" loading="lazy" alt="'+c.name+'"><div class="lb">'+c.name+'</div><div class="ck">✓</div>';
    d.onclick=function(){S.clothing=c.id;$$('.citem').forEach(function(x){x.classList.remove('on')});d.classList.add('on');$('genBtn').disabled=false};
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
  // Enable gen button if clothing selected
  if(S.clothing&&S.clothing!=='keep_original')$('genBtn').disabled=false;
  else $('genBtn').disabled=false; // keep_original is valid
}

function scrollCar(id,dir){
  var el=$(id);el.scrollBy({left:dir*120,behavior:'smooth'});
}

function $$(sel){return document.querySelectorAll(sel)}

/* ══════════ COUNTRY SELECT ══════════ */
function renderCountrySelect(){
  var sel=$('cs');sel.innerHTML='';
  // Use BD (backgrounds with country info) or fallback
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

async function uploadCustomClothing(){
  var input=document.createElement('input');input.type='file';input.accept='image/*';
  input.onchange=async function(){
    var file=input.files[0];if(!file)return;
    var fd=new FormData();fd.append('file',file);
    try{
      showOv('Uploading...');
      var r=await fetch(API+'/upload-custom-clothing',{method:'POST',body:fd});
      var d=await r.json();
      if(d.ok){
        S.customClothing=d.id;S.customClothingUrl=API+'/download/'+d.id+'_custom.png';S.customClothingName=file.name.replace(/\.[^.]+$/,'');
        localStorage.setItem('passport_custom_clothing',JSON.stringify({id:d.id,url:S.customClothingUrl,name:S.customClothingName}));
        $('custPreviewWrap').classList.remove('hidden');
        $('custPreviewImg').src=S.customClothingUrl;
        $('custPreviewName').textContent=S.customClothingName;
        S.clothing=d.id;
        renderClothing();
        toast('Custom clothing uploaded! 👔','ok');
      }
    }catch(e){toast('Upload failed','err')}
    hideOv();
  };
  input.click();
}

function removeCustomClothing(){
  S.customClothing=null;S.customClothingUrl=null;S.customClothingName=null;S.clothing='keep_original';
  localStorage.removeItem('passport_custom_clothing');
  $('custPreviewWrap').classList.add('hidden');
  renderClothing();
}

/* ══════════ FILE UPLOAD ══════════ */
function pickFile(){$('fi').click()}

async function handleFiles(e){
  var files=Array.from(e.target.files||[]);
  if(!files.length)return;
  S.bulk=files.length>1;S.photos=[];

  if(S.bulk){
    $('drop').classList.add('hidden');$('uploaded').classList.remove('hidden');
    $('upName').textContent=files.length+' photos';
    $('upMeta').textContent='Batch mode';
    $('upErr').classList.add('hidden');
    // Show multi thumbnails
    var mp=$('multiPreview');mp.innerHTML='';
    files.forEach(function(f,i){
      var img=document.createElement('img');
      img.style.cssText='width:48px;height:64px;object-fit:cover;border-radius:6px;border:2px solid #e2e8f0';
      img.src=URL.createObjectURL(f);
      mp.appendChild(img);
    });
    // Upload first file for session
    var fd=new FormData();fd.append('file',files[0]);
    showOv('Uploading...');
    try{
      var r=await fetch(API+'/upload',{method:'POST',body:fd});
      var d=await r.json();
      if(d.ok){
        S.sid=d.session_id;S.gender=d.gender||'male';
        $('upThumb').src=API+'/download/'+S.sid+'_passport.jpg';
        $('upGender').textContent=(S.gender==='male'?'👨':'👩')+' '+S.gender;
        $('upGender').style.display='inline-flex';
        // Upload rest in background
        for(var i=1;i<files.length;i++){
          var ffd=new FormData();ffd.append('file',files[i]);
          var rr=await fetch(API+'/upload',{method:'POST',body:ffd});
          var dd=await rr.json();
          if(dd.ok)S.photos.push({sid:dd.session_id,gender:dd.gender});
        }
        goOptions();
      }
    }catch(err){$('upErr').textContent='Upload failed: '+err.message;$('upErr').classList.remove('hidden')}
    hideOv();
  }else{
    var file=files[0];
    $('drop').classList.add('hidden');$('uploaded').classList.remove('hidden');
    $('upName').textContent=file.name;
    $('upMeta').textContent=(file.size/1024).toFixed(0)+' KB';
    $('upErr').classList.add('hidden');
    $('upThumb').src=URL.createObjectURL(file);
    var fd=new FormData();fd.append('file',file);
    showOv('Uploading...');
    try{
      var r=await fetch(API+'/upload',{method:'POST',body:fd});
      var d=await r.json();
      if(d.ok){
        S.sid=d.session_id;S.gender=d.gender||'male';
        $('upThumb').src=API+'/download/'+S.sid+'_passport.jpg';
        $('upGender').textContent=(S.gender==='male'?'👨':'👩')+' '+S.gender;
        $('upGender').style.display='inline-flex';
        goOptions();
      }else{
        throw new Error(d.detail||'Upload failed');
      }
    }catch(err){$('upErr').textContent='Upload failed: '+err.message;$('upErr').classList.remove('hidden')}
    hideOv();
  }
}

/* ══════════ NAVIGATION ══════════ */
function goOptions(){
  $('sec2').classList.remove('hidden');
  renderClothing();
  setTimeout(function(){$('sec2').scrollIntoView({behavior:'smooth',block:'start'})},200);
}

function newPhoto(){
  clearAll();
  window.scrollTo(0,0);
}

function clearAll(){
  S.photo=null;S.photos=[];S.bulk=false;S.sid=null;S.customClothing=null;S.customClothingUrl=null;S.customClothingName=null;
  $('fi').value='';
  $('drop').classList.remove('hidden');
  $('uploaded').classList.add('hidden');
  $('upErr').classList.add('hidden');
  $('sec2').classList.add('hidden');
  $('sec3').classList.add('hidden');
  $('batchPreview').classList.add('hidden');
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

    if(S.bulk&&S.photos.length>0){
      body.bulk_sessions=[S.sid].concat(S.photos.map(function(p){return p.sid}));
      var d=await api('/bulk-generate',body);
    }else{
      var d=await api('/generate',body);
    }
    if(d.ok){
      showResult(d,S.bulk);
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

function showResult(d,isBulk){
  var dt=d.dimensions_px||{};
  var stats='';
  stats+='<div class="rst"><div class="v">'+(d.time_seconds||'?')+'s</div><div class="l">Time</div></div>';
  stats+='<div class="rst"><div class="v">'+(dt.w||'?')+'×'+(dt.h||'?')+'</div><div class="l">px</div></div>';
  stats+='<div class="rst"><div class="v">'+(d.gender==='male'?'👨':d.gender==='female'?'👩':'—')+'</div><div class="l">Gender</div></div>';
  if(isBulk&&d.results){
    var okCount=d.results.filter(function(r){return r.ok}).length;
    stats+='<div class="rst"><div class="v">'+okCount+'/'+d.results.length+'</div><div class="l">Batch</div></div>';
  }
  $('rs').innerHTML=stats;
  $('ri').src=API+'/download/'+S.sid+'_passport.jpg?t='+Date.now();
  // Show sec3, hide sec2
  $('sec3').classList.remove('hidden');
  // Batch thumbnails
  if(isBulk&&d.results&&d.results.length>1){
    $('batchPreview').classList.remove('hidden');
    var sh='';
    for(var i=0;i<d.results.length;i++){
      var res=d.results[i];
      if(!res.ok)continue;
      var imgUrl=(res.download_passport?location.origin+res.download_passport:API+'/download/'+res.session_id+'_passport.jpg')+'?t='+Date.now();
      sh+='<div class="slide-item" onclick="selectBatchResult(\''+res.session_id+'\','+i+')">';
      sh+='<img src="'+imgUrl+'" style="border-color:'+(res.session_id===S.sid?'#6366f1':'#334155')+'">';
      sh+='<div style="font-size:.55rem;color:#64748b;margin-top:4px">'+(i+1)+'</div></div>';
    }
    $('sliderWrap').innerHTML=sh;
  }else{
    $('batchPreview').classList.add('hidden');
  }
  // Auto cut BG
  autoRemoveBG();
  toast('Done! Photo ready 🎉');
}

function selectBatchResult(sid,i){
  S.sid=sid;
  $('ri').src=API+'/download/'+sid+'_passport.jpg?t='+Date.now();
  $$('.slide-item').forEach(function(el,idx){
    el.querySelector('img').style.borderColor=idx===i?'#6366f1':'#334155';
  });
  autoRemoveBG();
}

/* ══════════ AUTO REMOVE BG ══════════ */
async function autoRemoveBG(){
  if(!S.sid)return;
  try{
    var color=$('bgColorPick').value||'#C4DCFF';
    var resp=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
    var d=await resp.json();
    if(d.ok){
      // Show transparent + BG color overlay
      var url=location.origin+(d.download_transparent||'');
      $('ri').src=url+'?t='+Date.now();
      previewBGColor(color);
      toast('✂️ Background removed');
    }
  }catch(e){console.error('autoRemoveBG:',e)}
}

/* ══════════ LIVE BG COLOR PREVIEW ══════════ */
function previewBGColor(hex){
  $('previewBg').style.backgroundColor=hex;
  $('bgColorPick').value=hex;
}

/* ══════════ APPLY BG (FREE after first remove-bg) ══════════ */
async function applyBG(){
  if(!S.sid)return;
  var color=$('bgColorPick').value||'#FFFFFF';
  previewBGColor(color);
  // Call apply-bg (FREE — uses transparent PNG + PIL)
  try{
    var resp=await fetch(API+'/apply-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
    var d=await resp.json();
    if(d.ok){
      $('ri').src=location.origin+d.download_bg+'?t='+Date.now();
      $('previewBg').style.backgroundColor='transparent';
      toast('Background applied! 🎨','ok');
    }
  }catch(e){
    // Fallback to remove-bg
    try{
      var resp2=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
      var d2=await resp2.json();
      if(d2.ok){
        $('ri').src=location.origin+d2.download_bg+'?t='+Date.now();
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
      $('ri').src=API+'/download/'+S.sid+'_passport.jpg?t='+Date.now();
      toast('Size applied: '+w+'×'+h+'mm 📐','ok');
    }
  }catch(e){toast('Resize failed','err')}
  hideOv();
}

/* ══════════ PRINT SHEET ══════════ */
function setPaper(type,el){
  $$('.pap-p').forEach(function(x){x.classList.remove('active')});
  if(el)el.classList.add('active');
}

async function genPrintSheet(){
  if(!S.sid)return;
  showOv('Generating print sheet...');
  try{
    var body={
      session_id:S.sid,
      paper:$('.pap-p.active')?$('.pap-p.active').textContent.trim():'4x6"',
      count:parseInt($('customCount').value)||6,
      border_width_mm:parseFloat($('bwmmPrint').value)||3,
      blade_mode:$('bmPrint').checked
    };
    var r=await fetch(API+'/print-sheet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var d=await r.json();
    if(d.ok){
      var imgUrl=location.origin+'/api/passport/download/'+d.print_sheet_filename+'?t='+Date.now();
      $('custPreviewWrap2').classList.remove('hidden');
      $('custPreviewImg2').src=imgUrl;
      $('custPreviewInfo').textContent=d.photo_count+' photos on '+d.paper_size+' ('+d.dimensions_px.w+'×'+d.dimensions_px.h+'px)';
      toast('Print sheet ready! 🖨️','ok');
    }
  }catch(e){toast('Print sheet failed','err')}
  hideOv();
}

/* ══════════ DOWNLOADS ══════════ */
function dl(type){
  if(!S.sid)return;
  var url=API+'/download/'+S.sid+(type==='transparent'?'_transparent.png':'_passport.jpg');
  var a=document.createElement('a');a.href=url;a.download='';document.body.appendChild(a);a.click();document.body.removeChild(a);
}

function dlTransparent(){
  if(!S.sid)return;
  dl('transparent');
}
