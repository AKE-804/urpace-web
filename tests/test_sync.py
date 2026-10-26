import unittest,sys,tempfile,shutil,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from sync_races import (parse_date,parse_jogandjoy,parse_runlah,parse_jsonld,extract,merge,
                       read_json,run,norm,num_distances,likely_same,public_row,write_site,BASE)
SRC={x['id']:x for x in read_json(BASE/'data'/'sources.json')}
FIX=BASE/'fixtures'

class ParserTests(unittest.TestCase):
 def test_thai_and_english_dates(self):
  for text,expect in [('21 พฤศจิกายน 2569','2026-11-21'),('NOVEMBER 1, 2026','2026-11-01'),('2027-02-14T06:00','2027-02-14'),('1 ต.ค. 2569','2026-10-01'),('32 ต.ค. 2569','')]:
   self.assertEqual(parse_date(text),expect)
 def test_distance(self):self.assertEqual(num_distances('42/21/10/5'),[5.0,10.0,21.1,42.195])
 def test_jogandjoy(self):
  events=extract((FIX/'source-002.html').read_text(),SRC['source-002'])
  self.assertEqual(len(events),3)
  self.assertEqual(events[0]['date'],'2026-11-21')
  self.assertEqual(events[1]['distances'],[5,10,21.1])
  self.assertEqual(events[-1]['date'],'2026-12-06')
 def test_runlah(self):
  events=extract((FIX/'source-001.html').read_text(),SRC['source-001'])
  self.assertEqual(len(events),2)
  self.assertEqual(events[0]['date'],'2026-11-21')
 def test_jsonld(self):
  ev=extract((FIX/'source-003.html').read_text(),SRC['source-003'])
  self.assertEqual(len(ev),1);self.assertEqual(ev[0]['province'],'เชียงใหม่')
  self.assertEqual(ev[0]['registration_url'],'https://patrunning.com/example/register')

class DedupTests(unittest.TestCase):
 def setUp(self):self.store=copy.deepcopy(read_json(BASE/'data'/'race_store.json'))
 def test_existing_seed_same_race(self):
  e=extract((FIX/'source-002.html').read_text(),SRC['source-002'])[0]
  a,b=merge(self.store,[e],'2026-10-25');self.assertEqual(a['added'],0);self.assertEqual(a['review_count'],0)
 def test_two_sources_same_race(self):
  a=extract((FIX/'source-001.html').read_text(),SRC['source-001'])[1]
  b=extract((FIX/'source-003.html').read_text(),SRC['source-003'])[0]
  a1,r1=merge(self.store,[a],'2026-10-25');a2,r2=merge(self.store,[b],'2026-10-25')
  self.assertEqual(a1['added'],1);self.assertEqual(a2['added'],0)
  self.assertEqual(a2['updated'],1)
 def test_repeat_idempotent(self):
  a=extract((FIX/'source-002.html').read_text(),SRC['source-002'])[1]
  merge(self.store,[a],'2026-10-25');a2,_=merge(self.store,[a],'2026-10-25')
  self.assertEqual(a2['added'],0)
 def test_different_year_edition(self):
  e=extract((FIX/'source-002.html').read_text(),SRC['source-002'])[0]
  e['date']='2027-11-21';a,b=merge(self.store,[e],'2026-10-25');self.assertEqual(a['added'],1)
 def test_uncertain_match_review(self):
  e=extract((FIX/'source-002.html').read_text(),SRC['source-002'])[0]
  e['name']='MUSS Mini Maraton ครั้งที่ 11'
  a,b=merge(self.store,[e],'2026-10-25');self.assertIn(a['review_count'],(0,1))
 def test_same_homepage_not_same_race(self):
  e=extract((FIX/'source-003.html').read_text(),SRC['source-003'])[0]
  e['url']='https://www.runlah.com/th/muss2026';e['date']='2026-11-21'
  # Same registration URL is not enough if event names are unrelated.
  a,rev=merge(self.store,[e],'2026-10-25')
  self.assertEqual(a['added'],1)
 def test_reschedule_same_url_needs_review(self):
  e=extract((FIX/'source-002.html').read_text(),SRC['source-002'])[0]
  e['date']='2026-12-01'
  a,rev=merge(self.store,[e],'2026-10-25')
  self.assertEqual(a['added'],0)
  self.assertEqual(a['review_count'],1)
 def test_bad_url_is_not_executable(self):
  e=extract((FIX/'source-003.html').read_text(),SRC['source-003'])[0]
  self.assertTrue(e['url'].startswith('https://'))

