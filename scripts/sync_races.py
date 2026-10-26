#!/usr/bin/env python3
"""RUN QUEST weekly race import. Public metadata only; no authentication bypass.

The HTML site is static. This command refreshes the canonical store and re-embeds
its data into index.html, making a newly committed/deployed file self-contained.
"""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent.parent
USER_AGENT = 'URPACE-BetaRaceIndexer/0.9 (+contact: website administrator; respects robots.txt)'
HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/ld+json;q=0.9'}
MAX_BODY = 3_000_000
MAX_EVENTS_PER_SOURCE = 500
MO = {'january':1,'jan':1,'february':2,'feb':2,'march':3,'mar':3,'april':4,'apr':4,
      'may':5,'june':6,'jun':6,'july':7,'jul':7,'august':8,'aug':8,'september':9,'sep':9,
      'october':10,'oct':10,'november':11,'nov':11,'december':12,'dec':12,
      'มกราคม':1,'ม.ค.':1,'กุมภาพันธ์':2,'ก.พ.':2,'มีนาคม':3,'มี.ค.':3,'เมษายน':4,'เม.ย.':4,
      'พฤษภาคม':5,'พ.ค.':5,'มิถุนายน':6,'มิ.ย.':6,'กรกฎาคม':7,'ก.ค.':7,'สิงหาคม':8,'ส.ค.':8,
      'กันยายน':9,'ก.ย.':9,'ตุลาคม':10,'ต.ค.':10,'พฤศจิกายน':11,'พ.ย.':11,'ธันวาคม':12,'ธ.ค.':12}
MOKEYS = '|'.join(re.escape(x) for x in sorted(MO, key=len, reverse=True))
ISO_DATE = re.compile(r'\b(20\d\d)-([01]?\d)-([0-3]?\d)(?=\D|$)')
TH_DATE = re.compile(r'\b([0-3]?\d)\s*('+MOKEYS+r')\s*[,.]?\s*(20\d\d|25\d\d)\b',re.I)
EN_DATE = re.compile(r'\b('+MOKEYS+r')\s+([0-3]?\d)\s*,?\s*(20\d\d)\b',re.I)
YEAR = re.compile(r'\b(20\d\d|25\d\d)\b')
DIST = re.compile(r'\b(42\.195|42\.2|42|21\.0975|21\.1|21|10\.5|10|5|3|2\.5|2|1)\b')
PROVINCES = ['กรุงเทพมหานคร','กรุงเทพฯ','กรุงเทพ','Bangkok','เชียงใหม่','เชียงราย','ภูเก็ต','Phuket','ชลบุรี','Pattaya','พัทยา','ขอนแก่น','นครราชสีมา','บุรีรัมย์','ลำปาง','น่าน','นครปฐม','นครสวรรค์','อุตรดิตถ์','สมุทรปราการ','สมุทรสาคร','เพชรบุรี','เพชรบูรณ์','นครนายก','อยุธยา','พระนครศรีอยุธยา','ระยอง','สุราษฎร์ธานี','สงขลา','หาดใหญ่','กาญจนบุรี','สุโขทัย','พิษณุโลก','อุดรธานี','หนองคาย','ลพบุรี','อ่างทอง','กระบี่','นครศรีธรรมราช','สระบุรี','ระนอง','พังงา','ประจวบคีรีขันธ์','ตาก','แม่ฮ่องสอน','ปทุมธานี','ปราจีนบุรี','สระแก้ว','จันทบุรี','ฉะเชิงเทรา','ตราด','ตรัง','สตูล','เลย','อุบลราชธานี','มหาสารคาม','ยโสธร','หนองบัวลำภู','พะเยา','แพร่','ลำพูน','กำแพงเพชร','ชัยภูมิ','ศรีสะเกษ','ร้อยเอ็ด','มุกดาหาร','สกลนคร','นครพนม','กาฬสินธุ์','สุรินทร์','อำนาจเจริญ','นครปฐม','ราชบุรี','สุพรรณบุรี','สิงห์บุรี','ชัยนาท','อุทัยธานี','สุราษฎร์ธานี','ชุมพร','ปัตตานี','ยะลา','นราธิวาส','พัทลุง']


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def dump_json(path, obj): Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def norm(s):
    s = unicodedata.normalize('NFKC',str(s or '')).lower()
    s = re.sub(r'\b(?:20\d\d|25\d\d|ครั้งที่\s*\d+)\b',' ',s)
    return re.sub(r'[^a-z0-9\u0e00-\u0e7f]+','',s)
