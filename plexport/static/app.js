const icons={grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',film:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4m10-8h4m-4 8h4"/>',settings:'<path d="M9 3h6l1 4 4 1 1 6-4 2-2 4H9l-1-4-4-1-1-6 4-2z"/><circle cx="12" cy="12" r="3"/>',route:'<circle cx="5" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h9a4 4 0 0 1 0 8H8a3 3 0 0 0 0 6h9"/>',plus:'<path d="M12 5v14M5 12h14"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',check:'<path d="m5 12 4 4L19 6"/>',layers:'<path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 11 3 3 5-5"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',link:'<path d="m9 15 6-6m-7 5-2 2a3 3 0 0 0 4 4l4-4a3 3 0 0 0 0-4m2-2 2-2a3 3 0 0 0-4-4l-4 4a3 3 0 0 0 0 4"/>',refresh:'<path d="M20 9a8 8 0 0 0-14-4L3 8m0-5v5h5m-4 7a8 8 0 0 0 14 4l3-3m0 5v-5h-5"/>',tv:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 22h8M9 2l3 3 3-3"/>'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.film}</svg>`;
function hydrate(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let settings=null,status={jobs:[],checks:{},configured_sources:0},results=[],currentPage='overview',sourceDraft=[],pollBusy=false,toastTimer,searchKind='movie',preflightGeneration=0;
const pages={overview:'Overzicht',search:'Ontdekken',downloads:'Downloads',library:'Bibliotheek',settings:'Instellingen'};
async function api(path,data){const response=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-PlexPort':'1',...(data===undefined?{}:{'Content-Type':'application/json'})},...(data===undefined?{}:{body:JSON.stringify(data)})});if(response.status===401){window.location.replace('/login'+window.location.hash);throw Error('Meld je opnieuw aan bij PlexPort.');}const body=await response.json();if(!response.ok)throw Error(body.error||body.message||'Verzoek mislukt.');return body;}
function toast(message,error=false){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').className=error?'error':'';$('#toast').hidden=false;toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
function navigate(page,updateHash=true){if(!pages[page])page='overview';currentPage=page;document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!=='page-'+page);document.querySelectorAll('nav button').forEach(el=>el.classList.toggle('active',el.dataset.page===page));$('#breadcrumb').textContent=pages[page];if(updateHash)history.replaceState(null,'','#'+page);window.scrollTo({top:0});}
const bytes=n=>{if(!n)return'0 B';const units=['B','KB','MB','GB','TB'];const i=Math.min(4,Math.floor(Math.log(n)/Math.log(1024)));return(n/1024**i).toFixed(i>1?1:0)+' '+units[i];};
const eta=n=>n<0||n>8640000?'Tijd onbekend':n<60?'Minder dan een minuut':n<3600?Math.ceil(n/60)+' min':Math.floor(n/3600)+' u '+Math.ceil(n%3600/60)+' min';
function empty(name,title,description,button=''){return`<div class="empty"><span>${icon(name)}</span><h3>${esc(title)}</h3><p>${esc(description)}</p>${button}</div>`;}
function jobRow(job,library=false){const labels={queued:'In wachtrij',downloading:job.paused?'Gepauzeerd':activityLabel(job.activity),importing:'Importeren',scan_pending:'Plex-scan aanvragen',done:'Geïmporteerd',stopped:'Gestopt',error:'Aandacht nodig'};let details='';const imported=job.files_imported?.length>0;if(library||imported){details=`<p class="file-path">${esc(job.scan_requested?'Plex-scan aangevraagd':job.state==='scan_pending'?'Plex-scan volgt':job.state==='error'?'Plex-scan niet gelukt':'In je mediamap · automatisch scannen instellen in Plex')}<br>${(job.files_imported||[]).slice(0,3).map(esc).join('<br>')}${job.files_imported?.length>3?'<br>+ '+(job.files_imported.length-3)+' bestanden':''}</p>`;}else if(job.state!=='error'){details=`<div class="progress-track" role="progressbar" aria-label="Downloadvoortgang" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(Math.max(0,Math.min(1,job.progress))*100)}"><div data-progress="${Math.round(Math.max(0,Math.min(1,job.progress))*100)}"></div></div><div class="progress-caption"><span>${Math.round(job.progress*100)}%${job.speed?' · '+bytes(job.speed)+'/s':''}</span><span>${job.state==='downloading'&&!job.paused&&(!job.activity||job.activity==='downloading')?eta(job.eta):''}</span></div>`;}const actions=(job.state==='stopped'?`<button data-action="resume" data-id="${esc(job.id)}">Hervatten</button>`:`<button data-action="stop" data-id="${esc(job.id)}">Stoppen</button>`)+(job.state==='error'?`<button data-action="retry" data-id="${esc(job.id)}">Opnieuw proberen</button>`:'')+`<button class="danger-text" data-action="remove" data-id="${esc(job.id)}">Verwijderen</button>`;return`<article class="job-row"><span class="job-type">${icon(job.kind==='tv'?'tv':'film')}</span><div class="job-body"><div class="job-top"><div class="job-title">${esc(job.title)}${job.year?' ('+esc(job.year)+')':''}</div><span class="status-pill ${job.state==='done'?'good':job.state==='error'?'bad':''}">${labels[job.state]||esc(job.state)}</span></div><div class="job-meta">${job.kind==='tv'?'Serie':'Film'} · ${esc(job.source)} · ${new Date(job.created*1000).toLocaleDateString('nl-BE',{day:'numeric',month:'short'})}</div>${details}${job.state==='downloading'&&!job.paused&&activityNote(job.activity)?`<p class="hint activity-note">${esc(activityNote(job.activity))}</p>`:''}${job.error?`<div class="job-error">${esc(job.error)}</div>`:''}${actions?'<div class="job-actions">'+actions+'</div>':''}</div></article>`;}
function renderStatus(){const jobs=status.jobs,active=jobs.filter(j=>!['done','error','stopped'].includes(j.state)).length;$('#stat-active').textContent=active;$('#nav-count').textContent=active;$('#stat-done').textContent=jobs.filter(j=>j.files_imported?.length).length;$('#stat-sources').textContent=status.configured_sources;const noJobs=empty('download','Nog even rustig hier.','Voeg je eerste download toe. Wij houden de route naar je bibliotheek in de gaten.','<button class="secondary" data-add>Je eerste download toevoegen '+icon('plus')+'</button>');$('#recent-jobs').innerHTML=jobs.length?jobs.slice(0,3).map(j=>jobRow(j)).join(''):noJobs;renderDownloads(noJobs);renderSetup();const imported=jobs.filter(j=>j.files_imported?.length);$('#library-jobs').innerHTML=imported.length?imported.map(j=>jobRow(j,true)).join(''):empty('film','Nog geen imports.','Je voltooide downloads verschijnen hier zodra ze in je mediamappen zijn geplaatst.');const connections=[['downloader',settings?.downloader.type==='qbittorrent'?'qBittorrent':'Transmission','Torrent-downloader','download'],['plex','Plex Media Server','Automatische bibliotheekscan','film'],['storage','Mediamappen','Download- en Plex-bestemming','layers']];$('#connection-list').innerHTML=connections.map(([key,title,subtitle,name])=>{const check=status.checks[key];return`<div class="connection-row"><span class="connection-icon">${icon(name)}</span><div><b>${title}</b><small>${subtitle}</small></div><span class="status-pill ${check?(check.ok?'good':'bad'):''}" title="${esc(check?.message||'Test de verbinding bij Instellingen')}">${check?(check.ok?'Getest':'Controleer'):'Niet getest'}</span></div>`;}).join('');renderProgress();}
async function refresh(){if(pollBusy)return;pollBusy=true;try{status=await api('status');$('#logout-button').hidden=status.authentication!=='session';renderStatus();}catch(e){$('#connection-list').innerHTML=`<div class="warning">De verbinding met PlexPort is verbroken. ${esc(e.message)}</div>`;}finally{pollBusy=false;}}
function removeDialog(id){
  const job=status.jobs.find(item=>item.id===id);
  if(!job)return;
  const form=$('#remove-form');form.reset();form.dataset.id=id;
  $('#remove-title').textContent=job.title;
  $('#remove-error').textContent='';updateRemoveChoice();
  $('#remove-dialog').showModal();$('#remove-cancel').focus();
}
function updateRemoveChoice(){
  const forget=$('#remove-scope').value==='forget';
  $('#remove-files-choice').hidden=forget;
  if(forget)$('#remove-files').checked=false;
  $('#remove-explanation').textContent=forget?'Je haalt alleen de taak uit PlexPort. De torrent en bestanden blijven in je downloader; downloaden of delen kan daar doorgaan. PlexPort zal deze taak niet meer importeren.':'De taak verdwijnt uit PlexPort en de torrent wordt uit je downloader verwijderd. Downloadbestanden blijven behouden, tenzij je hieronder kiest om ze ook te wissen.';
}
$('#remove-scope').addEventListener('change',updateRemoveChoice);
for(const selector of ['#remove-cancel','#remove-close'])$(selector).addEventListener('click',()=>$('#remove-dialog').close());
$('#remove-dialog').addEventListener('cancel',event=>{if($('#remove-submit').disabled)event.preventDefault();});
$('#remove-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const form=event.target,button=$('#remove-submit');
  const controls=[button,$('#remove-cancel'),$('#remove-close'),$('#remove-scope'),$('#remove-files')];
  const data={id:form.dataset.id,action:'remove',delete_files:$('#remove-files').checked,forget:$('#remove-scope').value==='forget'};
  controls.forEach(control=>control.disabled=true);$('#remove-error').textContent='';
  try{
    const result=await api('action',data);
    $('#remove-dialog').close();
    toast(result.forgotten?'Taak uit de lijst gehaald. Je downloader blijft ongewijzigd.':result.files_deleted?'Taak en downloadbestanden verwijderd. Media in je Plex-map blijven behouden.':'Taak en torrent verwijderd. De bestanden blijven behouden.');
    await refresh();
  }catch(error){$('#remove-error').textContent=error.message;}
  finally{controls.forEach(control=>control.disabled=false);}
});
function populateSettings(){Object.entries(settings).forEach(([group,values])=>{if(group==='sources')return;Object.entries(values).forEach(([key,value])=>{const input=$(`[name="${group}.${key}"]`);if(input)input.value=value;if(key.endsWith('_set')){const secret=$(`[name="${group}.${key.slice(0,-4)}"]`);if(secret)secret.placeholder=value?'Opgeslagen · leeg laten om te behouden':'Optioneel';}});});sourceDraft=settings.sources.map(s=>({...s}));renderSources();downloaderHint();}
function captureSources(){sourceDraft=[...document.querySelectorAll('.source-row')].map(row=>{const existing=sourceDraft.find(s=>s.id===row.dataset.id)||{};const draft={id:row.dataset.id,type:existing.type||'torznab',name:row.querySelector('[data-source="name"]').value,url:row.querySelector('[data-source="url"]').value,api_key_set:existing.api_key_set};const secret=row.querySelector('[data-source="api_key"]').value;if(secret)draft.api_key=secret;else if(existing.api_key)draft.api_key=existing.api_key;return draft;});}
function renderSources(){const element=$('#source-fields');element.innerHTML=sourceDraft.length?sourceDraft.map(s=>{const direct=s.type==='watchsomuch';return`<div class="source-row" data-id="${esc(s.id)}"><label>Naam<input data-source="name" value="${esc(s.name)}" placeholder="Mijn bron" required></label><label>${direct?'Website':'Torznab-URL'}<input data-source="url" value="${esc(s.url)}" type="url" placeholder="http://server:9696/1/api" ${direct?'readonly':''} required></label><label>${direct?'Rechtstreeks gekoppeld':'API-sleutel'}<input data-source="api_key" type="password" value="${esc(s.api_key||'')}" placeholder="${direct?'Geen API-sleutel nodig':s.api_key_set?'Opgeslagen':'API-sleutel'}" ${direct?'disabled':''} autocomplete="new-password"></label><button type="button" class="icon-button" data-remove-source="${esc(s.id)}" aria-label="Bron verwijderen">×</button></div>`;}).join(''):'<p class="hint">Nog geen bronnen gekoppeld. Je kunt ook rechtstreeks een magnetlink of torrentbestand toevoegen.</p>';}

function collectSettings(){captureSources();const data={downloader:{},library:{},plex:{},sources:sourceDraft.map(s=>{const {api_key_set,...rest}=s;return rest;})};new FormData($('#settings-form')).forEach((value,name)=>{const [group,key]=name.split('.');if(!group||!key)return;if(['password','token'].includes(key)&&!value)return;data[group][key]=value;});return data;}
async function saveSettings(){if(!$('#settings-form').reportValidity())throw Error('Vul de instellingen volledig in.');const payload=collectSettings();settings=await api('settings',payload);status.checks={};status.configured_sources=settings.sources.length;populateSettings();renderStatus();$('#save-status').textContent='Opgeslagen op dit apparaat.';return settings;}
async function saveWithFeedback(){const button=$('#save-top');button.disabled=true;try{await saveSettings();toast('Je instellingen zijn opgeslagen.');}catch(e){toast(e.message,true);}finally{button.disabled=false;}}
function addDialog(result=null){const form=$('#add-form');form.reset();$('#add-error').textContent='';form.elements.kind.value=result?.kind||'movie';form.elements.title.value=result?.library_title||result?.title||'';form.elements.year.value=result?.year||'';form.elements.season.value=result?.season||'';form.elements.episode.value=result?.episode||'';form.elements.link.value=result?.link||'';form.dataset.source=result?.source||'Handmatig';form.dataset.expectedBytes=String(result?.size||0);updateKind();$('#add-dialog').showModal();checkDownload();setTimeout(()=>form.elements.title.focus(),20);}
function updateKind(){const tv=$('#add-form').elements.kind.value==='tv';$('#episode-fields').hidden=!tv;$('#tv-hint').hidden=!tv;}
async function fileBase64(file){if(file.size>8*1024*1024)throw Error('Torrentbestand te groot. Maximaal 8 MB.');const bytes=new Uint8Array(await file.arrayBuffer());let text='';for(let i=0;i<bytes.length;i+=32768)text+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(text);}
function downloaderHint(){const form=$('#settings-form'),qb=form.elements['downloader.type'].value==='qbittorrent';form.elements['downloader.url'].placeholder=qb?'http://NAS-adres:8080':'http://transmission:9091/transmission/rpc';}

function activityLabel(activity){
  return {queued:'Wacht op een vrije plek',checking:'Bestanden controleren',metadata:'Download voorbereiden',waiting:'Wacht op delers',moving:'Bestanden verplaatsen',allocating:'Ruimte voorbereiden',paused:'Gepauzeerd',seeding:'Download klaar',unknown:'Status wordt opgehaald'}[activity]||'Downloaden';
}
function activityNote(activity){
  return {queued:'Je downloader laat deze taak starten zodra er plaats is.',checking:'Je downloader controleert de bestanden. PlexPort wacht tot die controle klaar is.',metadata:'De bestandsinformatie wordt opgehaald. Daarna verschijnt de downloadvoortgang.',waiting:'Er komt nu geen data binnen. Dit kan tijdelijk zijn. Blijft het zo, controleer je downloader of kies een andere versie.',moving:'Je downloader verplaatst de bestanden. PlexPort importeert ze pas als dit klaar is.'}[activity]||'';
}
function renderProgress(){document.querySelectorAll('.progress-track > [data-progress]').forEach(bar=>{bar.style.width=bar.dataset.progress+'%';});}
function renderDownloads(noJobs=''){
  const query=$('#download-query').value.trim().toLocaleLowerCase('nl');
  const filter=$('#download-filter').value;
  const jobs=status.jobs.filter(job=>job.title.toLocaleLowerCase('nl').includes(query)
    &&(filter==='all'||filter==='active'&&!['done','error','stopped'].includes(job.state)
      ||filter==='stopped'&&job.state==='stopped'||filter==='error'&&job.state==='error'||filter==='done'&&job.files_imported?.length));
  $('#download-count').textContent=`${jobs.length} van ${status.jobs.length} downloads`;
  $('#all-jobs').innerHTML=jobs.length?jobs.map(job=>jobRow(job)).join(''):status.jobs.length?empty('search','Geen downloads in deze selectie.','Pas de naam of het filter aan.'):noJobs||empty('download','Nog geen downloads.','Voeg een link of torrentbestand toe.');
  renderProgress();
}
function renderSetup(){
  if(!settings)return;
  const checks=status.checks;
  const rows=[
    [checks.downloader?.ok===true,'1 · Verbind je downloader',checks.downloader?.message||'Vul het adres van qBittorrent of Transmission in en test de verbinding.'],
    [checks.storage?.ok===true,'2 · Controleer je mappen',checks.storage?.message||'Kies de downloadmap en de bestemming voor films en series.'],
    [status.configured_sources>0,'3 · Kies je zoekbronnen',status.configured_sources?`${status.configured_sources} bron(nen) toegevoegd. Je kunt nu een titel zoeken.`:'Voeg een zoekbron toe, of gebruik zelf een link of torrentbestand.']
  ];
  $('#setup-checklist').innerHTML=rows.map(([ok,title,message])=>`<button class="setup-step ${ok?'complete':''}" data-goto="settings"><span>${icon(ok?'check':'arrow')}</span><div><b>${esc(title)}</b><small>${esc(message)}</small></div></button>`).join('');
  $('#setup-title').textContent=checks.downloader?.ok&&checks.storage?.ok?'Je downloadroute is gecontroleerd':'Klaar voor je eerste download?';
}
function renderResults(){
  const rows=PlexPortDiscovery.select(results,{quality:$('#filter-quality').value,maxGB:$('#filter-size').value,minSeeders:$('#filter-seeders').value,source:$('#filter-source').value,sort:$('#filter-sort').value});
  const qualityNames={'1080':'Full HD','720':'HD','2160':'4K','sd':'Standaardbeeld','unknown':'Kwaliteit niet vermeld'};
  $('#search-results').innerHTML=`<div class="result-heading">${rows.length} van ${results.length} versies</div>`+(rows.length?rows.map(r=>`<article class="result-row"><span class="job-type">${icon(searchKind==='tv'?'tv':'film')}</span><div class="job-body"><div class="result-title">${esc(r.title)}</div><div class="result-meta"><span class="quality-badge">${qualityNames[r.quality]}</span><span>${esc(r.source)}</span><span>${r.size?bytes(r.size):'Grootte onbekend'}</span><span>${Number(r.seeders||0)} delers</span></div></div><button class="primary" data-result="${r.index}">${icon('download')}Kiezen</button></article>`).join(''):empty('search','Geen versie past bij deze keuze.','Probeer een andere kwaliteit of een grotere maximale bestandsgrootte.','<button class="secondary" id="empty-reset">Alle versies tonen</button>'));
}
function resetFilters(){for(const [id,value]of [['quality','all'],['size','0'],['seeders','0'],['source','all'],['sort','seeders']])$('#filter-'+id).value=value;if(results.length)renderResults();}
function folderResults(report){
  return report.folders.map(folder=>`<div class="folder-check"><span class="status-pill ${folder.ok?'good':'bad'}">${folder.ok?'✓':'!'}</span><div><b>${esc(folder.label)}</b><small>${esc(folder.message)}${folder.free!==null?' · '+bytes(folder.free)+' vrij':''}</small></div></div>`).join('');
}
async function checkDownload(){
  const generation=++preflightGeneration;
  const form=$('#add-form');$('#download-preflight').textContent='Mappen en vrije ruimte controleren…';
  try{
    const report=await api('preflight',{kind:form.elements.kind.value,expected_bytes:Number(form.dataset.expectedBytes||0)});
    if(generation!==preflightGeneration)return;
    $('#download-preflight').innerHTML=`<h3>Voor je start${report.expected_bytes?' · '+bytes(report.expected_bytes):''}</h3>${folderResults(report)}${report.warnings.map(message=>`<p class="hint">${esc(message)}</p>`).join('')}<p class="hint">${esc(report.note)}</p>`;
  }catch(error){if(generation===preflightGeneration)$('#download-preflight').textContent=error.message;}
}
async function checkAll(){
  const button=$('#check-all');button.disabled=true;$('#check-all-result').textContent='Instellingen opslaan…';
  try{
    await saveSettings();
    const targets=['downloader','storage',...(settings.plex.url&&settings.plex.token_set?['plex']:[])];
    const rows=[];
    for(const target of targets){
      $('#check-all-result').innerHTML=rows.join('')+`<p class="hint">${target==='storage'?'Mappen':target==='plex'?'Plex':'Downloader'} controleren…</p>`;
      try{const report=await api('test',{target});rows.push(`<div class="notice">${esc(report.message)}</div>`);if(report.folders)rows.push(folderResults(report));}
      catch(error){rows.push(`<div class="warning">${esc(error.message)}</div>`);}
    }
    if(!targets.includes('plex'))rows.push('<p class="hint">Automatisch scannen via Plex is niet ingesteld. PlexPort kan wel bestanden in je mediamappen plaatsen.</p>');
    $('#check-all-result').innerHTML=rows.join('');await refresh();
  }catch(error){$('#check-all-result').innerHTML=`<div class="warning">${esc(error.message)}</div>`;}
  finally{button.disabled=false;}
}
hydrate();navigate(location.hash.slice(1),false);
$('#logout-button').addEventListener('click',async()=>{try{const response=await fetch('/auth/logout',{method:'POST',headers:{'X-PlexPort':'1','Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error('Afmelden is niet gelukt. Probeer opnieuw.');window.location.replace('/login');}catch(error){toast(error.message,true);}});
$('#check-all').addEventListener('click',checkAll);$('#reset-filters').addEventListener('click',resetFilters);document.addEventListener('click',event=>{if(event.target.closest('#empty-reset'))resetFilters();});for(const id of ['quality','size','seeders','source','sort'])$('#filter-'+id).addEventListener('change',renderResults);$('#download-query').addEventListener('input',()=>renderDownloads());$('#download-filter').addEventListener('change',()=>renderDownloads());
$('#theme-choice').value=window.PlexPortTheme.preference;
$('#theme-choice').addEventListener('change',event=>window.PlexPortTheme.set(event.target.value));
$('#settings-form').elements['downloader.type'].addEventListener('change',downloaderHint);
document.addEventListener('click',async event=>{const button=event.target.closest('button');if(!button)return;if(button.dataset.page)navigate(button.dataset.page);if(button.dataset.goto)navigate(button.dataset.goto);if(button.hasAttribute('data-add'))addDialog();if(button.dataset.removeSource){captureSources();sourceDraft=sourceDraft.filter(s=>s.id!==button.dataset.removeSource);renderSources();}if(button.dataset.result!==undefined){const selected=results[Number(button.dataset.result)];addDialog({...selected,kind:searchKind});}if(button.dataset.action==='remove'){removeDialog(button.dataset.id);return;}if(button.dataset.action){button.disabled=true;try{await api('action',{id:button.dataset.id,action:button.dataset.action});toast(button.dataset.action==='stop'?'Download gestopt. Je kunt hem later hervatten.':button.dataset.action==='resume'?'Download hervat.':'Download wordt opnieuw geprobeerd.');await refresh();}catch(e){toast(e.message,true);}finally{button.disabled=false;}}if(button.dataset.test){button.disabled=true;const target=button.dataset.test,display=$('#test-'+target);display.textContent='Verbinding controleren…';display.classList.remove('error');try{await saveSettings();const result=await api('test',{target});display.textContent=result.message+(result.sections?' · '+result.sections.map(s=>s.id+': '+s.title+' ('+s.type+')').join(' · '):'')+(result.free?' · '+bytes(result.free)+' vrij':'');await refresh();}catch(e){display.textContent=e.message;display.classList.add('error');await refresh();}finally{button.disabled=false;}}});
$('#save-top').addEventListener('click',saveWithFeedback);$('#settings-form').addEventListener('submit',e=>{e.preventDefault();saveWithFeedback();});$('#add-source').addEventListener('click',()=>{captureSources();sourceDraft.push({id:crypto.getRandomValues(new Uint8Array(16)).reduce((id,byte)=>id+byte.toString(16).padStart(2,'0'),''),name:'',url:''});renderSources();$('#source-fields').lastElementChild.querySelector('input').focus();});
$('#add-watchsomuch').addEventListener('click',()=>{captureSources();if(sourceDraft.some(s=>s.type==='watchsomuch')){toast('WatchSoMuch is al toegevoegd.');return;}sourceDraft.push({id:crypto.getRandomValues(new Uint8Array(16)).reduce((id,byte)=>id+byte.toString(16).padStart(2,'0'),''),type:'watchsomuch',name:'WatchSoMuch',url:'https://watchsomuch.to'});renderSources();});
$('#close-dialog').addEventListener('click',()=>$('#add-dialog').close());$('#cancel-dialog').addEventListener('click',()=>$('#add-dialog').close());$('#add-form').addEventListener('change',event=>{if(event.target.name==='kind'){updateKind();checkDownload();}});$('#add-form').elements.link.addEventListener('input',()=>{$('#add-form').dataset.expectedBytes='0';});$('#add-form').elements.link.addEventListener('change',checkDownload);$('#add-form').elements.torrent.addEventListener('change',event=>{if(event.target.files.length){$('#add-form').elements.link.value='';$('#add-form').dataset.expectedBytes='0';checkDownload();}});
$('#add-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.target,button=$('#add-submit');button.disabled=true;$('#add-error').textContent='';try{const data=Object.fromEntries(new FormData(form));delete data.torrent;data.source=form.dataset.source;data.expected_bytes=Number(form.dataset.expectedBytes||0);if(form.elements.torrent.files[0]){data.metainfo=await fileBase64(form.elements.torrent.files[0]);data.link='';}await api('jobs',data);$('#add-dialog').close();toast('Download toegevoegd. Je kunt de voortgang hier volgen.');navigate('downloads');await refresh();}catch(e){$('#add-error').textContent=e.message;}finally{button.disabled=false;}});
$('#search-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const button=$('#search-button');button.disabled=true;
  searchKind=event.target.elements['search-kind'].value;
  results=[];$('#result-tools').hidden=true;$('#search-errors').innerHTML='';
  $('#search-results').innerHTML=empty('search','Je bronnen worden doorzocht…','Een bron die niet bereikbaar is, kan wat langer duren.');
  try{
    const response=await api('search?'+new URLSearchParams({q:$('#query').value,kind:searchKind}));
    results=response.results;
    $('#search-errors').innerHTML=response.errors.map(e=>`<div class="warning"><b>${esc(e.source)}</b> · ${esc(e.error)}</div>`).join('');
    $('#filter-source').innerHTML='<option value="all">Alle bronnen</option>'+[...new Set(results.map(r=>r.source))].map(source=>`<option value="${esc(source)}">${esc(source)}</option>`).join('');
    $('#result-tools').hidden=!results.length;
    if(results.length)renderResults();
    else $('#search-results').innerHTML=empty('search',response.errors.length===status.configured_sources?'Zoeken is niet gelukt.':'Geen titels gevonden.',response.errors.length===status.configured_sources?'Controleer je bronnen bij Instellingen.':'Probeer een andere titel of kies Films of Series.');
  }catch(e){$('#search-results').innerHTML=empty('search','Zoeken lukt nog niet.',e.message,'<button class="secondary" data-goto="settings">Naar instellingen '+icon('arrow')+'</button>');}
  finally{button.disabled=false;}
});
$('#scan-button').addEventListener('click',async event=>{const button=event.currentTarget;button.disabled=true;try{const kinds=[...new Set(status.jobs.filter(j=>j.files_imported?.length).map(j=>j.kind))];if(!kinds.length)throw Error('Er zijn nog geen PlexPort-imports om te scannen.');for(const kind of kinds)await api('scan',{kind});toast('Plex-bibliotheekscan aangevraagd.');}catch(e){toast(e.message,true);}finally{button.disabled=false;}});
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1),false));
(async()=>{try{settings=await api('settings');populateSettings();await refresh();}catch(e){toast('PlexPort kon niet worden geladen: '+e.message,true);}setInterval(refresh,4000);})();
