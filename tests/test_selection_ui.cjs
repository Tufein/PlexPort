const test = require('node:test');
const assert = require('node:assert/strict');
const { selectionPayload, fileDescription } = require('../plexport/static/selection.js');
const snapshot = { id:'task', metadata_token:'current-identity', files:[
  {index:8,name:'Show.S01E01.mkv',kind:'video',selectable:true,season:1,episodes:[1]},
  {index:2,name:'Show.S01E01.nl.srt',kind:'subtitle',selectable:true},
  {index:11,name:'readme.txt',kind:'other',selectable:false}
] };
test('submits actual downloader indices and current metadata token, without guessing order',()=>{
  assert.deepEqual(selectionPayload(snapshot,['8','2','8']),{id:'task',metadata_token:'current-identity',files:[8,2]});
  assert.equal(snapshot.files[0].index,8);
});
test('requires a video rather than accepting only a subtitle or no files',()=>{
  assert.throws(()=>selectionPayload(snapshot,['2']),/minstens/);
  assert.throws(()=>selectionPayload(snapshot,[]),/minstens/);
});
test('rejects stale file indices and files outside the supported selection',()=>{
  for(const list of [['8','99'],['8','11']])assert.throws(()=>selectionPayload(snapshot,list),/veranderd/);
  assert.throws(()=>selectionPayload({...snapshot,metadata_token:''},['8']),/opnieuw/);
});
test('rejects booleans, fractions and malformed indices instead of coercing them',()=>{
  for(const value of [true,null,-1,0.5,'8abc',''])assert.throws(()=>selectionPayload(snapshot,[value]),/Ongeldige/);
});
test('multi-episode files remain one file and unknown names do not invent episode numbers',()=>{
  assert.match(fileDescription({kind:'video',season:1,episodes:[1,2]}),/1, 2.*één videobestand/);
  assert.match(fileDescription({kind:'video'}),/niet herkend/);
  assert.match(fileDescription({kind:'subtitle'}),/apart kiezen/);
});