def canonical_url(u):
    if not u:return ''
    u=urldefrag(str(u).strip())[0]
    return re.sub(r'/+$','',u).lower().replace('http://','https://',1)
def parse_date(txt):
    if not txt:return ''
    t=str(txt)
    m=ISO_DATE.search(t)
    if m:
        try:return dt.date(int(m[1]),int(m[2]),int(m[3])).isoformat()
        except ValueError:return ''
    m=TH_DATE.search(t) or EN_DATE.search(t)
    if m:
        if m.re is TH_DATE: day,mon,yr=int(m[1]),MO[m[2].lower()],int(m[3])
        else:mon,day,yr=MO[m[1].lower()],int(m[2]),int(m[3])
        if yr>2400:yr-=543
        try:return dt.date(yr,mon,day).isoformat()
        except ValueError:return ''
    return ''
def province_from(text):
    t=str(text or '').lower()
    for p in PROVINCES:
        if p.lower() in t:return 'กรุงเทพมหานคร' if p in ('กรุงเทพฯ','กรุงเทพ','Bangkok') else p
    return ''
def classify(name,desc):
    t=(name+' '+desc).lower()
    if 'trail' in t or 'เทรล' in t:return 'Trail'
    if 'ultra' in t or 'อัลตร้า' in t:return 'Ultra'
    if 'night' in t or 'ไนท์' in t:return 'Night Run'
    if 'fun run' in t or 'ฟันรัน' in t:return 'Fun Run'
    return 'Road'
def num_distances(text):
    # Only consume explicit numeric lists, never guess categories from race names.
    # Keep uncommon distances (6/12/30km etc), and reject non-distance text.
    parts = re.split(r'[\s/;,|]+', str(text or '').strip().replace('KM','').replace('km',''))
    vals=[]
    for raw in parts:
        raw=raw.strip()
        if not re.fullmatch(r'(?:\d{1,3})(?:\.\d{1,4})?',raw): continue
        v=float(raw)
        if not (0.5<=v<=250): continue
        if v in (42.0,42.2):v=42.195
        elif v in (21.0,21.0975):v=21.1
        if v not in vals:vals.append(v)
    return sorted(vals)
def safe_external(href,base):
    u=urljoin(base,href or '')
    if urlparse(u).scheme not in ('https','http'):return ''
    return u


def event(name,date,url,source,province='',venue='',distances=None,desc='',race_type='',end='',register=''):
    name=' '.join(str(name).split())[:170]
    day=parse_date(date)
    if not 3<=len(name) or not day or not url or len(name)>170:return None
    if not safe_external(url,source['url']):return None
    if not 2025<=int(day[:4])<=2031:return None
    if len(name)<5 and not re.search(r'run|วิ่ง',name,re.I):return None
    dists=[float(x) for x in (distances or []) if 0<float(x)<=250]
    return {'name':name,'date':day,'end':parse_date(end) or day,'province':str(province)[:90],
            'venue':str(venue)[:200], 'type':race_type or classify(name,desc),'distances':sorted(set(dists)),
            'url':safe_external(url,source['url']),'registration_url':safe_external(register,source['url']) if register else '',
            'source_id':source['id'],'source_name':source['name'],'source_url':source['url'],'note':str(desc)[:280]}


def flatten_jsonld(value):
    if isinstance(value,list):
        for child in value:yield from flatten_jsonld(child)
    elif isinstance(value,dict):
        if isinstance(value.get('@graph'),list):yield from flatten_jsonld(value['@graph'])
        yield value
        if isinstance(value.get('subEvent'),(list,dict)):yield from flatten_jsonld(value['subEvent'])


