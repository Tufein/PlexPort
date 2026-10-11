(function(root){
  'use strict';
  function identity(title,year,kind){return JSON.stringify([String(title||'').trim(),String(year||'').trim(),kind==='tv'?'tv':'movie']);}
  function endpoint(title,year,kind){return '/api/artwork?'+new URLSearchParams({title:String(title||'').trim(),year:String(year||'').trim(),kind:kind==='tv'?'tv':'movie'});}
  function safeMetadata(value){
    if(!value||!/^\/posters\/[a-f0-9]{64}\.jpg$/.test(value.image_url||''))return null;
    try{const url=new URL(value.source_url);if(url.origin!=='https://watchsomuch.to'||!/^\/Movie\/\d+[^/]*\/[^/]+\/?$/.test(url.pathname)||url.username||url.password||url.search||url.hash)return null;}catch{return null;}
    return {image_url:value.image_url,source_url:value.source_url,source_name:'WatchSoMuch'};
  }
  const helpers={identity,endpoint,safeMetadata};
  if(typeof module==='object'&&module.exports){module.exports=helpers;return;}
  const cache=new Map(),pending=new Map(),queue=[];
  let running=0,observer=null;
  function remember(key,value){if(cache.size>=256)cache.delete(cache.keys().next().value);cache.set(key,{value,until:Date.now()+(value?30*60*1000:5*60*1000)});}
  function pump(){
    while(running<3&&queue.length){
      const task=queue.shift();running++;
      fetch(task.path,{headers:{'X-PlexPort':'1'}}).then(response=>response.ok?response.json():null).then(safeMetadata).catch(()=>null).then(value=>{remember(task.key,value);pending.delete(task.key);task.resolve(value);}).finally(()=>{running--;pump();});
    }
  }
  function lookup(title,year,kind){
    const key=identity(title,year,kind),known=cache.get(key);
    if(known&&known.until>Date.now())return Promise.resolve(known.value);
    if(pending.has(key))return pending.get(key);
    const promise=new Promise(resolve=>queue.push({key,path:endpoint(title,year,kind),resolve}));
    pending.set(key,promise);pump();return promise;
  }
  function apply(node,value){
    if(!node.isConnected||!value)return;
    const image=node.querySelector('img'),credit=node.querySelector('a');
    image.addEventListener('load',()=>{image.hidden=false;node.classList.add('has-artwork');},{once:true});
    image.addEventListener('error',()=>{image.hidden=true;credit.hidden=true;node.classList.remove('has-artwork');cache.delete(identity(node.dataset.artworkTitle,node.dataset.artworkYear,node.dataset.artworkKind));},{once:true});
    credit.href=value.source_url;credit.title='Poster via '+value.source_name;credit.setAttribute('aria-label','Bron van deze poster: '+value.source_name);credit.hidden=false;
    image.src=value.image_url;
  }
  function load(node){if(!node.isConnected)return;lookup(node.dataset.artworkTitle,node.dataset.artworkYear,node.dataset.artworkKind).then(value=>apply(node,value));}
  function mount(scope=document){
    if(observer)observer.disconnect();
    const nodes=[...scope.querySelectorAll('[data-artwork-title]')];
    if('IntersectionObserver' in root){observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){observer.unobserve(entry.target);load(entry.target);}},{rootMargin:'100px'});}
    for(const node of nodes){
      if(node.querySelector('img').getAttribute('src'))continue;
      const known=cache.get(identity(node.dataset.artworkTitle,node.dataset.artworkYear,node.dataset.artworkKind));
      if(known&&known.until>Date.now()){apply(node,known.value);continue;}
      if(observer)observer.observe(node);else load(node);
    }
  }
  root.PlexPortArtwork={...helpers,mount};
})(typeof window==='undefined'?globalThis:window);
