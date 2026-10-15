const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,'../plexport/static/app.js'),'utf8');
const start = source.indexOf("$('#search-form').addEventListener('submit',async event=>{");
const end = source.indexOf("\n$('#scan-button')",start);
assert.ok(start>=0 && end>start,'actual search submit handler must be available');

function fixture(configuredSources=2) {
  const nodes=new Map(), calls=[], renders=[];
  let handler;
  const node=id=>{
    if(!nodes.has(id))nodes.set(id,{value:'Example',innerHTML:'',textContent:'',hidden:false,disabled:false,
      addEventListener:(name,fn)=>{assert.equal(name,'submit');handler=fn;}});
    return nodes.get(id);
  };
  const context={$:node,status:{configured_sources:configuredSources},results:[],searchKind:'movie',
    URLSearchParams,icon:()=>'',api:route=>new Promise((resolve,reject)=>calls.push({route,resolve,reject})),
    empty:(icon,title,description)=>`<h3>${title}</h3><p>${description}</p>`,
    esc:value=>String(value??'').replace(/[&<>"']/g,char=>`&#${char.charCodeAt(0)};`),
    renderResults:()=>renders.push([...context.results])};
  vm.createContext(context);vm.runInContext(source.slice(start,end),context);
  const submit=(kind='movie',mode='title')=>handler({preventDefault(){},target:{elements:{
    'search-kind':{value:kind},'search-mode':{value:mode}}}});
  return {context,node,calls,renders,submit};
}
const response=changes=>({results:[],errors:[],searched_sources:1,...changes});

test('one failed compatible provider shows failure even with another incompatible provider configured',async()=>{
  const app=fixture(2), submitted=app.submit('movie');
  assert.equal(app.node('#search-button').disabled,true);
  const request=app.calls[0],query=new URLSearchParams(request.route.split('?')[1]);
  assert.equal(query.get('kind'),'movie');assert.equal(query.get('q'),'Example');
  request.resolve(response({searched_sources:1,errors:[{source:'YTS',error:'Niet bereikbaar'}]}));
  await submitted;
  assert.match(app.node('#search-results').innerHTML,/Zoeken is niet gelukt\./);
  assert.match(app.node('#search-results').innerHTML,/Controleer je bronnen/);
  assert.match(app.node('#search-errors').innerHTML,/YTS.*Niet bereikbaar/);
  assert.equal(app.node('#search-button').disabled,false);
});

test('a partial provider failure with another successful empty search remains an empty result',async()=>{
  const app=fixture(2),submitted=app.submit();
  app.calls[0].resolve(response({searched_sources:2,errors:[{source:'YTS',error:'Niet bereikbaar'}]}));
  await submitted;
  assert.match(app.node('#search-results').innerHTML,/Geen titels gevonden\./);
  assert.doesNotMatch(app.node('#search-results').innerHTML,/Zoeken is niet gelukt/);
  assert.match(app.node('#search-errors').innerHTML,/Niet bereikbaar/);
});

test('zero compatible providers is not classified as all providers failing',async()=>{
  const app=fixture(1),submitted=app.submit('tv');
  app.calls[0].resolve(response({searched_sources:0}));await submitted;
  assert.match(app.node('#search-results').innerHTML,/Geen titels gevonden\./);
  assert.doesNotMatch(app.node('#search-results').innerHTML,/Zoeken is niet gelukt/);
  assert.equal(app.node('#result-tools').hidden,true);
});

test('all attempted providers failing reports failure independently of saved source count',async()=>{
  for(const configuredSources of [0,1,4]) {
    const app=fixture(configuredSources),submitted=app.submit();
    app.calls[0].resolve(response({searched_sources:2,errors:[
      {source:'A',error:'A failed'},{source:'B',error:'B failed'}]}));await submitted;
    assert.match(app.node('#search-results').innerHTML,/Zoeken is niet gelukt\./);
  }
});

test('partial successful results render their original rows and retain source errors and notices',async()=>{
  const rows=[{title:'Show.S01E01.1080p',source:'EZTV',link:'magnet:original',season:1,episode:1}];
  const app=fixture(2),submitted=app.submit('tv','title');
  app.calls[0].resolve(response({results:rows,searched_sources:2,
    errors:[{source:'Other',error:'<Unavailable>'}],search:{notice:'One source searched'}}));await submitted;
  assert.equal(app.renders.length,1);
  assert.equal(app.renders[0][0],rows[0]);
  assert.equal(app.node('#result-tools').hidden,false);
  assert.equal(app.node('#search-note').textContent,'One source searched');
  assert.equal(app.node('#search-note').hidden,false);
  assert.match(app.node('#search-errors').innerHTML,/&#60;Unavailable&#62;/);
  assert.match(app.node('#filter-source').innerHTML,/EZTV/);
});

test('a failed search request restores the button and shows its actionable error',async()=>{
  const app=fixture(),submitted=app.submit();
  app.calls[0].reject(Error('Server opnieuw aanmelden'));await submitted;
  assert.match(app.node('#search-results').innerHTML,/Zoeken lukt nog niet\./);
  assert.match(app.node('#search-results').innerHTML,/Server opnieuw aanmelden/);
  assert.equal(app.node('#search-button').disabled,false);
});