def parse_jsonld(html,source):
    soup=BeautifulSoup(html,'html.parser');out=[]
    for node in soup.select('script[type="application/ld+json"]'):
        try:raw=json.loads(node.string or node.get_text())
        except (ValueError,TypeError):continue
        for obj in flatten_jsonld(raw):
            typ=obj.get('@type',[]); typ=[typ] if isinstance(typ,str) else typ
            if not any(str(x).lower().endswith('event') and str(x).lower() not in ('eventstatus','eventattendance') for x in typ):continue
            place=obj.get('location') or {};
            if isinstance(place,list):place=place[0] if place else {}
            if isinstance(place,str):place={'name':place}
            if not isinstance(place,dict):place={}
            a=place.get('address') or {}
            if isinstance(a,str):a={'streetAddress':a}
            if not isinstance(a,dict):a={}
            desc=str(obj.get('description') or '')
            org=obj.get('organizer') or {}; registration=obj.get('offers') or []
            if isinstance(registration,dict):registration=[registration]
            reg=next((o.get('url') for o in registration if isinstance(o,dict) and o.get('url')),'')
            place_name=place.get('name') or a.get('streetAddress') or ''
            province=a.get('addressRegion') or province_from(place_name+' '+str(a))
            web_url=obj.get('url') or source['url']
            if isinstance(web_url,list):web_url=web_url[0] if web_url else source['url']
            e=event(obj.get('name') or '',obj.get('startDate'),web_url,source,province,place_name,
                  [],desc,end=obj.get('endDate') or '',register=reg)
            if e:out.append(e)
    return out


def parse_jogandjoy(html,source):
    soup=BeautifulSoup(html,'html.parser');out=[];month=0;year=0
    for element in soup.find_all(['h2','h3','h4','h5','tr']):
        txt=element.get_text(' ',strip=True)
        if element.name!='tr':
            m=re.search(r'('+MOKEYS+r')\s+(20\d\d|25\d\d)',txt,re.I)
            if m:month=MO[m[1].lower()];year=int(m[2]);year-=543 if year>2400 else 0
            continue
        cells=element.find_all(['td','th'],recursive=False)
        if len(cells)<4:continue
        first=cells[0].get_text(' ',strip=True)
        if not re.match(r'^\d{1,2}(?:\s*[-–]\s*\d{1,2})?$',first):continue
        # Some pages combine section header/month as a table caption rather than H4.
        if not month or not year:
            p=element.find_previous(string=re.compile(r'('+MOKEYS+r')\s+20\d\d',re.I))
            if p:
                m=re.search(r'('+MOKEYS+r')\s+(20\d\d)',str(p),re.I)
                if m:month=MO[m[1].lower()];year=int(m[2])
        if not month or not year:continue
        try:day=dt.date(year,month,int(re.match(r'\d+',first)[0])).isoformat()
        except ValueError:continue
        date_end=day
        rm=re.match(r'^\d{1,2}\s*[-–]\s*(\d{1,2})$',first)
        if rm:
            try:date_end=dt.date(year,month,int(rm[1])).isoformat()
            except ValueError:date_end=day
        race_name=cells[1].get_text(' ',strip=True)
        link=cells[1].find('a',href=True)
        # Some organizers publish only on the calendar. Keep their listed event
        # with the exact calendar URL as provenance, never invent a booking link.
        origin=safe_external(link['href'],source['url']) if link else source['url']
        distances=num_distances(cells[2].get_text(' ',strip=True))
        province=cells[3].get_text(' ',strip=True)
        org=cells[4].get_text(' ',strip=True) if len(cells)>=5 else ''
        e=event(race_name,day,origin,source,province=province,distances=distances,desc='Organizer: '+org,end=date_end)
        if e:out.append(e)
    return out


def runlah_event_dates(text):
    """Read date ranges first so a 13–15 Nov race starts on the 13th."""
    raw=' '.join(str(text or '').split())
    month_pattern=MOKEYS
    th_range=re.search(r'\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s+('+month_pattern+r')\s+(20\d\d|25\d\d)\b',raw,re.I)
    if th_range:
        first=parse_date(f"{th_range[1]} {th_range[3]} {th_range[4]}")
        last=parse_date(f"{th_range[2]} {th_range[3]} {th_range[4]}")
        if first and last and first<=last:return first,last,th_range.start(),th_range.end()
    ordinary=TH_DATE.search(raw) or EN_DATE.search(raw) or ISO_DATE.search(raw)
    if ordinary:
        day=parse_date(ordinary.group(0))
        return (day,day,ordinary.start(),ordinary.end()) if day else ('','',0,0)
    return '','',0,0


