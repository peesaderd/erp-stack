/* ══════════ STATE ══════════ */
var API='/api/passport';
var S={photo:null,photos:[],bulk:false,gender:'male',clothing:'keep_original',bg:'light_blue',bgType:'solid',gradient:null,bgc:null,tpl:'thai_passport',cw:null,ch:null,sid:null,cropPreset:'standard',customClothing:null,customClothingUrl:null,customClothingName:null};
var CD={male:[],female:[]},BD=[],TD=[];
var FLAGS={Thailand:'🇹🇭',Japan:'🇯🇵',China:'🇨🇳','South Korea':'🇰🇷','United States':'🇺🇸','United Kingdom':'🇬🇧','European Union':'🇪🇺',Canada:'🇨🇦',Australia:'🇦🇺',India:'🇮🇳',Singapore:'🇸🇬',Malaysia:'🇲🇾',Philippines:'🇵🇭',Indonesia:'🇮🇩',Vietnam:'🇻🇳',Cambodia:'🇰🇭',Laos:'🇱🇦',Myanmar:'🇲🇲','Hong Kong':'🇭🇰',France:'🇫🇷',Germany:'🇩🇪'};
var SOLID_COLORS=[
  {key:'light_blue',name:'Sky Blue',hex:'#C4DCFF'},
  {key:'white',name:'White',hex:'#FFFFFF'},
  {key:'light_gray',name:'Light Gray',hex:'#F0F0F0'},
  {key:'soft_blue',name:'Soft Blue',hex:'#B3D4FC'},
  {key:'mint',name:'Mint',hex:'#D4F5E9'},
  {key:'lavender',name:'Lavender',hex:'#E8D5F5'},
  {key:'cream',name:'Cream',hex:'#FFF8E7'},
  {key:'blush',name:'Blush',hex:'#FFE4E8'},
  {key:'warm_gray',name:'Warm Gray',hex:'#E8E4E0'}
];
var GRADIENTS=[
  {key:'grad_sky',name:'Sky',css:'linear-gradient(180deg,#89CFF0 0%,#C4DCFF 100%)'},
  {key:'grad_sunset',name:'Sunset',css:'linear-gradient(180deg,#FFB88C 0%,#FF8E72 100%)'},
  {key:'grad_forest',name:'Forest',css:'linear-gradient(180deg,#A8E6CF 0%,#7BC8A4 100%)'},
  {key:'grad_ocean',name:'Ocean',css:'linear-gradient(180deg,#667EEA 0%,#764BA2 100%)'},
  {key:'grad_peach',name:'Peach',css:'linear-gradient(180deg,#FFECD2 0%,#FCB69F 100%)'},
  {key:'grad_frost',name:'Frost',css:'linear-gradient(180deg,#E0EAFC 0%,#CFDEF3 100%)'},
  {key:'grad_rose',name:'Rose',css:'linear-gradient(180deg,#FAD0C4 0%,#FFD1FF 100%)'},
  {key:'grad_stone',name:'Stone',css:'linear-gradient(180deg,#D7DDE8 0%,#C4CCD8 100%)'}
];

function $(id){return document.getElementById(id)}

/* ══════════ TAB NAV ══════════ */
var currentTab=0;
function switchTab(i){
  if(i===1&&!S.photo){toast('Upload a photo first','err');return}
  currentTab=i;
  var panes=document.querySelectorAll('.pane');
  for(var p=0;p<panes.length;p++)panes[p].classList.remove('act');
  $('pane'+i).classList.add('act');
  var tabs=document.querySelectorAll('.pill-tab');
  for(var t=0;t<tabs.length;t++)tabs[t].classList.toggle('active',t===i);
  window.scrollTo(0,0);
}
function goOptions(){
  if(!S.photo){toast('Upload a photo first','err');return}
  $('tabOptions').classList.remove('disabled');
  switchTab(1);
  // Enable Generate if clothing is already selected (keep_original is default)
  if(S.clothing){$('genBtn').disabled=false}
}

