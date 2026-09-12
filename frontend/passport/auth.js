// Shared auth: login button + account/payment/settings panel (index/gallery/print/order)
// NOTE: each page declares ids guestView/signedView/avatarBox/signedName/signedMeta for these to bind to.
(function(){
  var AUTH_BASE='/api/v1/auth';
  var AUTH_TOKEN_KEY='passport_token';
  var AUTH_USER_KEY='passport_user';

  function b64uDecode(s){
    s=s.replace(/-/g,'+').replace(/_/g,'/');
    while(s.length%4)s+='=';
    try{return decodeURIComponent(escape(atob(s)))}catch(e){return atob(s)}
  }
  function parseToken(t){
    try{var p=t.split('.');if(p.length<2)return null;return JSON.parse(b64uDecode(p[1]))}catch(e){return null}
  }
  function doLogin(provider){
    var ret=encodeURIComponent(window.location.pathname);
    window.location.href=AUTH_BASE+'/'+provider+'/login?return_to='+ret;
  }
  function doLogout(){
    try{localStorage.removeItem(AUTH_TOKEN_KEY);localStorage.removeItem(AUTH_USER_KEY);localStorage.removeItem('line_user_id')}catch(e){}
    var g=document.getElementById('guestView'),s=document.getElementById('signedView');
    if(g)g.style.display='';
    if(s)s.style.display='none';
    updateHdrUser();
    try{history.replaceState({},'',window.location.pathname)}catch(e){}
  }
  function applyUser(u,token){
    var nm=u&&u.name?u.name:(u&&u.email?u.email:'ผู้ใช้');
    var av=document.getElementById('avatarBox'),sn=document.getElementById('signedName'),sm=document.getElementById('signedMeta');
    if(av)av.textContent=nm.charAt(0).toUpperCase();
    if(sn)sn.textContent=nm;
    var meta=[];
    if(u&&u.email)meta.push(u.email);
    if(u&&u.line_user_id)meta.push('LINE: '+u.line_user_id.slice(0,8)+'…');
    if(u&&u.providers&&u.providers.length)meta.push(u.providers.map(function(p){return p.provider}).join(', '));
    if(sm)sm.textContent=meta.join(' · ');
    var g=document.getElementById('guestView'),s=document.getElementById('signedView');
    if(g)g.style.display='none';
    if(s)s.style.display='';
    if(u&&u.line_user_id){try{localStorage.setItem('line_user_id',u.line_user_id)}catch(e){}}
    try{localStorage.setItem(AUTH_TOKEN_KEY,token||'');localStorage.setItem(AUTH_USER_KEY,JSON.stringify(u||{}))}catch(e){}
    updateHdrUser();
  }
  function togglePanel(){
    var p=document.getElementById('acctPanel');
    if(!p)return;
    p.style.display=(p.style.display==='none')?'':'none';
  }
  function showAcctTab(tab){
    document.querySelectorAll('.acct-tab').forEach(function(b){b.classList.toggle('on',b.getAttribute('data-tab')===tab)});
    var map={login:'acctLogin',payment:'acctPayment',settings:'acctSettings'};
    var show=map[tab]||'acctLogin';
    for(var k in map){var el=document.getElementById(map[k]);if(el)el.style.display=(map[k]===show)?'':'none';}
  }
  function updateHdrUser(){
    var el=document.getElementById('hdrUserLabel');
    if(!el)return;
    var u=null;try{u=JSON.parse(localStorage.getItem(AUTH_USER_KEY)||'null')}catch(e){}
    if(u&&u.name)el.textContent=u.name.split(' ')[0];
    else if(u&&u.email)el.textContent=u.email.split('@')[0];
    else el.textContent='เข้าสู่ระบบ';
  }
  function saveSettings(){
    var s={name:val('setName'),phone:val('setPhone'),addr:val('setAddr'),province:val('setProvince'),zip:val('setZip')};
    try{localStorage.setItem('passport_settings',JSON.stringify(s))}catch(e){}
    fillFormFromSettings();
    var t=document.getElementById('toast');
    if(t){t.textContent='บันทึกที่อยู่เริ่มต้นแล้ว';t.classList.add('show');setTimeout(function(){t.classList.remove('show')},2200);}
  }
  function val(id){var e=document.getElementById(id);return e?e.value:''}
  function loadSettingsUI(){
    var s={};try{s=JSON.parse(localStorage.getItem('passport_settings')||'{}')}catch(e){}
    ['setName','setPhone','setAddr','setProvince','setZip'].forEach(function(id){var e=document.getElementById(id);if(e)e.value=s[id.slice(3).toLowerCase()]||'';});
    fillFormFromSettings();
  }
  function fillFormFromSettings(){
    var s={};try{s=JSON.parse(localStorage.getItem('passport_settings')||'{}')}catch(e){}
    var map={recipientName:'name',name:'name',phone:'phone',address:'addr',addr:'addr',province:'province',postal:'zip',zip:'zip'};
    for(var id in map){var e=document.getElementById(id);if(e&&!e.value&&s[map[id]])e.value=s[map[id]];}
  }
  function restoreSession(){
    var m=window.location.href.match(/[?&]token=([^&]+)/);
    if(m&&m[1]){
      try{localStorage.setItem(AUTH_TOKEN_KEY,m[1])}catch(e){}
      try{history.replaceState({},'',window.location.pathname)}catch(e){}
      fetch(AUTH_BASE+'/me',{headers:{'Authorization':'Bearer '+m[1]}})
        .then(function(r){return r.json()})
        .then(function(d){if(d.ok&&d.user)applyUser(d.user,m[1])})
        .catch(function(){});
      return;
    }
    var tok='';try{tok=localStorage.getItem(AUTH_TOKEN_KEY)||''}catch(e){}
    if(tok){
      fetch(AUTH_BASE+'/me',{headers:{'Authorization':'Bearer '+tok}})
        .then(function(r){return r.json()})
        .then(function(d){if(d.ok&&d.user)applyUser(d.user,tok)})
        .catch(function(){doLogout()});
    }
  }
  function setupPanelDismiss(){
    document.addEventListener('click',function(ev){
      var p=document.getElementById('acctPanel'),b=document.getElementById('hdrUserBtn');
      if(!p||p.style.display==='none')return;
      if((!p.contains(ev.target))&&(!b||!b.contains(ev.target)))p.style.display='none';
    });
  }
  // expose
  window.doLogin=doLogin;window.doLogout=doLogout;window.applyUser=applyUser;
  window.togglePanel=togglePanel;window.showAcctTab=showAcctTab;window.updateHdrUser=updateHdrUser;
  window.saveSettings=saveSettings;window.loadSettingsUI=loadSettingsUI;window.fillFormFromSettings=fillFormFromSettings;

  function init(){
    updateHdrUser();
    loadSettingsUI();
    restoreSession();
    setupPanelDismiss();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
  else init();
})();
