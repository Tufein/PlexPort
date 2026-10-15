const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const discovery = require('../plexport/static/discovery.js');
const {select, group, recommend} = discovery;
const GB = 1024 ** 3;

const film = changes => ({title:'Example.1080p',library_title:'Example',year:'2024',kind:'movie',
  source:'Source A',link:'magnet:example',size:3 * GB,seeders:5,...changes});

test('availability takes priority over quality and file size', () => {
  const rows = select([film({title:'Example.2160p',seeders:20,size:GB}),
    film({title:'Example.720p',seeders:21,size:4 * GB})]);
  assert.equal(recommend(rows), rows.find(row => row.index === 1));
  assert.equal(recommend(rows).index, 1);
});

test('equal availability prefers 4K, Full HD, HD, SD, then unknown quality', () => {
  const rows = select(['unmarked','SD','720p','1080p','2160p'].map(label => film({title:`Example.${label}`})));
  for (let end=rows.length;end>0;end--) {
    assert.equal(recommend(rows.slice(0,end)).index, end-1);
  }
});

test('all-zero availability still produces a stable quality recommendation', () => {
  const rows = select([film({title:'Example.720p',seeders:0}),film({title:'Example.1080p',seeders:0}),
    film({title:'Example.2160p',seeders:0})],{sort:'smallest'});
  assert.equal(recommend(rows).index, 2);
  assert.equal(recommend([...rows].reverse()).index, 2);
});

test('quality ties prefer a known smaller size and finally the original result index', () => {
  const rows = select([film({size:0}),film({size:4*GB}),film({size:2*GB}),film({size:2*GB})]);
  assert.equal(recommend(rows).index, 2);
  assert.equal(recommend([...rows].reverse()).index, 2);
  assert.equal(recommend([rows[0],{...rows[0],index:10,size:undefined}]).index, 0);
});

test('display sorting changes version order without changing the recommendation', () => {
  const results = [film({title:'A.720p',seeders:5,size:GB}),
    film({title:'Z.1080p',seeders:30,size:4*GB}),film({title:'B.2160p',seeders:20,size:2*GB})];
  for (const sort of ['seeders','smallest','title']) {
    const groups = group(select(results,{sort}),'movie');
    assert.equal(groups.length,1);
    assert.equal(recommend(groups[0].versions).index,1);
    assert.equal(recommend(groups[0].versions).link,results[1].link);
  }
});

test('recommendation cannot bring a filtered quality, source, size or seeder count back', () => {
  const results = [film({title:'Example.2160p',source:'B',seeders:100,size:12*GB}),
    film({title:'Example.1080p',source:'A',seeders:30,size:3*GB}),
    film({title:'Example.720p',source:'A',seeders:1,size:GB})];
  const cases = [[{quality:'1080'},1],[{source:'A'},1],[{maxGB:2},2],[{minSeeders:31},0]];
  for (const [filters,index] of cases) {
    const rows = select(results,filters), selected = recommend(rows);
    assert.equal(selected.index,index);
    assert.ok(rows.includes(selected));
    assert.ok(selected.index>=0 && selected.index<results.length);
    assert.equal(selected.title,results[selected.index].title);
  }
  assert.equal(recommend(select(results,{quality:'sd'})),null);
});

test('recommendations keep unsafe identities, remakes and TV episodes in separate groups', () => {
  const results = [film(),film({year:'1982',seeders:100}),film({year:'',seeders:200}),
    film({year:'',seeders:300}),film({kind:'tv',season:1,episode:1}),
    film({kind:'tv',season:1,episode:2})];
  const groups = group(select(results),'movie');
  assert.equal(groups.length,results.length);
  assert.deepEqual(groups.map(entry=>recommend(entry.versions).index).sort(),[0,1,2,3,4,5]);
});

test('ranking never mutates or copies rows and rejects unusable selection indices', () => {
  const rows = select([film(),film({seeders:10})]), before = structuredClone(rows);
  assert.equal(recommend(rows),rows[0]);
  assert.deepEqual(rows,before);
  assert.equal(recommend([]),null);
  assert.equal(recommend([null,film(),film({index:-1}),film({index:1.5}),film({index:'1'})]),null);
  assert.equal(recommend([film({index:2,seeders:NaN,size:-1}),film({index:1,seeders:-5,size:Infinity})]).index,1);
});