/* ══════════ BOOT ══════════ */
async function boot(){
  try{
    var r=await fetch(API+'/options');
    if(r.ok){
      var j=await r.json();
      if(j.ok){
        TD=j.templates||[];
        CD.male=j.clothing&&j.clothing.male?j.clothing.male:[];
        CD.female=j.clothing&&j.clothing.female?j.clothing.female:[];
        BD=j.backgrounds||[];
      }
    }else{
      console.error('OPTIONS failed: HTTP',r.status);
      toast('⚠️ Server connection failed','err');
    }
    if(!TD.length||(!CD.male.length&&!CD.female.length)){
      try{var m=await fetch(API+'/clothing?gender=male');var mj=await m.json();CD.male=mj.options||mj}catch(e){}
      try{var f=await fetch(API+'/clothing?gender=female');var fj=await f.json();CD.female=fj.options||fj}catch(e){}
      try{var b=await fetch(API+'/backgrounds');var bj=await b.json();BD=bj.options||bj}catch(e){}
      try{var t=await fetch(API+'/templates');var tj=await t.json();TD=tj.templates||tj}catch(e){}
    }
  }catch(e){console.error('Load data error:',e);toast('⚠️ Cannot connect to server','err')}
  renderCountry();renderGenderTabs();renderClothes();renderBG();
  if(TD.length){
    var found=TD.filter(function(t){return t.code==='thai_passport'});
    if(found.length){S.tpl='thai_passport';$('cs').value='thai_passport'}
  }
}

/* ══════════ UPLOAD ══════════ */
function pickFile(){
  var fi=$('fi');
  fi.multiple=true;
  fi.click();
}
$('fi').addEventListener('change',function(e){handleFiles(e.target.files)});
$('drop').addEventListener('click',function(e){
  if(e.target.closest('button'))return;
  if(e.target.closest('.btn-p')||e.target.closest('.btn-c'))return;
  $('fi').click();
});
$('drop').addEventListener('dragover',function(e){e.preventDefault();e.stopPropagation()});
$('drop').addEventListener('drop',function(e){e.preventDefault();e.stopPropagation();handleFiles(e.dataTransfer.files)});

function handleFiles(files){
  if(!files||!files.length)return;
  var a=[];for(var i=0;i<files.length;i++){if(files[i].type.startsWith('image/'))a.push(files[i])}
  if(!a.length){showErr('No valid images found. Please upload JPG or PNG.');return}
  hideErr();
  if(a.length===1){S.photo=a[0];S.photos=[a[0]];S.bulk=false}
  else{S.photos=a.slice(0,20);S.photo=a[0];S.bulk=true}
  showUploaded();detectGender();
}

function showUploaded(){
  $('drop').classList.add('hidden');
  $('uploaded').classList.remove('hidden');
  $('upThumb').src=URL.createObjectURL(S.photo);
  $('upName').textContent=S.photo.name;
  $('upMeta').textContent=S.bulk?(S.photos.length+' photos · '+(S.photo.size/1024).toFixed(0)+' KB'):((S.photo.size/1024).toFixed(0)+' KB');
  $('upGender').style.display='none';
  if(S.photos.length>1){
    var h='';
    for(var i=0;i<Math.min(8,S.photos.length);i++){
      h+='<div style="flex:0 0 52px;aspect-ratio:3/4;border-radius:6px;overflow:hidden;border:2px solid #e2e8f0"><img src="'+URL.createObjectURL(S.photos[i])+'" style="width:100%;height:100%;object-fit:cover"></div>';
    }
    if(S.photos.length>8)h+='<div style="flex:0 0 52px;aspect-ratio:3/4;border-radius:6px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:.62rem;font-weight:700;color:#94a3b8">+'+(S.photos.length-8)+'</div>';
    $('multiPreview').innerHTML=h;
  }else{$('multiPreview').innerHTML=''}
}

async function detectGender(){
  if(!S.photo)return;
  try{
    var b=await toB64(S.photo);
    var fd=new FormData();fd.append('image_base64',b);
    var r=await fetch(API+'/detect-gender',{method:'POST',body:fd});
    var d=await r.json();
    if(d.ok&&d.gender&&d.gender!=='unknown'){
      S.gender=d.gender;
      S.clothing=S.gender==='male'?'keep_original':'keep_original';
      $('upGender').style.display='inline-flex';
      $('upGender').textContent=(S.gender==='male'?'👨':'👩')+' '+S.gender+(d.confidence?(' · '+Math.round(d.confidence*100)+'%'):'');
      renderGenderTabs();renderClothes();
    }
  }catch(e){console.error('detectGender:',e)}
}

