const test=require('node:test');
const assert=require('node:assert/strict');
const {identity,endpoint,safeMetadata}=require('../plexport/static/artwork.js');
test('artwork identity separates years and media kinds',()=>{
  assert.notEqual(identity('Example',2024,'movie'),identity('Example',1922,'movie'));
  assert.notEqual(identity('Example',2024,'movie'),identity('Example',2024,'tv'));
  assert.equal(identity(' Example ','2024','movie'),identity('Example',2024,'movie'));
});
test('artwork requests encode titles without changing the endpoint or query',()=>{
  const url=new URL(endpoint('A & B?/ <test>','2024','movie'),'http://localhost');
  assert.equal(url.pathname,'/api/artwork');
  assert.equal(url.searchParams.get('title'),'A & B?/ <test>');
  assert.equal(url.searchParams.get('year'),'2024');
  assert.equal(url.searchParams.size,3);
});
test('only cached local images and the verified source can enter the page',()=>{
  const valid={image_url:'/posters/'+'a'.repeat(64)+'.jpg',source_url:'https://watchsomuch.to/Movie/1234/Example-2024',source_name:'Anything'};
  assert.equal(safeMetadata(valid).source_name,'WatchSoMuch');
  for(const value of [null,{}, {...valid,image_url:'https://example.com/p.jpg'},{...valid,image_url:'/posters/../../settings'}, {...valid,source_url:'javascript:alert(1)'},{...valid,source_url:'https://watchsomuch.to.evil.example/Movie/1234/Example'},{...valid,source_url:'https://user:pass@watchsomuch.to/Movie/1234/Example'},{...valid,source_url:'https://watchsomuch.to:8443/Movie/1234/Example'},{...valid,source_url:'https://watchsomuch.to/Movie/1234/Example?redirect=1'}])assert.equal(safeMetadata(value),null);
});
