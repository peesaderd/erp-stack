/* ══════════ STATE ══════════ */
var API='/api/passport';
var S={photo:null,photos:[],bulk:false,gender:'male',clothing:'keep_original',bg:'light_blue',bgType:'solid',gradient:null,bgc:null,tpl:'thai_passport',cw:null,ch:null,sid:null,cropPreset:'standard',customClothing:null,customClothingUrl:null,customClothingName:null,bgRemoved:false};
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

function $(id){return document.getElementById(id)}

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
    }else{toast('⚠️ Server connection failed','err')}
    if(!TD.length||(!CD.male.length&&!CD.female.length)){
      try{var m=await fetch(API+'/clothing?gender=male');var mj=await m.json();CD.male=mj.options||mj}catch(e){}
      try{var f=await fetch(API+'/clothing?gender=female');var fj=await f.json();CD.female=fj.options||fj}catch(e){}
      try{var b=await fetch(API+'/backgrounds');var bj=await b.json();BD=bj.options||bj}catch(e){}
      try{var t=await fetch(API+'/templates');var tj=await t.json();TD=tj.templates||tj}catch(e){}
    }
  }catch(e){console.error('Load data error:',e);toast('⚠️ Cannot connect to server','err')}
  renderGenderTabs();renderClothes();renderBG();
  renderCountryPills();renderSizeRow();
  if(TD.length){
    var found=TD.filter(function(t){return t.code==='thai_passport'});
    if(found.length){S.tpl='thai_passport'}
  }
}

/* ══════════ UPLOAD ══════════ */
function pickFile(multi){var fi=$('fi');fi.multiple=!!multi;fi.click()}
$('fi').addEventListener('change',function(e){handleFiles(e.target.files)});
$('drop').addEventListener('click',function(e){if(e.target.closest('button'))return;$('fi').click()});
$('drop').addEventListener('dragover',function(e){e.preventDefault();e.stopPropagation()});
$('drop').addEventListener('drop',function(e){e.preventDefault();e.stopPropagation();handleFiles(e.dataTransfer.files)});

function handleFiles(files){
  if(!files||!files.length)return;
  var a=[];for(var i=0;i<files.length;i++){if(files[i].type.startsWith('image/'))a.push(files[i])}
  if(!a.length){showErr('No valid images');return}
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
    var h='';for(var i=0;i<Math.min(8,S.photos.length);i++){
      h+='<div style="flex:0 0 44px;aspect-ratio:3/4;border-radius:5px;overflow:hidden;border:2px solid #e2e8f0"><img src="'+URL.createObjectURL(S.photos[i])+'" style="width:100%;height:100%;object-fit:cover"></div>';
    }
    if(S.photos.length>8)h+='<div style="flex:0 0 44px;aspect-ratio:3/4;border-radius:5px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:700;color:#94a3b8">+'+(S.photos.length-8)+'</div>';
    $('multiPreview').innerHTML=h;
  }else{$('multiPreview').innerHTML=''}
  // Show options card
  $('optionsCard').classList.remove('hidden');
  $('genBtn').disabled=false;
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
      $('upGender').style.display='inline-flex';
      $('upGender').textContent=(S.gender==='male'?'👨':'👩')+' '+S.gender+(d.confidence?(' · '+Math.round(d.confidence*100)+'%'):'');
      renderGenderTabs();renderClothes();
    }
  }catch(e){console.error('detectGender:',e)}
}