/* ══════════ COUNTRY ══════════ */
function renderCountry(){
  var h='';
  for(var i=0;i<TD.length;i++){
    var t=TD[i],f=FLAGS[t.country]||'';
    h+='<option value="'+t.code+'"'+(t.code===S.tpl?' selected':'')+'>'+f+' '+t.name+' ('+t.width_mm+'×'+t.height_mm+'mm)</option>';
  }
  $('cs').innerHTML=h;
}
$('cs').addEventListener('change',function(){S.tpl=this.value;S.cw=null;S.ch=null});

/* ══════════ CLOTHING ══════════ */
function renderGenderTabs(){
  var h='<button class="gtab'+(S.gender==='male'?' active':'')+'" data-g="male" onclick="setGender(\'male\')">👨 Men</button>';
  h+='<button class="gtab'+(S.gender==='female'?' active':'')+'" data-g="female" onclick="setGender(\'female\')">👩 Women</button>';
  $('gt').innerHTML=h;
}
function setGender(g){
  S.gender=g;S.clothing='keep_original';
  renderGenderTabs();renderClothes();
  $('genBtn').disabled=false;
}
function renderClothes(){
  var d=S.gender==='male'?CD.male:CD.female;
  if(!d||!d.length){$('cl').innerHTML='<div style="padding:12px;color:#94a3b8;font-size:.72rem">No data</div>';return}
  var h='';
  // Custom clothing card
  h+='<div class="citem'+(S.customClothing?' on':'')+'" onclick="pickCustomClothing()" style="border-style:dashed;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fafbff">';
  h+='<div style="font-size:20px;color:#6366f1;margin-top:18px">👚</div>';
  h+='<div class="lb" style="color:#6366f1;font-weight:700">เพิ่มชุดเอง</div>';
  if(S.customClothing){h+='<img src="'+S.customClothingUrl+'" style="width:100%;height:60px;object-fit:cover;border-radius:0 0 8px 8px;margin-top:auto">'}
  h+='<div class="ck">✓</div></div>';
  for(var i=0;i<d.length;i++){
    var c=d[i];
    h+='<div class="citem'+(c.key===S.clothing?' on':'')+'" data-k="'+c.key+'" onclick="setClothes(\''+c.key+'\')">';
    h+='<img src="/img/clothing/'+S.gender+'/'+c.key+'.png" loading="lazy" onerror="this.style.background=\'#f1f5f9\'">';
    h+='<div class="lb">'+c.name+'</div>';
    h+='<div class="ck">✓</div></div>';
  }
  $('cl').innerHTML=h;
}
function pickCustomClothing(){
  var inp=document.createElement('input');
  inp.type='file';inp.accept='image/jpeg,image/png';
  inp.onchange=function(){
    var f=inp.files&&inp.files[0];if(!f)return;
    S.customClothing=f;S.customClothingUrl=URL.createObjectURL(f);S.customClothingName=f.name;
    S.clothing='__custom__';
    toast('👚 ใส่ชุดนี้ให้','');renderClothes();$('genBtn').disabled=false;
  };inp.click();
}
function setClothes(k){
  S.clothing=k;
  if(k==='__custom__'){pickCustomClothing();return}
  var items=$('cl').querySelectorAll('.citem');
  for(var j=0;j<items.length;j++)items[j].classList.remove('on');
  var el=$('cl').querySelector('.citem[data-k="'+k+'"]');
  if(el)el.classList.add('on');
  $('genBtn').disabled=false;
}
function scrollCar(id,dir){var el=$(id);if(!el)return;el.scrollBy({left:dir*160,behavior:'smooth'})}