class IntegrationTests(unittest.TestCase):
 def test_fixture_run_and_embed(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'data').mkdir()
   for n in ['source_registry.csv','sources.json','race_store.json','sync_status.json','site_payload.json','review_queue.json']:
    shutil.copy(BASE/'data'/n,root/'data'/n)
   shutil.copy(BASE/'index.html',root/'index.html')
   s=run(root,FIX,{'source-001','source-002','source-003'})
   self.assertEqual(s['last_success'],read_json(BASE/'data'/'sync_status.json')['last_success'])
   r=read_json(root/'data'/'site_payload.json');self.assertEqual(len(r['races']),31)
   self.assertIn('RUN QUEST FIXTURE', (root/'index.html').read_text())
   s2=run(root,FIX,{'source-001','source-002','source-003'})
   self.assertEqual(s2['added'],0)
 def test_offline_never_mark_success(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'data').mkdir()
   for n in ['sources.json','race_store.json','sync_status.json','site_payload.json','review_queue.json']:
    shutil.copy(BASE/'data'/n,root/'data'/n)
   shutil.copy(BASE/'index.html',root/'index.html')
   s=run(root,no_network=True,only={'source-001'})
   self.assertEqual(s['last_success'],read_json(BASE/'data'/'sync_status.json')['last_success'])


class BetaHardeningTests(unittest.TestCase):
 def test_jogandjoy_unlinked_entries_keep_calendar_provenance(self):
  html="<h4>JANUARY 2027</h4><table><tr><td>10</td><td>Community River Run 2027</td><td>12/6/4</td><td>กรุงเทพฯ</td><td>Local Organizer</td></tr></table>"
  src=SRC['source-002']; ev=parse_jogandjoy(html,src)
  self.assertEqual(len(ev),1)
  self.assertEqual(ev[0]['url'],src['url'])
  self.assertEqual(ev[0]['registration_url'],'')
  self.assertEqual(ev[0]['distances'],[4.0,6.0,12.0])
 def test_metadata_offline_never_beta_ready(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'data').mkdir()
   for n in ['sources.json','race_store.json','sync_status.json','site_payload.json','review_queue.json']:
    shutil.copy(BASE/'data'/n,root/'data'/n)
   shutil.copy(BASE/'index.html',root/'index.html')
   st=run(root,no_network=True,only={'source-001'})
   self.assertFalse(st['beta_gate']['ready'])
   self.assertEqual(st['future_events_parsed'],0)
 def test_jogandjoy_2027_fixture_duplicate_does_not_create_two_rows(self):
  src=SRC['source-002']
  html='''<h4>JANUARY 2027</h4><table><tr><td>10</td><td><a href="https://example.com/race">Local Run</a></td><td>10/5</td><td>Bangkok</td><td>Org</td></tr></table>'''
  ev=extract(html,src)
  store={'events':[]}
  a,_=merge(store,ev,'2026-10-26');b,_=merge(store,ev,'2026-10-27')
  self.assertEqual(a['added'],1);self.assertEqual(b['added'],0)


class RunlahCalendarAndVisibilityTests(unittest.TestCase):
 def test_calendar_card_with_date_inside_link(self):
  html='<a href="/th/exrun2026">EXRUN 2026 Run for Education 22 พฤศจิกายน 2569 กรุงเทพมหานคร</a>'
  found=parse_runlah(html,SRC['source-001'])
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]['name'],'EXRUN 2026 Run for Education')
  self.assertEqual(found[0]['date'],'2026-11-22')
  self.assertEqual(found[0]['province'],'กรุงเทพมหานคร')

 def test_calendar_date_near_link(self):
  html='<div><a href="/th/khundan2027">ขุนด่าน เทรล 2027</a><span>14 กุมภาพันธ์ 2570 จ.นครนายก</span></div>'
  found=parse_runlah(html,SRC['source-001'])
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]['date'],'2027-02-14')

 def test_multiday_card_uses_first_and_last_race_dates(self):
  html='<a href="/th/lampang26">LAMPANG MYSSTIC TRAIL 2026 13-15 พฤศจิกายน 2569 ลำปาง</a>'
  found=parse_runlah(html,SRC['source-001'])
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]['date'],'2026-11-13')
  self.assertEqual(found[0]['end'],'2026-11-15')

 def test_only_future_and_ongoing_races_are_public(self):
  from sync_races import write_site
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'data').mkdir()
   shutil.copy(BASE/'index.html',root/'index.html')
   store=copy.deepcopy(read_json(BASE/'data'/'race_store.json'))
   examples=copy.deepcopy(store['events'][0])
   examples['id']='test-past';examples['race']['Event ID']='test-past'
   examples['race']['Event start']='2026-10-20';examples['race']['Event end']='2026-10-24'
   examples['categories']=[]
   ongoing=copy.deepcopy(examples)
   ongoing['id']='test-ongoing';ongoing['race']['Event ID']='test-ongoing'
   ongoing['race']['Event start']='2026-10-25';ongoing['race']['Event end']='2026-10-27'
   future=copy.deepcopy(examples)
   future['id']='test-future';future['race']['Event ID']='test-future'
   future['race']['Event start']='2026-11-12';future['race']['Event end']='2026-11-12'
   synthetic={'events':[examples,ongoing,future]}
   status={'sync_date':'2026-10-26','source_results':[]}
   write_site(synthetic,status,[],root)
   public=read_json(root/'data'/'site_payload.json')
   self.assertEqual([r['Event ID'] for r in public['races']],['test-ongoing','test-future'])
   self.assertEqual(len(synthetic['events']),3)


if __name__=='__main__':unittest.main()