function cardFixture(results,filters={}) {
  const source = fs.readFileSync(path.join(__dirname,'../plexport/static/app.js'),'utf8');
  const start = source.indexOf('function releaseMeta(release){');
  const end = source.indexOf('\nfunction applyPreferences(',start);
  assert.ok(start>=0 && end>start);
  const output={innerHTML:''}, confirmations=[];
  let clickHandler;
  const context = {PlexPortDiscovery:discovery,results,searchKind:'movie',
    $:()=>output,filterValues:()=>({quality:'all',size:'0',seeders:'0',source:'all',sort:'seeders',...filters}),
    esc:value=>String(value??'').replace(/[&<>"']/g,char=>`&#${char.charCodeAt(0)};`),
    bytes:value=>`${value/GB} GB`,artwork:()=>'',icon:()=>'',finishRender(){},empty:()=>'<p>Empty</p>',
    document:{addEventListener:(name,handler)=>{clickHandler=handler;}},
    addDialog:result=>confirmations.push(result),api:()=>{throw Error('A recommendation must open confirmation first');}};
  vm.createContext(context);vm.runInContext(source.slice(start,end),context);
  const listenerStart=source.indexOf("document.addEventListener('click',async event=>{");
  const listenerEnd=source.indexOf("\n$('#save-top')",listenerStart);
  assert.ok(listenerStart>=0 && listenerEnd>listenerStart);
  vm.runInContext(source.slice(listenerStart,listenerEnd),context);
  return {context,output,confirmations,click:async index=>{
    const button={dataset:{result:String(index)},hasAttribute:()=>false};
    await clickHandler({target:{closest:()=>button}});
  }};
}

test('title cards default to collapsed versions and one prominent recommendation', () => {
  const results = [film({title:'Example.720p',seeders:2}),film({title:'Example.2160p',seeders:10})];
  const app=cardFixture(results);app.context.renderResults();
  const html=app.output.innerHTML;
  assert.match(html,/<details class="release-list">/);
  assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
  assert.match(html,/Andere kwaliteit of versie kiezen \(2\)/);
  assert.equal((html.match(/class="primary" data-result=/g)||[]).length,1);
  assert.match(html,/class="primary" data-result="1"/);
  assert.match(html,/Aanbevolen/);
  assert.match(html,/4K/);
  assert.match(html,/10 delers/);
  assert.match(html,/Source A/);
  assert.match(html,/class="secondary" data-result="0"/);
  assert.match(html,/class="secondary" data-result="1"/);
});

test('recommended and manual version actions both open the exact original confirmation dialog', async () => {
  const results=[film({title:'A.720p',link:'magnet:first',size:GB,seeders:2}),
    film({title:'Z.1080p',link:'magnet:recommended',size:3*GB,seeders:30}),
    film({title:'Other.1080p',library_title:'Other',link:'magnet:other',seeders:5})];
  const app=cardFixture(results,{sort:'smallest'});app.context.renderResults();
  const index=Number(app.output.innerHTML.match(/class="primary" data-result="(\d+)"/)[1]);
  assert.equal(index,1);
  await app.click(index);await app.click(0);
  assert.equal(app.confirmations[0].link,'magnet:recommended');
  assert.equal(app.confirmations[0].size,3*GB);
  assert.equal(app.confirmations[1].link,'magnet:first');
  assert.equal(app.confirmations[1].size,GB);
});

test('filtered card recommendation preserves its original nonzero result index and escapes content', () => {
  const results=[film({title:'Example.2160p',seeders:100,source:'Hidden'}),
    film({title:'Example.1080p<script>',seeders:2,source:'A < B',link:'magnet:filtered'})];
  const app=cardFixture(results,{source:'A < B'});app.context.renderResults();
  assert.match(app.output.innerHTML,/class="primary" data-result="1"/);
  assert.doesNotMatch(app.output.innerHTML,/data-result="0"/);
  assert.match(app.output.innerHTML,/A &#60; B/);
  assert.doesNotMatch(app.output.innerHTML,/<script>/);
});

test('TVmaze attribution links only the verified metadata provider show URL', () => {
  const result=film({kind:'tv',season:1,episode:1,metadata_source:'TVmaze',metadata_url:'https://www.tvmaze.com/shows/123'});
  const app=cardFixture([result]);app.context.renderResults();
  assert.match(app.output.innerHTML,/href="https:\/\/www\.tvmaze\.com\/shows\/123"/);
  assert.match(app.output.innerHTML,/Seriegegevens: TVmaze/);
  for(const metadata_url of ['https://evil.test/shows/123','https://www.tvmaze.com.evil.test/shows/123',
    'javascript:alert(1)','https://www.tvmaze.com/shows/123?redirect=evil','http://www.tvmaze.com/shows/123']) {
    const invalid=cardFixture([{...result,metadata_url}]);invalid.context.renderResults();
    assert.doesNotMatch(invalid.output.innerHTML,/Seriegegevens: TVmaze/);
  }
  const other=cardFixture([{...result,metadata_source:'Unverified'}]);other.context.renderResults();
  assert.doesNotMatch(other.output.innerHTML,/Seriegegevens: TVmaze/);
});