def parse_runlah(html,source):
    """Read public race-card links with their *own* dates, not the page-wide calendar date."""
    soup=BeautifulSoup(html,'html.parser');out=[];seen=set()
    for link in soup.find_all('a',href=True):
        url=safe_external(link['href'],source['url'])
        p=urlparse(url)
        if p.netloc not in ('www.runlah.com','runlah.com') or not re.fullmatch(r'/(th|en)/[a-zA-Z0-9_-]{4,45}/?',p.path):continue
        if p.path.strip('/').split('/')[-1].lower() in {'account','login','results','promote','terms','register','calendar','settings'}:continue
        raw=' '.join(link.get_text(' ',strip=True).split())
        day,last,at,stop=runlah_event_dates(raw)
        context=raw
        # Some calendar layouts put the date beside the linked event title.
        if not day:
            node=link.parent
            for depth in range(4):
                if node is None or node.name in ('html','body'):break
                event_links=[x for x in node.find_all('a',href=True) if re.fullmatch(r'/(th|en)/[a-zA-Z0-9_-]{4,45}/?',urlparse(safe_external(x.get('href'),source['url'])).path)]
                if len(event_links)>1:break  # never attach another race's date to this link
                context=node.get_text(' ',strip=True)
                day,last,at,stop=runlah_event_dates(context)
                if day:break
                node=node.parent
        if not day or not (2025<=int(day[:4])<=2031):continue
        head=link.find(['h2','h3','h4','h5','strong'])
        title=' '.join(head.get_text(' ',strip=True).split()) if head else ''
        if not title:
            # A race card may be a single anchor: "Race name 21 พฤศจิกายน 2569 Venue".
            if runlah_event_dates(raw)[0]:
                title=raw[:runlah_event_dates(raw)[2]].strip(' •|–-')
            else:title=raw
        title=re.sub(r'^(?:ปิดรับสมัคร|เปิดรับสมัคร|Registration closed|Register now)\s*[:·-]?\s*','',title,flags=re.I).strip()
        if not 5<=len(title)<=170 or parse_date(title):continue
        if title.lower() in ('รายละเอียด','สมัครเลย!','register','details','ดูรายละเอียด','read more'):continue
        key=(canonical_url(url),day)
        if key in seen:continue
        seen.add(key)
        e=event(title,day,url,source,province_from(context),desc='',race_type=classify(title,context),end=last)
        if e:out.append(e)
    return out



def parse_wordpress(html,source):
    out=parse_jsonld(html,source)
    if out:return out
    soup=BeautifulSoup(html,'html.parser')
    for block in soup.select('.tribe-events-calendar-list__event, .mec-event-article, .eventon_list_event'):
        name_link=block.select_one('h3 a[href], h2 a[href], a[href*="event"]')
        if not name_link:continue
        txt=block.get_text(' ',strip=True)
        dates=block.select_one('time[datetime]')
        day=dates.get('datetime') if dates else txt
        e=event(name_link.get_text(' ',strip=True),day,safe_external(name_link['href'],source['url']),source,province_from(txt),desc='')
        if e:out.append(e)
    return out


def extract(html,source):
    method=source['method']
    if method=='jogandjoy':found=parse_jogandjoy(html,source)
    elif method=='runlah':found=parse_runlah(html,source)
    elif method=='wordpress':found=parse_wordpress(html,source)
    else:found=parse_jsonld(html,source)
    # Include structured data fallback for all supported layouts.
    if method!='jsonld':found.extend(parse_jsonld(html,source))
    dedup={}
    for e in found:
        key=(norm(e['name']),e['date'],canonical_url(e['url']))
        if key not in dedup:dedup[key]=e
    return list(dedup.values())[:MAX_EVENTS_PER_SOURCE]