/* ══════════ CLOTHING ══════════ */
function renderGenderTabs(){
  $('gt').innerHTML='<button class="gtab'+(S.gender==='male'?' active':'')+'" onclick="setGender(\'male\')">👨 Men</button><button class="gtab'+(S.gender==='female'?' active':'')+'" onclick="setGender(\'female\')">👩 Women</button>';
}
function setGender(g){S.gender=g;S.clothing='keep_original';renderGenderTabs();renderClothes()}
function renderClothes(){
  var d=S.gender==='male'?CD.male:CD.female;
  if(!d||!d.length){$('cl').innerHTML='<div style="padding:12px;color:#94a3b8;font-size:.68rem">No data</div>';return}
  var h='<div class="citem'+(S.clothing==='keep_original'&&!S.customClothing?' on':'')+'" onclick="setClothes(\'keep_original\')" style="display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fafbff"><div style="font-size:18px;margin-top:14px">👕</div><div class="lb">Original</div><div class="ck">✓</div></div>';
  h+='<div class="citem'+(S.customClothing?' on':'')+'" onclick="pickCustomClothing()" style="border-style:dashed;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fafbff"><div style="font-size:18px;margin-top:14px">👚</div><div class="lb" style="color:#6366f1">เพิ่มชุด</div>';
  if(S.customClothing)h+='<img src="'+S.customClothingUrl+'" style="width:100%;height:50px;object-fit:cover;margin-top:auto">';
  h+='<div class="ck">✓</div></div>';
  for(var i=0;i<d.length;i++){
    var c=d[i];
    h+='<div class="citem'+(c.key===S.clothing?' on':'')+'" data-k="'+c.key+'" onclick="setClothes(\''+c.key+'\')">';
    h+='<img src="/img/clothing/'+S.gender+'/'+c.key+'.png" loading="lazy" onerror="this.style.background=\'#f1f5f9\'">';
    h+='<div class="lb">'+c.name+'</div><div class="ck">✓</div></div>';
  }
  $('cl').innerHTML=h;
}
function pickCustomClothing(){
  var inp=document.createElement('input');inp.type='file';inp.accept='image/jpeg,image/png';
  inp.onchange=function(){var f=inp.files&&inp.files[0];if(!f)return;S.customClothing=f;S.customClothingUrl=URL.createObjectURL(f);S.customClothingName=f.name;S.clothing='__custom__';renderClothes()};inp.click();
}
function setClothes(k){
  S.clothing=k;if(k==='__custom__'){pickCustomClothing();return}
  S.customClothing=null;S.customClothingUrl=null;
  renderClothes();
}

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
  S.bg=k;S.bgc=null;
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

/* ══════════ COUNTRY PILLS ══════════ */
function renderCountryPills(){
  var h='';
  for(var i=0;i<TD.length;i++){
    var t=TD[i],f=FLAGS[t.country]||'';
    h+='<div class="pill-item'+(t.code===S.tpl?' on':'')+'" data-code="'+t.code+'" onclick="selectCountry(\''+t.code+'\')">'+f+' '+t.name+' <small style="opacity:.6">'+t.width_mm+'×'+t.height_mm+'</small></div>';
  }
  $('countryPills').innerHTML=h;
}
function selectCountry(code){
  S.tpl=code;S.cw=null;S.ch=null;
  var items=$('countryPills').querySelectorAll('.pill-item');
  for(var i=0;i<items.length;i++)items[i].classList.toggle('on',items[i].dataset.code===code);
  // Re-generate with new size if we have a result
  if(S.sid)applyCountrySize();
}

/* ══════════ SIZE ROW ══════════ */
function renderSizeRow(){
  var sizes=[{l:'35×45',w:35,h:45},{l:'25×35',w:25,h:35},{l:'33×48',w:33,h:48},{l:'51×51',w:51,h:51},{l:'38×50',w:38,h:50}];
  var h='';
  for(var i=0;i<sizes.length;i++){
    var s=sizes[i];
    h+='<div class="sz-p'+(i===0?' active':'')+'" onclick="setCustomSize('+s.w+','+s.h+',this)">'+s.l+'</div>';
  }
  $('sizeRow').innerHTML=h;
}
function setCustomSize(w,h,btn){
  $('customW').value=w;$('customH').value=h;
  var all=document.querySelectorAll('#sizeRow .sz-p');
  for(var i=0;i<all.length;i++)all[i].classList.remove('active');
  if(btn)btn.classList.add('active');
}