/* ══════════ BACKGROUND ══════════ */
function renderBG(){
  var h='';
  for(var i=0;i<SOLID_COLORS.length;i++){
    var b=SOLID_COLORS[i];
    h+='<div class="bg-d'+(b.key===S.bg?' on':'')+'" style="background:'+(b.hex||'#ccc')+'" data-k="'+b.key+'" title="'+b.name+'" onclick="setBg(\''+b.key+'\')"></div>';
  }
  $('bgPresets').innerHTML=h;
}
function setBg(k){
  S.bg=k;S.bgc=null;S.gradient=null;
  var dots=$('bgPresets').querySelectorAll('.bg-d');
  for(var i=0;i<dots.length;i++)dots[i].classList.remove('on');
  var el=$('bgPresets').querySelector('.bg-d[data-k="'+k+'"]');
  if(el)el.classList.add('on');
}

/* ══════════ CROP ══════════ */
function setCrop(p){
  S.cropPreset=p;
  var opts=document.querySelectorAll('.crop-opt');
  for(var i=0;i<opts.length;i++)opts[i].classList.toggle('active',opts[i].dataset.preset===p);
}

/* ══════════ OPTION TABS ══════════ */
function switchOptTab(n){
  var tabs=document.querySelectorAll('.opt-tab');
  var panes=document.querySelectorAll('.opt-pane');
  for(var i=0;i<tabs.length;i++){
    tabs[i].classList.toggle('active',i===n);
    panes[i].classList.toggle('act',i===n);
  }
}

