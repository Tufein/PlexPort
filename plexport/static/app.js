const icons={grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',film:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4m10-8h4m-4 8h4"/>',settings:'<path d="M9 3h6l1 4 4 1 1 6-4 2-2 4H9l-1-4-4-1-1-6 4-2z"/><circle cx="12" cy="12" r="3"/>',route:'<circle cx="5" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h9a4 4 0 0 1 0 8H8a3 3 0 0 0 0 6h9"/>',plus:'<path d="M12 5v14M5 12h14"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',check:'<path d="m5 12 4 4L19 6"/>',layers:'<path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 11 3 3 5-5"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',link:'<path d="m9 15 6-6m-7 5-2 2a3 3 0 0 0 4 4l4-4a3 3 0 0 0 0-4m2-2 2-2a3 3 0 0 0-4-4l-4 4a3 3 0 0 0 0 4"/>',refresh:'<path d="M20 9a8 8 0 0 0-14-4L3 8m0-5v5h5m-4 7a8 8 0 0 0 14 4l3-3m0 5v-5h-5"/>',tv:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 22h8M9 2l3 3 3-3"/>'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.film}</svg>`;
function hydrate(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let settings=null,status={jobs:[],checks:{},configured_sources:0},results=[],currentPage='overview',sourceDraft=[],pollBusy=false,toastTimer,searchKind='movie',preflightGeneration=0,downloadFilter='all',settingsBusy=false;
let titleMatches=[],preflightTimer,filesSnapshot=null,filesTimer,filesLoading=null,filesGeneration=0,filesSubmitting=null;
const pages={overview:'Overzicht',search:'Ontdekken',downloads:'Downloads',settings:'Instellingen'};
async function api(path,data){
  const response=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-PlexPort':'1',...(data===undefined?{}:{'Content-Type':'application/json'})},...(data===undefined?{}:{body:JSON.stringify(data)})});
  if(response.status===401){window.location.replace('/login'+window.location.hash);throw Error('Meld je opnieuw aan bij PlexPort.');}
  const body=await response.json();
  if(!response.ok){const error=Error(body.error||body.message||'Verzoek mislukt.');error.report=body;throw error;}
  return body;
}
function toast(message,error=false){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').className=error?'error':'';$('#toast').hidden=false;toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
function navigate(page,updateHash=true){
  if(page==='library'){page='downloads';downloadFilter='imported';$('#download-query').value='';}
  if(!pages[page])page='overview';
  currentPage=page;
  document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!=='page-'+page);
  document.querySelectorAll('nav button').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('#breadcrumb').textContent=pages[page];
  if(updateHash)history.replaceState(null,'','#'+(page==='downloads'&&downloadFilter==='imported'?'library':page));
  if(page==='downloads'){renderDownloads();finishRender();}
  window.scrollTo({top:0});
}
const bytes=n=>{if(!n)return'0 B';const units=['B','KB','MB','GB','TB'];const i=Math.min(4,Math.floor(Math.log(n)/Math.log(1024)));return(n/1024**i).toFixed(i>1?1:0)+' '+units[i];};
const eta=n=>n<0||n>8640000?'Tijd onbekend':n<60?'Minder dan een minuut':n<3600?Math.ceil(n/60)+' min':Math.floor(n/3600)+' u '+Math.ceil(n%3600/60)+' min';
function empty(name,title,description,button=''){return`<div class="empty"><span>${icon(name)}</span><h3>${esc(title)}</h3><p>${esc(description)}</p>${button}</div>`;}
function artwork(title,year,kind){return `<div class="media-artwork" data-artwork-title="${esc(title)}" data-artwork-year="${esc(year||'')}" data-artwork-kind="${kind==='tv'?'tv':'movie'}"><span class="artwork-placeholder" aria-hidden="true">${icon(kind==='tv'?'tv':'film')}<small>${kind==='tv'?'Serie':'Film'}</small></span><img alt="Poster van ${esc(title)}" width="80" height="120" decoding="async" hidden><a class="artwork-credit" target="_blank" rel="noopener noreferrer" hidden>Bron ↗</a></div>`;}
function jobRow(job){const labels={awaiting_selection:'Kies afleveringen',queued:'In wachtrij',downloading:job.paused?'Gepauzeerd':activityLabel(job.activity),importing:'Importeren',scan_pending:'Plex-scan aanvragen',done:'Geïmporteerd',stopped:'Gestopt',error:'Aandacht nodig'};let details='';const imported=PlexPortJobs.hasImports(job);if(imported){details=`<p class="file-path">${esc(job.scan_requested?'Plex-scan aangevraagd':job.state==='scan_pending'?'Plex-scan volgt':job.state==='error'?'Plex-scan niet gelukt':'In je mediamap · automatisch scannen instellen in Plex')}<br>${(job.files_imported||[]).slice(0,3).map(esc).join('<br>')}${job.files_imported?.length>3?'<br>+ '+(job.files_imported.length-3)+' bestanden':''}</p>`;}else if(job.state!=='error'){details=`<div class="progress-track" role="progressbar" aria-label="Downloadvoortgang" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(Math.max(0,Math.min(1,job.progress))*100)}"><div data-progress="${Math.round(Math.max(0,Math.min(1,job.progress))*100)}"></div></div><div class="progress-caption"><span>${Math.round(job.progress*100)}%${job.speed?' · '+bytes(job.speed)+'/s':''}</span><span>${job.state==='downloading'&&!job.paused&&(!job.activity||job.activity==='downloading')?eta(job.eta):''}</span></div>`;}const actions=(job.selection_requested&&['waiting_metadata','awaiting_selection'].includes(job.selection_state)?`<button class="primary" data-files="${esc(job.id)}">${job.selection_state==='waiting_metadata'?'Bestandsinformatie bekijken':'Afleveringen kiezen'}</button>`:'')+(job.state==='stopped'?`<button data-action="resume" data-id="${esc(job.id)}">Hervatten</button>`:`<button data-action="stop" data-id="${esc(job.id)}">Stoppen</button>`)+(job.state==='error'?`<button data-action="retry" data-id="${esc(job.id)}">Opnieuw proberen</button>`:'')+`<button class="danger-text" data-action="remove" data-id="${esc(job.id)}">Verwijderen</button>`;return`<article class="job-row" data-job-id="${esc(job.id)}">${artwork(job.title,job.year,job.kind)}<div class="job-body"><div class="job-top"><div class="job-title">${esc(job.title)}${job.year?' ('+esc(job.year)+')':''}</div><span class="status-pill ${job.state==='done'?'good':job.state==='error'?'bad':''}">${labels[job.state]||esc(job.state)}</span></div><div class="job-meta">${job.kind==='tv'?'Serie':'Film'} · ${esc(job.source)} · ${new Date(job.created*1000).toLocaleDateString('nl-BE',{day:'numeric',month:'short'})}</div>${details}${job.selection_requested&&job.selection_state!=='committed'?'<p class="hint">'+(job.selection_state==='waiting_metadata'?'Bestandsinformatie ophalen. Er kan al data binnenkomen; de import wacht op jouw keuze.':'De import wacht op je bestandskeuze. Kies afleveringen om door te gaan.')+'</p>':''}${job.state==='downloading'&&!job.paused&&activityNote(job.activity)?`<p class="hint activity-note">${esc(activityNote(job.activity))}</p>`:''}${job.error?`<div class="job-error">${esc(job.error)}</div>`:''}${job.selection_error?`<div class="job-error">${esc(job.selection_error)}</div>`:''}${actions?'<div class="job-actions">'+actions+'</div>':''}</div></article>`;}
function renderStatus(){
  const jobs=status.jobs,totals=PlexPortJobs.counts(jobs);
  $('#stat-active').textContent=totals.active;$('#nav-count').textContent=totals.active;
  $('#stat-done').textContent=totals.imported;$('#stat-sources').textContent=status.configured_sources;
  document.querySelectorAll('.app-version').forEach(element=>element.textContent=status.version?'v'+status.version:'Versie onbekend');
  const noJobs=empty('download','Nog even rustig hier.','Voeg je eerste download toe. Wij houden de route naar je bibliotheek in de gaten.','<button class="secondary" data-add>Je eerste download toevoegen '+icon('plus')+'</button>');
  $('#recent-jobs').innerHTML=jobs.length?jobs.slice(0,3).map(jobRow).join(''):noJobs;
  renderDownloads(noJobs);renderSetup();
  const connections=[['downloader',settings?.downloader.type==='qbittorrent'?'qBittorrent':'Transmission','Torrent-downloader','download'],['plex','Plex Media Server','Automatische bibliotheekscan','film'],['storage','Mediamappen','Download- en Plex-bestemming','layers']];
  $('#connection-list').innerHTML=connections.map(([key,title,subtitle,name])=>{
    const check=status.checks[key];
    return`<div class="connection-row"><span class="connection-icon">${icon(name)}</span><div><b>${title}</b><small>${subtitle}</small></div><span class="status-pill ${check?(check.ok?'good':'bad'):''}" title="${esc(check?.message||'Test de verbinding bij Instellingen')}">${check?(check.ok?'Getest':'Controleer'):'Niet getest'}</span></div>`;
  }).join('');
  finishRender();
}
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
async function saveSettings(){
  if(!$('#settings-form').reportValidity())throw Error('Vul de instellingen volledig in.');
  settings=await api('settings',collectSettings());
  status.configured_sources=settings.sources.length;
  populateSettings();
  $('#save-status').textContent='Opgeslagen op je PlexPort-server.';
  await refresh();
  return settings;
}

function addDialog(result=null){const form=$('#add-form');form.reset();titleMatches=[];$('#title-warning').hidden=true;$('#confirm-title').checked=false;$('#add-error').textContent='';form.elements.kind.value=result?.kind||'movie';form.elements.title.value=result?.library_title||result?.title||'';form.elements.year.value=result?.year??'';form.elements.season.value=result?.season??'';form.elements.episode.value=result?.episode??'';form.elements.link.value=result?.link||'';form.dataset.source=result?.source||'Handmatig';form.dataset.expectedBytes=String(result?.size||0);updateKind();$('#add-dialog').showModal();checkDownload();setTimeout(()=>form.elements.title.focus(),20);}
function updateKind(){const tv=$('#add-form').elements.kind.value==='tv';$('#episode-fields').hidden=!tv;$('#tv-hint').hidden=!tv;$('#selection-choice').hidden=!tv;if(!tv)$('#add-form').elements.selection_requested.checked=false;}
async function fileBase64(file){if(file.size>8*1024*1024)throw Error('Torrentbestand te groot. Maximaal 8 MB.');const bytes=new Uint8Array(await file.arrayBuffer());let text='';for(let i=0;i<bytes.length;i+=32768)text+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(text);}
function downloaderHint(){const form=$('#settings-form'),qb=form.elements['downloader.type'].value==='qbittorrent';form.elements['downloader.url'].placeholder=qb?'http://NAS-adres:8080':'http://transmission:9091/transmission/rpc';}

function activityLabel(activity){
  return {queued:'Wacht op een vrije plek',checking:'Bestanden controleren',metadata:'Download voorbereiden',waiting:'Wacht op delers',moving:'Bestanden verplaatsen',allocating:'Ruimte voorbereiden',paused:'Gepauzeerd',seeding:'Download klaar',unknown:'Status wordt opgehaald'}[activity]||'Downloaden';
}
function activityNote(activity){
  return {queued:'Je downloader laat deze taak starten zodra er plaats is.',checking:'Je downloader controleert de bestanden. PlexPort wacht tot die controle klaar is.',metadata:'De bestandsinformatie wordt opgehaald. Daarna verschijnt de downloadvoortgang.',waiting:'Er komt nu geen data binnen. Dit kan tijdelijk zijn. Blijft het zo, controleer je downloader of kies een andere versie.',moving:'Je downloader verplaatst de bestanden. PlexPort importeert ze pas als dit klaar is.'}[activity]||'';
}
function renderProgress(){document.querySelectorAll('.progress-track > [data-progress]').forEach(bar=>{bar.style.width=bar.dataset.progress+'%';});}
function finishRender(){renderProgress();PlexPortArtwork.mount();}
function renderDownloads(noJobs=''){
  const query=$('#download-query').value.trim();
  const jobs=status.jobs.filter(job=>PlexPortDiscovery.matches(job.title,query)&&PlexPortJobs.matchesFilter(job,downloadFilter));
  const totals=PlexPortJobs.counts(status.jobs);
  document.querySelectorAll('[data-download-filter]').forEach(button=>{
    const filter=button.dataset.downloadFilter;
    button.setAttribute('aria-pressed',String(filter===downloadFilter));
    button.querySelector('.tab-count').textContent=totals[filter];
  });
  $('#import-tools').hidden=downloadFilter!=='imported'&&!jobs.some(PlexPortJobs.hasImports);
  $('#download-count').textContent=`${jobs.length} van ${status.jobs.length} downloads`;
  const noImports=empty('film','Nog geen imports in deze selectie.','Je downloads verschijnen hier zodra ze in je Plex-mediamappen zijn geplaatst.');
  $('#all-jobs').innerHTML=jobs.length?jobs.map(jobRow).join(''):downloadFilter==='imported'&&!query?noImports:status.jobs.length?empty('search','Geen downloads in deze selectie.','Pas de naam of de status aan.'):noJobs||empty('download','Nog geen downloads.','Voeg een link of torrentbestand toe.');
}
function updateDownloads(){renderDownloads();finishRender();}
function setDownloadFilter(filter){
  downloadFilter=filter;
  history.replaceState(null,'','#'+(filter==='imported'?'library':'downloads'));
  updateDownloads();
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
function filterValues(){return Object.fromEntries(['quality','size','seeders','source','sort'].map(id=>[id,$('#filter-'+id).value]));}
function writeFilterValues(values){for(const [id,value]of Object.entries(values))$('#filter-'+id).value=value;}
function releaseRow(release){
  const qualityNames={'1080':'Full HD','720':'HD','2160':'4K','sd':'Standaardbeeld','unknown':'Kwaliteit niet vermeld'};
  return`<div class="release-row"><div class="job-body"><div class="release-title">${esc(release.title)}</div><div class="result-meta"><span class="quality-badge">${qualityNames[release.quality]||qualityNames.unknown}</span><span>${esc(release.source)}</span><span>${release.size?bytes(release.size):'Grootte onbekend'}</span><span>${Number(release.seeders||0)} delers</span></div></div><button class="primary" data-result="${release.index}" aria-label="Kies ${esc(release.title)}">${icon('download')}Kiezen</button></div>`;
}
function titleCard(group){
  const cast=[...new Set(group.versions.map(release=>release.cast).filter(Boolean))].join(' · ');
  const episode=group.kind==='tv'&&group.season!==''&&group.season!==undefined&&group.episode!==''&&group.episode!==undefined?` · Seizoen ${esc(group.season)}, aflevering ${esc(group.episode)}`:'';
  return`<article class="title-card"><div class="title-card-heading">${artwork(group.title,group.year,group.kind)}<div class="job-body"><h3>${esc(group.title)}${group.year?' ('+esc(group.year)+')':''}</h3><p class="job-meta">${group.kind==='tv'?'Serie':'Film'}${episode}${cast?' · Met '+esc(cast):''}</p></div></div><details class="release-list" open><summary>${group.versions.length} ${group.versions.length===1?'versie':'versies'} beschikbaar</summary>${group.versions.map(releaseRow).join('')}</details></article>`;
}
function renderResults(){
  const rows=PlexPortDiscovery.select(results,PlexPortDiscovery.readFilters(filterValues()));
  const groups=PlexPortDiscovery.group(rows,searchKind);
  $('#search-results').innerHTML=`<div class="result-heading">${groups.length} ${groups.length===1?'titel':'titels'} · ${rows.length} van ${results.length} versies</div>`+(rows.length?groups.map(titleCard).join(''):empty('search','Geen versie past bij deze keuze.','Probeer een andere kwaliteit of een grotere maximale bestandsgrootte.','<button class="secondary" id="empty-reset">Alle versies tonen</button>'));
  finishRender();
}
function applyPreferences(preferences){
  writeFilterValues(PlexPortDiscovery.writeFilters(preferences));
  $('#preference-status').textContent='Je opgeslagen voorkeuren zijn toegepast. Alles tonen is tijdelijk.';
  if(results.length)renderResults();
}
async function savePreferences(){
  const button=$('#save-preferences');button.disabled=true;
  try{
    const preferences=PlexPortDiscovery.readPreferences(filterValues());
    const saved=await api('settings',{preferences});settings.preferences=saved.preferences;
    $('#preference-status').textContent='Opgeslagen op je PlexPort-server. Ook beschikbaar op Android.';
    toast('Je downloadvoorkeuren zijn opgeslagen.');
  }catch(error){$('#preference-status').textContent=error.message;toast(error.message,true);}
  finally{button.disabled=false;}
}
async function restorePreferences(){
  const button=$('#restore-preferences');button.disabled=true;
  try{const saved=await api('settings');settings.preferences=saved.preferences;applyPreferences(saved.preferences);}
  catch(error){toast(error.message,true);}
  finally{button.disabled=false;}
}
function resetFilters(){
  writeFilterValues(PlexPortDiscovery.writeFilters());
  $('#preference-status').textContent='Alle versies zichtbaar. Je opgeslagen voorkeuren blijven behouden.';
  if(results.length)renderResults();
}
function folderResults(report){
  return report.folders.map(folder=>`<div class="folder-check"><span class="status-pill ${folder.ok?'good':'bad'}">${folder.ok?'✓':'!'}</span><div><b>${esc(folder.label)}</b><small>${esc(folder.message)}${folder.free!==null?' · '+bytes(folder.free)+' vrij':''}</small></div></div>`).join('');
}
function downloadDraft(){
  const form=$('#add-form');
  return {kind:form.elements.kind.value,title:form.elements.title.value,year:form.elements.year.value,
    season:form.elements.season.value,episode:form.elements.episode.value,
    expected_bytes:Number(form.dataset.expectedBytes||0),selection_requested:form.elements.selection_requested.checked};
}
function showTitleConflicts(matches){
  const signature=items=>items.map(item=>item.id).sort().join(',');
  if(signature(titleMatches)!==signature(matches))$('#confirm-title').checked=false;
  titleMatches=matches;
  $('#title-warning').hidden=!matches.length;
  $('#title-matches').innerHTML=matches.map(match=>`<div class="existing-title"><b>${esc(match.title)}${match.year?' ('+esc(match.year)+')':''}</b><span>${match.imported?'Al geïmporteerd':{stopped:'Gestopt',error:'Aandacht nodig',queued:'In wachtrij',done:'Geïmporteerd'}[match.state]||'Al in je downloads'}${match.certainty==='possible'?' · mogelijke overeenkomst':''}</span><p class="hint">${esc(match.message||({season_pack:'Een seizoenspakket kan deze aflevering bevatten.',missing_episode:'Afleveringsinformatie ontbreekt; controleer de bestaande taak.',missing_year:'Het jaar ontbreekt; de titel is mogelijk dezelfde.',ambiguous_title:'De titel is niet eenduidig.'}[match.reason]||'De titel en bekende gegevens komen overeen.'))}</p><button class="text-button" type="button" data-existing-task="${esc(match.id)}">Bekijk bestaande taak</button></div>`).join('');
}
async function checkDownload(){
  const generation=++preflightGeneration;
  $('#download-preflight').textContent='Mappen, opslag en eerdere taken controleren…';
  try{
    const report=await api('preflight',downloadDraft());
    if(generation!==preflightGeneration||!$('#add-dialog').open)return;
    showTitleConflicts(report.title_conflicts||[]);
    const capability=report.import_capability;
    const storage=capability?`<section class="import-estimate"><h3>Ruimte bij het importeren</h3><p>${esc(capability.message)}</p>${capability.additional_bytes>0?`<p>Geschatte extra ruimte: <b>${bytes(capability.additional_bytes)}</b>. De oorspronkelijke download blijft beschikbaar om te delen.</p>`:''}${capability.space_message?`<p class="${capability.space_ok===false?'form-error':'hint'}">${esc(capability.space_message)}</p>`:''}<details><summary>Hoe controleren we dit?</summary><p class="hint">${esc(capability.note)}</p></details></section>`:'';
    $('#download-preflight').innerHTML=`<h3>Voor je start${report.expected_bytes?' · '+bytes(report.expected_bytes):''}</h3>${folderResults(report)}${storage}${report.warnings.map(message=>`<p class="hint">${esc(message)}</p>`).join('')}<p class="hint">${esc(report.note)}</p>`;
  }catch(error){if(generation===preflightGeneration)$('#download-preflight').textContent=error.message;}
}
function invalidateDownload(){
  preflightGeneration++;clearTimeout(preflightTimer);titleMatches=[];$('#title-warning').hidden=true;$('#confirm-title').checked=false;
  preflightTimer=setTimeout(checkDownload,350);
}
function closeFiles(){if(filesSubmitting===filesGeneration)return;clearTimeout(filesTimer);filesGeneration++;filesSnapshot=null;filesSubmitting=null;$('#files-dialog').close();}
async function loadFiles(){
  if(filesLoading===filesGeneration||filesSubmitting===filesGeneration||!$('#files-dialog').open)return;
  const generation=filesGeneration;filesLoading=generation;filesSnapshot=null;$('#files-submit').disabled=true;clearTimeout(filesTimer);$('#files-error').textContent='';
  const jobId=$('#files-form').dataset.id;
  try{
    const snapshot=await api('files',{id:jobId});
    if(generation!==filesGeneration||!$('#files-dialog').open||$('#files-form').dataset.id!==jobId)return;
    filesSnapshot=snapshot;
    const ready=snapshot.state==='awaiting_selection';
    $('#files-note').textContent=snapshot.state==='waiting_metadata'?'De bestandsinformatie is nog niet beschikbaar. Je downloader kan nu delers benaderen en data ontvangen. Er wordt pas geïmporteerd nadat je kiest.':snapshot.state==='committed'?'Je bestandskeuze is opgeslagen. Alleen die bestanden komen voor import in aanmerking.':'Je downloader wacht op je keuze. Kies minstens één video; alleen gekozen, voltooide bestanden worden geïmporteerd.';
    $('#files-list').innerHTML=(snapshot.files||[]).map(file=>`<label class="torrent-file"><input type="checkbox" name="selected_file" value="${file.index}" ${file.selected?'checked':''} ${!ready||!file.selectable?'disabled':''}><span><b>${esc(file.name)}</b><small>${esc(PlexPortSelection.fileDescription(file))} · ${bytes(file.size)}${file.progress>=0?' · '+Math.round(file.progress*100)+'%':''}</small></span></label>`).join('');
    $('#files-submit').disabled=!ready;
    if(snapshot.error)$('#files-error').textContent=snapshot.error;
    if(snapshot.state==='waiting_metadata')filesTimer=setTimeout(()=>{if(generation===filesGeneration)loadFiles();},3000);
  }catch(error){if(generation===filesGeneration&&$('#files-dialog').open)$('#files-error').textContent=error.message;}
  finally{if(generation===filesGeneration)filesLoading=null;}
}
function openFiles(id){
  const job=status.jobs.find(job=>job.id===id);if(!job)return;
  filesGeneration++;filesSubmitting=null;filesSnapshot=null;$('#files-form').querySelectorAll('button').forEach(button=>button.disabled=false);$('#files-form').dataset.id=id;$('#files-title').textContent=job.title;
  $('#files-list').textContent='Bestandsinformatie controleren…';$('#files-note').textContent='De import wacht op je bevestigde keuze.';$('#files-error').textContent='';$('#files-submit').disabled=true;
  $('#files-dialog').showModal();loadFiles();
}
for(const id of ['files-close','files-cancel'])$('#'+id).addEventListener('click',closeFiles);
$('#files-dialog').addEventListener('close',()=>{if(!$('#files-dialog').open){clearTimeout(filesTimer);filesGeneration++;filesSnapshot=null;filesSubmitting=null;}});
$('#files-dialog').addEventListener('cancel',event=>{if(filesSubmitting===filesGeneration)event.preventDefault();});
$('#files-reload').addEventListener('click',loadFiles);
$('#files-form').addEventListener('submit',async event=>{
  event.preventDefault();if(filesLoading===filesGeneration||filesSubmitting===filesGeneration)return;const generation=filesGeneration,button=$('#files-submit');
  const controls=[...$('#files-form').querySelectorAll('button,input')].map(control=>[control,control.disabled]);
  const values=[...$('#files-list').querySelectorAll('input:checked')].map(input=>input.value);
  let data;try{data=PlexPortSelection.selectionPayload(filesSnapshot,values);}catch(error){$('#files-error').textContent=error.message;return;}
  filesSubmitting=generation;controls.forEach(([control])=>control.disabled=true);$('#files-error').textContent='';
  try{
    const saved=await api('select',data);
    if(generation!==filesGeneration)return;
    filesSubmitting=null;closeFiles();toast(saved.selection_error?'Je keuze is opgeslagen, maar hervatten is niet gelukt. Open de taak en kies Hervatten.':(saved.job_state||saved.state)==='stopped'?'Bestandskeuze opgeslagen. De taak blijft gestopt tot je Hervatten kiest.':'Bestandskeuze opgeslagen. Je download gaat verder.',Boolean(saved.selection_error));await refresh();
  }catch(error){
    if(generation!==filesGeneration)return;
    $('#files-error').textContent=error.message;if(error.report?.code==='metadata_changed'){filesSubmitting=null;await loadFiles();if(generation===filesGeneration&&!$('#files-error').textContent)$('#files-error').textContent='De bestandslijst is veranderd. Controleer de vernieuwde lijst en kies opnieuw.';}
  }finally{
    if(generation===filesGeneration){filesSubmitting=null;controls.forEach(([control,disabled])=>control.disabled=disabled);button.disabled=filesSnapshot?.state!=='awaiting_selection';}
  }
});
document.addEventListener('click',event=>{
  const filesButton=event.target.closest('[data-files]');if(filesButton)openFiles(filesButton.dataset.files);
  const existing=event.target.closest('[data-existing-task]');if(existing){
    $('#add-dialog').close();downloadFilter='all';$('#download-query').value='';navigate('downloads');
    const row=[...document.querySelectorAll('#all-jobs [data-job-id]')].find(row=>row.dataset.jobId===existing.dataset.existingTask);
    if(row){row.tabIndex=-1;row.focus();row.scrollIntoView({block:'center'});}
  }
});
function connectionReport(target,report){
  const title={downloader:'Downloader',storage:'Mediamappen',plex:'Plex'}[target];
  const sections=report.sections?.length?`<p class="hint">${report.sections.map(section=>esc(section.id)+': '+esc(section.title)+' ('+esc(section.type)+')').join(' · ')}</p>`:'';
  const folders=report.folders?folderResults(report):report.free!==undefined&&report.free!==null?`<p class="hint">${bytes(report.free)} vrij</p>`:'';
  return`<div class="connection-report"><div class="${report.ok?'notice':'warning'}"><b>${title}</b><span>${esc(report.message||report.error||'Verzoek mislukt.')}</span></div>${sections}${folders}</div>`;
}
async function testConnection(target){
  const display=$('#test-'+target);display.textContent='Verbinding controleren…';
  let report;
  try{report=await api('test',{target});}
  catch(error){report={...error.report,ok:false,message:error.message};}
  display.innerHTML=connectionReport(target,report);
  return report;
}
async function runConnectionTests(selectedTargets=null){
  if(settingsBusy)return;
  settingsBusy=true;
  const controls=[...document.querySelectorAll('#save-top,#settings-form button[type="submit"],[data-test]')];
  controls.forEach(control=>control.disabled=true);
  $('#check-all-result').textContent='Instellingen opslaan…';
  try{
    await saveSettings();
    const targets=selectedTargets||['downloader','storage',...(settings.plex.url&&settings.plex.token_set?['plex']:[])];
    const rows=[];let failed=false;
    for(const target of targets){
      const title={downloader:'Downloader',storage:'Mediamappen',plex:'Plex'}[target];
      $('#check-all-result').innerHTML=rows.join('')+`<p class="hint">${title} controleren…</p>`;
      const report=await testConnection(target);failed=failed||!report.ok;
      rows.push(connectionReport(target,report));
    }
    if(!selectedTargets&&!targets.includes('plex'))rows.push('<p class="hint">Automatisch scannen via Plex is niet ingesteld. PlexPort kan wel bestanden in je mediamappen plaatsen.</p>');
    $('#check-all-result').innerHTML=rows.join('');
    toast(failed?'Instellingen opgeslagen. Controleer de meldingen bij je verbindingen.':'Instellingen opgeslagen en gecontroleerd.',failed);
  }catch(error){$('#check-all-result').innerHTML=`<div class="warning">${esc(error.message)}</div>`;toast(error.message,true);}
  finally{await refresh();settingsBusy=false;controls.forEach(control=>control.disabled=false);}
}

hydrate();navigate(location.hash.slice(1),false);
$('#logout-button').addEventListener('click',async()=>{try{const response=await fetch('/auth/logout',{method:'POST',headers:{'X-PlexPort':'1','Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error('Afmelden is niet gelukt. Probeer opnieuw.');window.location.replace('/login');}catch(error){toast(error.message,true);}});
$('#save-preferences').addEventListener('click',savePreferences);$('#restore-preferences').addEventListener('click',restorePreferences);$('#reset-filters').addEventListener('click',resetFilters);document.addEventListener('click',event=>{if(event.target.closest('#empty-reset'))resetFilters();});for(const id of ['quality','size','seeders','source','sort'])$('#filter-'+id).addEventListener('change',renderResults);$('#download-query').addEventListener('input',updateDownloads);document.querySelectorAll('[data-download-filter]').forEach(button=>button.addEventListener('click',()=>setDownloadFilter(button.dataset.downloadFilter)));
$('#theme-choice').value=window.PlexPortTheme.preference;
$('#theme-choice').addEventListener('change',event=>window.PlexPortTheme.set(event.target.value));
$('#settings-form').elements['downloader.type'].addEventListener('change',downloaderHint);
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.page)navigate(button.dataset.page);
  if(button.dataset.goto)navigate(button.dataset.goto);
  if(button.hasAttribute('data-add'))addDialog();
  if(button.dataset.removeSource){captureSources();sourceDraft=sourceDraft.filter(source=>source.id!==button.dataset.removeSource);renderSources();}
  if(button.dataset.result!==undefined){const selected=results[Number(button.dataset.result)];addDialog({...selected,kind:['movie','tv'].includes(selected?.kind)?selected.kind:searchKind});}
  if(button.dataset.action==='remove'){removeDialog(button.dataset.id);return;}
  if(button.dataset.action){
    button.disabled=true;
    try{await api('action',{id:button.dataset.id,action:button.dataset.action});toast(button.dataset.action==='stop'?'Download gestopt. Je kunt hem later hervatten.':button.dataset.action==='resume'?'Download hervat.':'Download wordt opnieuw geprobeerd.');await refresh();}
    catch(error){toast(error.message,true);}
    finally{button.disabled=false;}
  }
  if(button.dataset.test)await runConnectionTests([button.dataset.test]);
});
$('#save-top').addEventListener('click',()=>runConnectionTests());$('#settings-form').addEventListener('submit',event=>{event.preventDefault();runConnectionTests();});$('#add-source').addEventListener('click',()=>{captureSources();sourceDraft.push({id:crypto.getRandomValues(new Uint8Array(16)).reduce((id,byte)=>id+byte.toString(16).padStart(2,'0'),''),name:'',url:''});renderSources();$('#source-fields').lastElementChild.querySelector('input').focus();});
$('#add-watchsomuch').addEventListener('click',()=>{captureSources();if(sourceDraft.some(s=>s.type==='watchsomuch')){toast('WatchSoMuch is al toegevoegd.');return;}sourceDraft.push({id:crypto.getRandomValues(new Uint8Array(16)).reduce((id,byte)=>id+byte.toString(16).padStart(2,'0'),''),type:'watchsomuch',name:'WatchSoMuch',url:'https://watchsomuch.to'});renderSources();});
$('#add-dialog').addEventListener('cancel',event=>{if($('#add-submit').disabled)event.preventDefault();});$('#close-dialog').addEventListener('click',()=>{if(!$('#add-submit').disabled)$('#add-dialog').close();});$('#cancel-dialog').addEventListener('click',()=>{if(!$('#add-submit').disabled)$('#add-dialog').close();});$('#add-form').addEventListener('change',event=>{if(event.target.name==='kind')updateKind();if(['kind','title','year','season','episode','selection_requested'].includes(event.target.name))invalidateDownload();});$('#add-form').addEventListener('input',event=>{if(['title','year','season','episode'].includes(event.target.name))invalidateDownload();});$('#add-form').elements.link.addEventListener('input',()=>{$('#add-form').dataset.expectedBytes='0';});$('#add-form').elements.link.addEventListener('change',checkDownload);$('#add-form').elements.torrent.addEventListener('change',event=>{if(event.target.files.length){$('#add-form').elements.link.value='';$('#add-form').dataset.expectedBytes='0';checkDownload();}});
$('#add-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.target,button=$('#add-submit');button.disabled=true;$('#add-error').textContent='';try{const data=Object.fromEntries(new FormData(form));delete data.torrent;data.source=form.dataset.source;data.expected_bytes=Number(form.dataset.expectedBytes||0);data.selection_requested=form.elements.selection_requested.checked;data.confirmed_conflicts=$('#confirm-title').checked?titleMatches.map(match=>match.id):[];if(titleMatches.length&&!$('#confirm-title').checked){$('#confirm-title').focus();throw Error('Controleer de bestaande titel en kies bewust of je met deze versie wilt doorgaan.');}if(form.elements.torrent.files[0]){data.metainfo=await fileBase64(form.elements.torrent.files[0]);data.link='';}await api('jobs',data);$('#add-dialog').close();toast('Download toegevoegd. Je kunt de voortgang hier volgen.');downloadFilter='active';navigate('downloads');await refresh();}catch(e){if(e.report?.code==='title_conflict'){showTitleConflicts(e.report.matches||[]);$('#confirm-title').checked=false;}$('#add-error').textContent=e.message;}finally{button.disabled=false;}});
$('#search-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const button=$('#search-button');button.disabled=true;
  searchKind=event.target.elements['search-kind'].value;const searchMode=event.target.elements['search-mode'].value;
  results=[];$('#result-tools').hidden=true;$('#search-errors').innerHTML='';$('#search-note').hidden=true;$('#search-note').textContent='';
  $('#search-results').innerHTML=empty('search','Je bronnen worden doorzocht…','Een bron die niet bereikbaar is, kan wat langer duren.');
  try{
    const response=await api('search?'+new URLSearchParams({q:$('#query').value,kind:searchKind,mode:searchMode}));
    results=response.results;$('#search-note').textContent=response.search?.notice||'';$('#search-note').hidden=!response.search?.notice;
    $('#search-errors').innerHTML=response.errors.map(e=>`<div class="warning"><b>${esc(e.source)}</b> · ${esc(e.error)}</div>`).join('');
    $('#filter-source').innerHTML='<option value="all">Alle bronnen</option>'+[...new Set(results.map(r=>r.source))].map(source=>`<option value="${esc(source)}">${esc(source)}</option>`).join('');
    $('#result-tools').hidden=!results.length;
    if(results.length)renderResults();
    else $('#search-results').innerHTML=empty('search',response.errors.length===status.configured_sources?'Zoeken is niet gelukt.':'Geen titels gevonden.',response.errors.length===status.configured_sources?'Controleer je bronnen bij Instellingen.':'Probeer een andere titel of kies Films of Series.');
  }catch(e){$('#search-results').innerHTML=empty('search','Zoeken lukt nog niet.',e.message,'<button class="secondary" data-goto="settings">Naar instellingen '+icon('arrow')+'</button>');}
  finally{button.disabled=false;}
});
$('#scan-button').addEventListener('click',async event=>{const button=event.currentTarget;button.disabled=true;try{const kinds=[...new Set(status.jobs.filter(PlexPortJobs.hasImports).map(j=>j.kind))];if(!kinds.length)throw Error('Er zijn nog geen PlexPort-imports om te scannen.');for(const kind of kinds)await api('scan',{kind});toast('Plex-bibliotheekscan aangevraagd.');}catch(e){toast(e.message,true);}finally{button.disabled=false;}});
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1),false));
(async()=>{try{settings=await api('settings');populateSettings();applyPreferences(settings.preferences);await refresh();}catch(e){toast('PlexPort kon niet worden geladen: '+e.message,true);}setInterval(refresh,4000);})();

document.querySelectorAll('input[name="search-mode"]').forEach(input=>input.addEventListener('change',()=>{$('#query').placeholder=input.value==='actor'?'Naam van een acteur of actrice, bijvoorbeeld Tom Hanks':'Film of serie, bijvoorbeeld Star*';}));