/* ══════════ GENERATE ══════════ */
async function generate(){
  if(!S.photo){toast('Upload a photo first','err');return}
  if(S.bulk&&S.photos.length>1)return genBulk();
  showOv('Generating...','~10 seconds');
  try{
    var b=await toB64(S.photo);
    var body={image_base64:b,template_code:S.tpl,gender:S.gender,clothing:S.clothing,background:S.bg,strength:0.45,crop_preset:S.cropPreset,bg_type:'solid',print_size:'4x6',photo_count:6,border:'frame',blade_mode:false,gap_mm:2,border_color:'#FFFFFF',border_width_mm:0};
    if(S.bgc)body.background_color=S.bgc;
    if(S.cw&&S.ch){body.custom_width=S.cw;body.custom_height=S.ch}
    if(S.customClothing){body.custom_clothing_base64=await toB64(S.customClothing)}
    var r=await fetch(API+'/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){var t=await r.text();throw new Error('Server '+r.status+': '+t)}
    var d=await r.json();
    if(!d.ok)throw new Error(d.detail||d.error||'Failed');
    S.sid=d.session_id;
    showResult(d);
    // Auto cut BG → transparent
    autoRemoveBG();
  }catch(e){console.error('generate:',e);toast('Error: '+e.message,'err')}finally{hideOv()}
}

async function genBulk(){
  showOv('Generating '+S.photos.length+' photos...','~'+(S.photos.length*10)+'s');
  try{
    var imgs=[];for(var i=0;i<S.photos.length;i++)imgs.push(await toB64(S.photos[i]));
    var body={images:imgs,template_code:S.tpl,gender:S.gender,clothing:S.clothing,background:S.bg,strength:0.45,crop_preset:S.cropPreset,bg_type:'solid',print_size:'4x6',photo_count:6,border:'frame',blade_mode:false,gap_mm:2,border_color:'#FFFFFF',border_width_mm:0};
    if(S.bgc)body.background_color=S.bgc;
    if(S.cw&&S.ch){body.custom_width=S.cw;body.custom_height=S.ch}
    var r=await fetch(API+'/bulk-generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){var t=await r.text();throw new Error('Server '+r.status+': '+t)}
    var d=await r.json();
    if(!d.ok)throw new Error(d.detail||d.error||'Failed');
    S.bulkResults=d.results||[];
    S.sid=d.results&&d.results[0]?d.results[0].session_id:null;
    showResult(d,true);
    autoRemoveBG();
  }catch(e){console.error('genBulk:',e);toast('Error: '+e.message,'err')}finally{hideOv()}
}

function showResult(d,isBulk){
  var dt=d.dimensions_px||{};
  var stats='';
  stats+='<div style="text-align:center;padding:6px 10px;background:#f8fafc;border-radius:8px;min-width:50px"><div style="font-size:.78rem;font-weight:700">'+(d.time_seconds||'?')+'s</div><div style="font-size:.52rem;color:#94a3b8">Time</div></div>';
  stats+='<div style="text-align:center;padding:6px 10px;background:#f8fafc;border-radius:8px;min-width:50px"><div style="font-size:.78rem;font-weight:700">'+(dt.w||'?')+'×'+(dt.h||'?')+'</div><div style="font-size:.52rem;color:#94a3b8">px</div></div>';
  if(isBulk&&d.results){var ok=d.results.filter(function(r){return r.ok}).length;stats+='<div style="text-align:center;padding:6px 10px;background:#f8fafc;border-radius:8px;min-width:50px"><div style="font-size:.78rem;font-weight:700">'+ok+'/'+d.results.length+'</div><div style="font-size:.52rem;color:#94a3b8">Batch</div></div>'}
  $('resultStats').innerHTML=stats;
  // Show transparent placeholder first, will be replaced by autoRemoveBG
  $('previewImg').src=API+'/download/'+S.sid+'_passport.jpg?t='+Date.now();
  // Show all post-generate cards
  $('resultCard').classList.remove('hidden');
  $('countryCard').classList.remove('hidden');
  $('printCard').classList.remove('hidden');
  // Batch slider in result card
  if(isBulk&&d.results&&d.results.length>1){
    var sh='<div style="display:flex;gap:6px;overflow-x:auto;padding:8px 0;scrollbar-width:none">';
    for(var i=0;i<d.results.length;i++){var res=d.results[i];if(!res.ok)continue;var u=(res.download_passport?location.origin+res.download_passport:API+'/download/'+res.session_id+'_passport.jpg')+'?t='+Date.now();sh+='<div style="flex:0 0 60px;cursor:pointer;text-align:center" onclick="selectBatchResult(\''+res.session_id+'\','+i+')"><img src="'+u+'" style="width:60px;height:80px;object-fit:cover;border-radius:6px;border:2px solid '+(res.session_id===S.sid?'#6366f1':'#e2e8f0')+'"><div style="font-size:.5rem;color:#64748b">'+(i+1)+'</div></div>'}
    sh+='</div>';
    $('resultCard').insertAdjacentHTML('afterbegin',sh);
  }
  // Scroll to result
  setTimeout(function(){$('resultCard').scrollIntoView({behavior:'smooth',block:'start'})},200);
  toast('Done! 🎉');
}

/* ══════════ AUTO REMOVE BG ══════════ */
async function autoRemoveBG(){
  if(!S.sid)return;
  try{
    var color=$('bgColorPick').value||'#C4DCFF';
    var resp=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:color})});
    var d=await resp.json();
    if(d.ok){
      var url=location.origin+(d.download_transparent||d.download_bg)+'?t='+Date.now();
      $('previewImg').src=url;
      S.bgRemoved=true;
      // Update preview frame bg color to match selected
      $('previewFrame').style.background=color;
      toast('✂️ Background removed');
    }
  }catch(e){console.error('autoRemoveBG:',e)}
}