def allowed_by_robots(session,url):
    p=urlparse(url); robots=f'{p.scheme}://{p.netloc}/robots.txt'
    try:
        res=session.get(robots,timeout=(5,7),headers=HEADERS,allow_redirects=False)
        if res.status_code==404:return True,'robots.txt absent'
        if res.status_code in (401,403):return False,'robots.txt denied'
        if res.status_code!=200:return False,f'robots.txt HTTP {res.status_code}'
        if len(res.content)>300_000:return False,'robots.txt too large'
        rp=RobotFileParser();rp.parse(res.text.splitlines())
        return rp.can_fetch(USER_AGENT,url), 'robots checked'
    except requests.RequestException as exc:return False, f'robots check failed: {type(exc).__name__}'


def fetch(session,source,fixture_dir=None):
    if fixture_dir:
        file=Path(fixture_dir)/(source['id']+'.html')
        if not file.exists():return None,'no fixture'
        return file.read_text(encoding='utf-8'),'fixture'
    url=source['url']
    if urlparse(url).scheme!='https':return None,'https only'
    allowed,why=allowed_by_robots(session,url)
    if not allowed:return None,why
    try:
        res=session.get(url,headers=HEADERS,timeout=(5,10),allow_redirects=True,stream=True)
        res.raise_for_status()
        # Prevent fetching redirects to unknown external hosts.
        if urlparse(res.url).netloc!=urlparse(url).netloc:return None,'redirect outside registered host'
        if 'html' not in res.headers.get('Content-Type','text/html').lower():return None,'not HTML'
        blob=b''
        for chunk in res.iter_content(chunk_size=32768):
            blob+=chunk
            if len(blob)>MAX_BODY:return None,'page exceeds size limit'
        # iter_content() has already consumed the streamed body; accessing
        # res.apparent_encoding here would read res.content again and crash.
        # requests determines res.encoding from the HTTP charset when present.
        encoding=res.encoding or 'utf-8'
        try:return blob.decode(encoding,errors='replace'),'HTTP 200'
        except LookupError:return blob.decode('utf-8',errors='replace'),'HTTP 200'
    except requests.RequestException as exc:return None,f'fetch error: {type(exc).__name__}'


def norm_province(s):
    p=norm(s)
    return 'กรุงเทพมหานคร' if p in ('กทม','กรุงเทพ','กรุงเทพฯ','กรุงเทพมหานคร','bangkok') else p
def event_key(name,date,province):return (norm(name),date,norm_province(province))
def likely_same(existing,new):
    r=existing['race']; old_date=r.get('First race date') or r.get('Event start')
    old_year=str(old_date)[:4]
    if old_year!=new['date'][:4]:return 'different'
    old_dates={r.get('First race date'),r.get('Event start'),r.get('Event end')}
    old_dates.update(c.get('วันแข่งจริง') for c in existing.get('categories',[]))
    same_day=new['date'] in old_dates
    if not same_day:
        try:
            lo=dt.date.fromisoformat(r.get('Event start'));hi=dt.date.fromisoformat(r.get('Event end'))
            same_day=lo <= dt.date.fromisoformat(new['date']) <= hi
        except (ValueError,TypeError):pass
    a=norm(r.get('Event / งานวิ่ง'));b=norm(new['name'])
    if not a or not b:return 'different'
    known_urls=[canonical_url(x.get('source_url')) for x in existing.get('provenance',[])]
    # Same published event URL can announce a reschedule. Do not duplicate, but review date changes.
    same_name_score=difflib.SequenceMatcher(None,a,b).ratio()
    if canonical_url(new['url']) in known_urls and known_urls and same_name_score>=.85:return 'exact'
    if not same_day:return 'different'
    ap=norm_province(r.get('จังหวัด'));bp=norm_province(new['province'])
    if ap and bp and ap!=bp:return 'different'
    ratio=difflib.SequenceMatcher(None,a,b).ratio()
    if a==b and (ap==bp or not ap or not bp):return 'exact'
    if ratio>=.93 and ap and bp and ap==bp:return 'exact'
    if ratio>=.77 and (ap==bp or not ap or not bp):return 'review'
    return 'different'