/* ══════════ GENERATE ══════════ */
async function generate(){
  if(!S.photo){toast('Please upload a photo first','err');return}
  if(S.bulk&&S.photos.length>1)return genBulk();
  showOv('Generating your passport photo...','This takes ~10 seconds');
  try{
    var b=await toB64(S.photo);
    var body={image_base64:b,template_code:S.tpl,gender:S.gender,clothing:S.clothing,background:S.bg,strength:0.45,crop_preset:S.cropPreset,bg_type:S.bgType||'solid',print_size:'4x6',photo_count:6,border:'frame',blade_mode:false,gap_mm:2,border_color:'#FFFFFF',border_width_mm:0};
    if(S.bgc)body.background_color=S.bgc;
    if(S.gradient)body.background_gradient=S.gradient;
    if(S.cw&&S.ch){body.custom_width=S.cw;body.custom_height=S.ch}
    if(S.customClothing){body.custom_clothing_base64=await toB64(S.customClothing)}
    var r=await fetch(API+'/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){var errText=await r.text();throw new Error('Server error '+r.status+': '+errText)}
    var d=await r.json();
    if(!d.ok)throw new Error(d.detail||d.error||'Generation failed');
    S.sid=d.session_id;
    showResult(d);
  }catch(e){console.error('generate error:',e);toast('Error: '+e.message,'err')}finally{hideOv()}
}

async function genBulk(){
  showOv('Generating '+S.photos.length+' photos...','This takes ~'+(S.photos.length*10)+' seconds');
  try{
    var imgs=[];for(var i=0;i<S.photos.length;i++)imgs.push(await toB64(S.photos[i]));
    var body={images:imgs,template_code:S.tpl,gender:S.gender,clothing:S.clothing,background:S.bg,strength:0.45,crop_preset:S.cropPreset,bg_type:S.bgType||'solid',print_size:'4x6',photo_count:6,border:'frame',blade_mode:false,gap_mm:2,border_color:'#FFFFFF',border_width_mm:0};
    if(S.bgc)body.background_color=S.bgc;
    if(S.gradient)body.background_gradient=S.gradient;
    if(S.cw&&S.ch){body.custom_width=S.cw;body.custom_height=S.ch}
    var r=await fetch(API+'/bulk-generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){var errText=await r.text();throw new Error('Server error '+r.status+': '+errText)}
    var d=await r.json();
    if(!d.ok)throw new Error(d.detail||d.error||'Generation failed');
    S.bulkResults=d.results||[];
    S.sid=d.results&&d.results[0]?d.results[0].session_id:null;
    if(S.sid)$('ri').src=API+'/download/'+S.sid+'_passport.jpg?t='+Date.now();
    showResult(d,true);
  }catch(e){console.error('genBulk error:',e);toast('Error: '+e.message,'err')}finally{hideOv()}
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
  $('ri').src=API+'/download/'+S.sid+'_cropped.jpg?t='+Date.now();
  $('sec2').classList.remove('hidden');
  // Build batch thumbnails below big preview
  if(isBulk&&d.results&&d.results.length>1){
    $('batchPreview').classList.remove('hidden');
    var sh='';
    for(var i=0;i<d.results.length;i++){
      var res=d.results[i];
      if(!res.ok)continue;
      var imgUrl=(res.download_passport?location.origin+res.download_passport:API+'/download/'+res.session_id+'_passport.jpg')+'?t='+Date.now();
      sh+='<div style="flex:0 0 60px;cursor:pointer;text-align:center" onclick="selectBatchResult(\''+res.session_id+'\','+i+')">';
      sh+='<img src="'+imgUrl+'" style="width:60px;height:80px;object-fit:cover;border-radius:8px;border:2px solid '+(res.session_id===S.sid?'#6366f1':'#334155')+';transition:.2s">';
      sh+='<div style="font-size:.5rem;color:#64748b;margin-top:2px">'+(i+1)+'</div></div>';
    }
    $('sliderWrap').innerHTML=sh;
  }else{
    $('batchPreview').classList.add('hidden');
  }
  // Scroll to section 2
  setTimeout(function(){var el=$('sec2');if(el)el.scrollIntoView({behavior:'smooth',block:'start'})},200);
  toast('Done! Photo ready 🎉');
}

function selectBatchResult(sid,idx){
  S.sid=sid;
  $('ri').src=API+'/download/'+sid+'_passport.jpg?t='+Date.now();
  // Highlight selected thumbnail
  var thumbs=$('sliderWrap').children;
  for(var i=0;i<thumbs.length;i++){
    var img=thumbs[i].querySelector('img');
    if(img)img.style.borderColor=i===idx?'#6366f1':'#334155';
  }
}

function selectBatchPhoto(idx){
  if(idx<0||idx>=S.photos.length)return;
  S.photo=S.photos[idx];
  // Also update S.sid to match this photo's result
  if(S.bulkResults&&S.bulkResults[idx]&&S.bulkResults[idx].ok){
    S.sid=S.bulkResults[idx].session_id;
    $('ri').src=API+'/download/'+S.sid+'_cropped.jpg?t='+Date.now();
  }
  var items=document.querySelectorAll('.slide-item');
  for(var i=0;i<items.length;i++)items[i].classList.toggle('active',i===idx);
}

function toggleSelectAll(checked){
  // placeholder for batch select all
}

/* ══════════ CUSTOMIZE ══════════ */
async function applyBG(){
  if(!S.sid){toast('Generate first','err');return}
  var color=$('bgColorPick').value||'#C4DCFF';
  var cutEnabled=$('cutBg').checked;
  showOv(cutEnabled?'✂️ Cutting BG + applying color...':'🎨 Applying color...',cutEnabled?'$0.0025':'free');
  try{
    var payload={session_id:S.sid,background_color:color};
    var resp=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    var d=await resp.json();
    if(!d.ok){hideOv();toast('BG remove failed','err');return}
    var url=location.origin+d.download_bg+'?t='+Date.now();
    $('ri').src=url;
    showCustPreview(url,'Color: '+color+(cutEnabled?' • BG cut':' • BG replaced'));
    toast('✅ BG updated');
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

function setCustomSize(w,h,btn){
  $('customW').value=w;$('customH').value=h;
  var all=document.querySelectorAll('.sz-p');
  for(var i=0;i<all.length;i++)all[i].classList.remove('active');
  if(btn)btn.classList.add('active');
}

async function applySize(){
  if(!S.sid){toast('Generate first','err');return}
  var w=parseFloat($('customW').value),h=parseFloat($('customH').value);
  if(!w||!h||w<10||h<10){toast('Size 10–200 mm','err');return}
  showOv('📐 Cropping to '+w+'×'+h+'mm...','cache hit');
  try{
    var resp=await fetch(API+'/recrop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,template_code:'custom',target_w_mm:w,target_h_mm:h})});
    var d=await resp.json();
    if(d.ok){
      var url=location.origin+d.download_url+'?t='+Date.now();
      $('ri').src=url;
      showCustPreview(url,'✅ Cropped: '+w+'×'+h+'mm');
      toast('✅ Size updated');
    }else{toast(d.error||'Crop failed','err')}
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

function setPaper(p,btn){
  var all=document.querySelectorAll('.pap-p');
  for(var i=0;i<all.length;i++)all[i].classList.remove('active');
  if(btn)btn.classList.add('active');
}

async function genPrintSheet(){
  if(!S.sid){toast('Generate first','err');return}
  var count=parseInt($('customCount').value)||6;
  var paper=document.querySelector('.pap-p.active');
  var paperVal=paper?paper.textContent.replace(/[^a-z0-9]/gi,'').toLowerCase():'4x6';
  if(paperVal.includes('4'))paperVal='4x6';else if(paperVal.includes('5'))paperVal='5x7';else if(paperVal.includes('a6'))paperVal='a6';else if(paperVal.includes('a4'))paperVal='a4';
  var w=parseFloat($('customW').value)||35,h=parseFloat($('customH').value)||45;
  var borderMm=parseFloat($('bwmmPrint').value)||0;
  var blade=$('bmPrint').checked;
  showOv('🖨️ Building print sheet...',count+' photos on '+paperVal);
  try{
    var resp=await fetch(API+'/print-sheet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,print_size:paperVal,photo_size:'passport',photo_count:count,border:'frame',blade_mode:blade,gap_mm:2.0,border_color:'#FFFFFF',border_width_mm:borderMm})});
    var d=await resp.json();
    if(!d.ok){hideOv();toast('Print sheet failed','err');return}
    var url=location.origin+d.download_url+'?t='+Date.now();
    showCustPreview(url,'✅ '+(d.info&&d.info.count||count)+' photos on '+(d.info&&d.info.sheets||1)+' sheet(s)');
    toast('✅ Print sheet ready');
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

function showCustPreview(url,info){
  $('custPreviewImg').src=url;
  $('custPreviewWrap').classList.remove('hidden');
  $('custPreviewInfo').textContent=info||'';
}

/* ══════════ DOWNLOAD ══════════ */
function dl(t){
  if(!S.sid)return;
  var a=document.createElement('a');
  if(t==='print'){a.href=API+'/download/'+S.sid+'_print.jpg';a.download='passport_print_sheet.jpg'}
  else{a.href=API+'/download/'+S.sid+'_passport.jpg';a.download='passport_photo.jpg'}
  a.click();
}

async function dlTransparent(){
  if(!S.sid){toast('Generate first','err');return}
  showOv('💎 Generating transparent PNG...','$0.0025');
  try{
    var resp=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:'#FFFFFF'})});
    var d=await resp.json();
    if(!d.ok){hideOv();toast('Failed to cut BG','err');return}
    var url=location.origin+d.download_transparent+'?t='+Date.now();
    var a=document.createElement('a');a.href=url;a.download='passport_'+S.sid+'_transparent.png';a.click();
    toast('💎 Transparent PNG downloaded');
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

function newPhoto(){clearAll()}
function clearAll(){
  S.photo=null;S.photos=[];S.bulk=false;S.sid=null;S.customClothing=null;S.customClothingUrl=null;S.customClothingName=null;
  $('fi').value='';
  $('drop').classList.remove('hidden');
  $('uploaded').classList.add('hidden');
  $('upErr').classList.add('hidden');
  $('sec2').classList.add('hidden');
  $('batchPreview').classList.add('hidden');
  $('custPreviewWrap').classList.add('hidden');
  $('genBtn').disabled=true;
  switchTab(0);
}

/* ══════════ UTILS ══════════ */
function toB64(f){return new Promise(function(res,rej){var r=new FileReader();r.onload=function(){res(r.result.split(',')[1])};r.onerror=rej;r.readAsDataURL(f)})}
function showOv(t,s){$('ovt').textContent=t;$('ovs').textContent=s||'';$('ov').classList.add('show')}
function hideOv(){$('ov').classList.remove('show')}
function showErr(m){var e=$('upErr');e.textContent=m;e.classList.remove('hidden')}
function hideErr(){$('upErr').classList.add('hidden')}
var tt;function toast(m,t){clearTimeout(tt);var e=$('toast');e.className='toast show '+(t||'');e.textContent=m;tt=setTimeout(function(){e.classList.remove('show')},3000)}

boot();