function selectBatchResult(sid,idx){
  S.sid=sid;
  $('previewImg').src=API+'/download/'+sid+'_passport.jpg?t='+Date.now();
  autoRemoveBG();
}

/* ══════════ APPLY SIZE ══════════ */
async function applySize(){
  if(!S.sid){toast('Generate first','err');return}
  var w=parseFloat($('customW').value),h=parseFloat($('customH').value);
  if(!w||!h||w<10||h<10){toast('Size 10–200mm','err');return}
  showOv('📐 Cropping '+w+'×'+h+'mm...','');
  try{
    var resp=await fetch(API+'/recrop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,template_code:'custom',target_w_mm:w,target_h_mm:h})});
    var d=await resp.json();
    if(d.ok){
      var url=location.origin+d.download_url+'?t='+Date.now();
      $('previewImg').src=url;
      toast('✅ '+w+'×'+h+'mm');
    }else{toast(d.error||'Crop failed','err')}
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

async function applyCountrySize(){
  // Called when country pill changes — recrop to new template size
  if(!S.sid)return;
  showOv('📐 Applying size...','');
  try{
    var resp=await fetch(API+'/recrop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,template_code:S.tpl})});
    var d=await resp.json();
    if(d.ok){
      var url=location.origin+d.download_url+'?t='+Date.now();
      $('previewImg').src=url;
      toast('✅ Size applied');
    }
  }catch(e){console.error('applyCountrySize:',e)}finally{hideOv()}
}

/* ══════════ PAPER ══════════ */
function setPaper(p,btn){
  var all=document.querySelectorAll('#printCard .sz-p');
  for(var i=0;i<all.length;i++)all[i].classList.remove('active');
  if(btn)btn.classList.add('active');
}

async function genPrintSheet(){
  if(!S.sid){toast('Generate first','err');return}
  var count=parseInt($('customCount').value)||6;
  var paperEl=document.querySelector('#printCard .sz-p.active');
  var paper=paperEl?paperEl.textContent.replace(/[^a-z0-9]/gi,'').toLowerCase():'4x6';
  if(paper.includes('4'))paper='4x6';else if(paper.includes('5'))paper='5x7';else if(paper==='a6')paper='a6';else if(paper==='a4')paper='a4';
  var w=parseFloat($('customW').value)||35,h=parseFloat($('customH').value)||45;
  var borderMm=parseFloat($('bwmmPrint').value)||0;
  showOv('🖨️ Print sheet...',count+' photos');
  try{
    var resp=await fetch(API+'/print-sheet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,print_size:paper,photo_size:'passport',photo_count:count,border:'frame',blade_mode:$('bmPrint').checked,gap_mm:2,border_color:'#FFFFFF',border_width_mm:borderMm})});
    var d=await resp.json();
    if(!d.ok){hideOv();toast('Print failed','err');return}
    var url=location.origin+d.download_url+'?t='+Date.now();
    $('custPreviewImg').src=url;
    $('custPreviewInfo').textContent='✅ '+(d.info&&d.info.count||count)+' photos on '+(d.info&&d.info.sheets||1)+' sheet(s)';
    $('printPreviewCard').classList.remove('hidden');
    toast('✅ Print sheet ready');
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

/* ══════════ DOWNLOAD ══════════ */
function dl(t){
  if(!S.sid)return;
  var a=document.createElement('a');
  if(t==='print'){a.href=API+'/download/'+S.sid+'_print.jpg';a.download='print_sheet.jpg'}
  else{a.href=API+'/download/'+S.sid+'_passport.jpg';a.download='passport.jpg'}
  a.click();
}
async function dlTransparent(){
  if(!S.sid){toast('Generate first','err');return}
  showOv('💎 Transparent PNG...','');
  try{
    var resp=await fetch(API+'/remove-bg',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:S.sid,background_color:'#FFFFFF'})});
    var d=await resp.json();
    if(!d.ok){hideOv();toast('Failed','err');return}
    var url=location.origin+d.download_transparent+'?t='+Date.now();
    var a=document.createElement('a');a.href=url;a.download='passport_transparent.png';a.click();
    toast('💎 Downloaded');
  }catch(e){toast('Error: '+e.message,'err')}finally{hideOv()}
}

/* ══════════ RESET ══════════ */
function newPhoto(){clearAll()}
function clearAll(){
  S.photo=null;S.photos=[];S.bulk=false;S.sid=null;S.customClothing=null;S.customClothingUrl=null;S.bgRemoved=false;
  $('fi').value='';
  $('drop').classList.remove('hidden');
  $('uploaded').classList.add('hidden');
  $('upErr').classList.add('hidden');
  $('optionsCard').classList.add('hidden');
  $('resultCard').classList.add('hidden');
  $('countryCard').classList.add('hidden');
  $('printCard').classList.add('hidden');
  $('printPreviewCard').classList.add('hidden');
  $('genBtn').disabled=true;
  window.scrollTo(0,0);
}

/* ══════════ UTILS ══════════ */
function toB64(f){return new Promise(function(res,rej){var r=new FileReader();r.onload=function(){res(r.result.split(',')[1])};r.onerror=rej;r.readAsDataURL(f)})}
function showOv(t,s){$('ovt').textContent=t;$('ovs').textContent=s||'';$('ov').classList.add('show')}
function hideOv(){$('ov').classList.remove('show')}
function showErr(m){var e=$('upErr');e.textContent=m;e.classList.remove('hidden')}
function hideErr(){$('upErr').classList.add('hidden')}
var tt;function toast(m,t){clearTimeout(tt);var e=$('toast');e.className='toast show '+(t||'');e.textContent=m;tt=setTimeout(function(){e.classList.remove('show')},3000)}

boot();