def public_row(new,event_id,checked):
    d=new['date'];km=new['distances']
    return {'Event ID':event_id,'Event / งานวิ่ง':new['name'],'Event start':d,'Event end':new.get('end') or d,
            'First race date':d,'จังหวัด':new['province'],'จุดจัดงาน / Venue':new['venue'],
            'ประเภท':new['type'],'ระยะ (กม.)':', '.join('%g'%x for x in km),
            'สถานะรับสมัคร*':'ตรวจสอบกับต้นทาง','วันสิ้นสุดรับสมัคร**':'','ผู้จัด':'',
            'ชนิดแหล่งข้อมูล':'Imported public listing','URL แหล่งอ้างอิง':new['url'],
            'URL สมัคร':new['registration_url'],'ตรวจข้อมูลล่าสุด':checked,
            'ระดับการตรวจสอบ':'อัตโนมัติ — ยังไม่ยืนยันกับผู้จัด','หมายเหตุ':'ข้อมูลจาก '+new['source_name']+' · โปรดตรวจสอบรายละเอียดกับต้นทาง'}
def make_categories(new,event_id):
    return [{'Event ID':event_id,'ระยะ / Category':'%gK'%km,'วันแข่งจริง':new['date'] if new.get('end',new['date'])==new['date'] else '','เวลา Start (ICT)':'',
           'ระยะทาง (กม.)':'%g'%km,'Elevation gain (เมตร)':'','Cutoff (ชม.)':'','ค่าสมัคร (บาท)*':'',
           'ชนิดราคา / เงื่อนไข':'','URL อ้างอิง':new['url'],'หมายเหตุ':''} for km in new['distances']]

def merge(store,discovered,now):
    """Returns counters/review queue. Keep known dates/organizer links immutable automatically."""
    review=[];stats={'added':0,'updated':0,'unchanged':0,'review_count':0}
    for new in discovered:
        matches=[(e,likely_same(e,new)) for e in store['events']]
        exact=next((e for e,match in matches if match=='exact'),None)
        if exact:
            rec={'source_url':new['url'],'source_name':new['source_name'],'source_id':new['source_id'],
                 'first_seen':now,'last_seen':now,'data_origin':'auto_parse'}
            old=next((x for x in exact['provenance'] if canonical_url(x.get('source_url'))==canonical_url(new['url'])),None)
            if old:old['last_seen']=now;stats['unchanged']+=1
            else:exact['provenance'].append(rec);stats['updated']+=1
            exact['last_seen']=now
            old_dates={exact['race'].get('First race date'),exact['race'].get('Event start'),exact['race'].get('Event end')}
            if new['date'] not in old_dates:
                review.append({'incoming':new,'possible_matches':[exact['id']],
                     'reason':'Date changed on same source URL — verify with organizer before updating'});stats['review_count']+=1
            # Never overwrite verified event dates or authoritative organizer registration URLs using aggregators.
            if not exact['race'].get('จังหวัด') and new.get('province'):
                exact['race']['จังหวัด']=new['province'];stats['updated']+=1
            if not exact['race'].get('ระยะ (กม.)') and new.get('distances'):
                exact['race']['ระยะ (กม.)']=', '.join('%g'%x for x in new['distances'])
                if not exact['categories']:exact['categories']=make_categories(new,exact['id'])
            continue
        candidates=[e['id'] for e,match in matches if match=='review']
        if candidates:
            review.append({'incoming':new,'possible_matches':candidates,'reason':'name/date similarity - needs manual review'})
            stats['review_count']+=1
            continue
        digest=hashlib.sha256((norm(new['name'])+'|'+new['date']+'|'+norm(new['province'])).encode()).hexdigest()[:12]
        eid='RQ-'+digest
        if any(x['id']==eid for x in store['events']):
            review.append({'incoming':new,'possible_matches':[eid],'reason':'ID collision'});stats['review_count']+=1;continue
        newr=public_row(new,eid,now)
        store['events'].append({'id':eid,'race':newr,'categories':make_categories(new,eid),
                 'provenance':[{'source_url':new['url'],'source_name':new['source_name'],'source_id':new['source_id'],
                                'first_seen':now,'last_seen':now,'data_origin':'auto_parse'}],
                 'first_seen':now,'last_seen':now,'last_verified_at':None,'status':'auto_unverified'})
        stats['added']+=1
    return stats,review


def write_site(store,status,sources,root=BASE):
    cutoff=status.get('sync_date') or dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date().isoformat()
    # Public calendar excludes completed races. Keep all history in race_store.json.
    visible=[x for x in store['events'] if str(x['race'].get('Event end') or x['race'].get('First race date') or x['race'].get('Event start') or '')[:10]>=cutoff]
    races=[x['race'] for x in visible]
    cats=[c for x in visible for c in x['categories']]
    payload={'races':races,'categories':cats}
    dump_json(root/'data'/'site_payload.json',payload)
    s=(root/'index.html').read_text(encoding='utf-8')
    # Only update the designated data assignment, retaining all generator logic and inline fonts.
    pattern=r'const DATA=\{.*?\};(?=\s*const RUNQUEST_SYNC_META=)'
    repl='const DATA='+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';'
    patched,n=re.subn(pattern,lambda _:repl,s,count=1,flags=re.S)
    if n!=1:raise RuntimeError('site DATA assignment not found; aborting site update')
    # Embedded sync metadata controls visible status; always display last successful run explicitly.
    sync_blob='const RUNQUEST_SYNC_META='+json.dumps({'last_attempt':status.get('last_attempt'),
        'last_success':status.get('last_success'),'source_count':len(sources),
        'scanned':sum(1 for x in status.get('source_results',[]) if x.get('state')=='ok'),
        'source_results':status.get('source_results',[]),'review_count':status.get('review_count',0),
        'added':status.get('added',0),'mode':status.get('mode'),
        'sources_with_events':status.get('sources_with_events',0),
        'events_parsed':status.get('events_parsed',0),
        'future_events_parsed':status.get('future_events_parsed',0),
        'beta_gate':status.get('beta_gate',{})},ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';'
    patched,n=re.subn(r'const RUNQUEST_SYNC_META=\{.*?\};',lambda _:sync_blob,patched,count=1,flags=re.S)
    if n!=1:raise RuntimeError('RUNQUEST_SYNC_META assignment not found')
    src_blob='const RUNQUEST_SOURCES='+json.dumps([{'id':v['id'],'name':v['name'],
        'url':v['url'],'method':v['method'],'enabled':v['enabled']} for v in sources],
        ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';'
    patched,n=re.subn(r'const RUNQUEST_SOURCES=\[.*?\];',lambda _:src_blob,patched,count=1,flags=re.S)
    if n!=1:raise RuntimeError('RUNQUEST_SOURCES assignment not found')
    (root/'index.html').write_text(patched,encoding='utf-8')
    return len(races),len(cats)


def run(root=BASE,fixture_dir=None,only=None,no_network=False):
    sources=read_json(root/'data'/'sources.json')
    store=read_json(root/'data'/'race_store.json')
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date().isoformat()
    # All event visibility cutoffs use the sync date in Thailand.
    
    stamp=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    status=read_json(root/'data'/'sync_status.json')
    session=requests.Session();results=[];found=[]
    for source in sources:
        if only and source['id'] not in only:continue
        if not source['enabled']:
            results.append({'id':source['id'],'name':source['name'],'state':'manual','count':0,'note':source['method']})
            continue
        if no_network and not fixture_dir:
            results.append({'id':source['id'],'name':source['name'],'state':'not_checked','count':0,'note':'offline mode'})
            continue
        urls=[source['url']]
        if source['method']=='runlah' and not fixture_dir:
            # Use actual server-rendered type calendars, not JS-loading homepage.
            # Each page is checked against robots.txt; limit request rate.
            urls+=source.get('additional_urls',[])[:5]
        all_events=[];reports=[];successful_pages=0
        for target_url in urls:
            page_source={**source,'url':target_url}
            html,why=fetch(session,page_source,fixture_dir)
            if html is None:
                reports.append(f"{target_url}: {why}")
            else:
                try:
                    events=extract(html,page_source)
                    if source['method']=='runlah' and not events:
                        diag_soup=BeautifulSoup(html,'html.parser')
                        anchors=diag_soup.find_all('a',href=True)
                        examples=[]
                        for a_tag in anchors:
                            h=urlparse(safe_external(a_tag.get('href',''),target_url)).path
                            if h.startswith('/th/') or h.startswith('/en/'):
                                examples.append({'path':h[:75],
                                  'text':a_tag.get_text(' ',strip=True)[:65],
                                  'parent_tag':a_tag.parent.name if a_tag.parent else '',
                                  'has_date':bool(runlah_event_dates(a_tag.get_text(' ',strip=True))[0])})
                            if len(examples)>=8:break
                        print('RUNLAH_PARSER_DIAG '+json.dumps({
                          'page':target_url,'bytes':len(html),'anchor_count':len(anchors),
                          'page_title':diag_soup.title.get_text(' ',strip=True)[:80] if diag_soup.title else '',
                          'script_tags':len(diag_soup.find_all('script')),
                          'next_data':'__NEXT_DATA__' in html,'nuxt_data':'__NUXT__' in html,
                          'body_text_prefix':diag_soup.get_text(' ',strip=True)[:130],
                          'examples':examples},ensure_ascii=False))
                    successful_pages+=1
                    all_events.extend(events)
                    reports.append(f"{target_url}: {len(events)} events")
                except Exception as exc:
                    reports.append(f"{target_url}: {type(exc).__name__}: {str(exc)[:80]}")
            if not fixture_dir:time.sleep(1.0)
        unique={}
        for e in all_events:
            key=(canonical_url(e['url']),e['date'])
            if key not in unique:unique[key]=e
        events=list(unique.values())
        future=[e for e in events if (e.get('end') or e['date'])>=now]
        found.extend(future)  # Do not add old races discovered in calendars.
        results.append({'id':source['id'],'name':source['name'],
            'state':'ok' if events else ('empty' if successful_pages else 'skipped'),
            'count':len(events),'future_count':len(future),
            'pages_checked':successful_pages,'pages_requested':len(urls),
            'note':'; '.join(reports)[:650]})
    counters,review=merge(store,found,now)
    status['sync_date']=now
    status.update({'last_attempt':stamp,'mode':'fixture_test' if fixture_dir else ('offline' if no_network else 'scheduled'),
                   'source_count':len(sources),'source_results':results,
                   'sources_with_events':sum(x['state']=='ok' for x in results),
                   'events_parsed':len(found),'future_events_parsed':sum(x.get('future_count',0) for x in results),
                   **counters})
    # Success requires at least one *future* event actually parsed from live HTML.
    # HTTP 200 / empty event pages must not count as successful race updates.
    if not fixture_dir and not no_network and any(x.get('future_count',0)>0 for x in results):
        status['last_success']=stamp
    if fixture_dir:status['last_fixture_test']=stamp
    dump_json(root/'data'/'race_store.json',store)
    dump_json(root/'data'/'sync_status.json',status)
    dump_json(root/'data'/'review_queue.json',review)
    counts=write_site(store,status,sources,root)
    upcoming=[e for e in store['events'] if (e['race'].get('Event end') or e['race'].get('Event start') or '')>=now]
    live_sources={src['id'] for src in results if src.get('future_count',0)>0} if not fixture_dir and not no_network else set()
    # 60 events / 2 live feeds are release *policy*, not evidence of full coverage.
    # Offline and fixture runs can never mark a release ready.
    status['beta_gate']={'ready': bool(status.get('last_success') and len(upcoming)>=60 and len(live_sources)>=2 and not fixture_dir and not no_network),
                         'upcoming_events':len(upcoming),'min_upcoming_events':60,'live_sources_this_run':len(live_sources),'min_live_sources':2,
                         'rule':'UR.PACE beta release gate; not a guarantee of completeness'}
    dump_json(root/'data'/'sync_status.json',status)
    # Status is updated after gate evaluation; persist it in the web page, too.
    counts=write_site(store,status,sources,root)
    print(json.dumps({'races':counts[0],'categories':counts[1],'found':len(found),**counters,
                      'checked':sum(x['state']=='ok' for x in results),'skipped':sum(x['state']!='ok' for x in results)},ensure_ascii=False))
    return status


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--fixture-dir',help='Offline example responses (source-001.html etc)')
    ap.add_argument('--only',help='Source IDs to scan, comma-separated')
    ap.add_argument('--offline',action='store_true',help='Do not make network requests; rebuild site from store')
    args=ap.parse_args()
    run(fixture_dir=args.fixture_dir,only=set(args.only.split(',')) if args.only else None,no_network=args.offline)
if __name__=='__main__':main()
