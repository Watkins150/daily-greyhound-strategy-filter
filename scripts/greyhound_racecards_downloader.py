#!/usr/bin/env python3
"""
Greyhound Step 1 - Self-contained daily racecard downloader
Double-click this file on Windows.
"""
import csv,json,os,re,subprocess,sys,time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

def ensure_package(import_name,pip_name=None):
    try:return __import__(import_name)
    except ImportError:
        pip_name=pip_name or import_name
        subprocess.check_call([sys.executable,'-m','pip','install',pip_name]);return __import__(import_name)
requests=ensure_package('requests');ensure_package('bs4','beautifulsoup4')
from bs4 import BeautifulSoup
BASE='https://www.sportinglife.com';INDEX=BASE+'/greyhounds/racecards'
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0 Safari/537.36','Accept-Language':'en-GB,en;q=0.9','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
session=requests.Session();session.headers.update(HEADERS)
def clean_text(v):return re.sub(r'\s+',' ',str(v or '')).strip()
def get(url,timeout=25):
 r=session.get(url,timeout=timeout);r.raise_for_status();return r
def walk(obj):
 if isinstance(obj,dict):
  yield obj
  for v in obj.values():yield from walk(v)
 elif isinstance(obj,list):
  for v in obj:yield from walk(v)
def find_first(d,keys):
 for k in keys:
  if isinstance(d,dict) and k in d and d[k] not in (None,'',[]):return d[k]
def extract_json_scripts(html):
 soup=BeautifulSoup(html,'html.parser');out=[]
 for s in soup.find_all('script'):
  typ=(s.get('type') or '').lower();txt=(s.string or s.get_text() or '').strip()
  if txt and (typ=='application/json' or txt.startswith('{') or txt.startswith('[')):
   try:out.append(json.loads(txt))
   except:pass
 return out
def parse_index(date_str):
 html=get(INDEX).text;refs=[];seen=set()
 for root in extract_json_scripts(html):
  for d in walk(root):
   if not isinstance(d,dict):continue
   href=find_first(d,['url','href','raceUrl','race_url']);rid=find_first(d,['raceId','race_id','id']);track=find_first(d,['meetingName','meeting_name','venue','track','courseName','course']);tm=find_first(d,['raceTime','race_time','time','offTime','off_time'])
   hs=clean_text(href)
   if hs and '/greyhounds/racecards/' in hs:
    full=urljoin(BASE,hs)
    if re.search(r'/20\d{2}-\d{2}-\d{2}/',full) and date_str not in full:continue
    if full not in seen:
     seen.add(full);refs.append({'track':clean_text(track),'race_time':clean_text(tm),'race_id':clean_text(rid),'url':full})
 soup=BeautifulSoup(html,'html.parser')
 for a in soup.find_all('a',href=True):
  full=urljoin(BASE,a['href'])
  if '/greyhounds/racecards/' not in full or date_str not in full or full in seen:continue
  m=re.search(r'/greyhounds/racecards/(\d{4}-\d{2}-\d{2})/([^/]+)/racecard/(\d+)',full)
  if not m:continue
  text=clean_text(a.get_text(' ',strip=True));tm=re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b',text)
  refs.append({'track':m.group(2).replace('-',' ').title(),'race_time':tm.group(0) if tm else '','race_id':m.group(3),'url':full});seen.add(full)
 refs.sort(key=lambda x:(x['track'],x['race_time'],x['url']));return refs
def parse_runner_dicts(root):
 cand=[]
 for d in walk(root):
  if not isinstance(d,dict):continue
  num=find_first(d,['trapNumber','trap_number','trap','runnerNumber','runner_number','clothNumber','cloth_number','number']);name=find_first(d,['dogName','dog_name','runnerName','runner_name','greyhoundName','greyhound_name','name'])
  if num is None or name is None:continue
  m=re.search(r'\d+',clean_text(num));ns=clean_text(name)
  if not m:continue
  n=int(m.group())
  if not 1<=n<=8 or len(ns)<2 or ns.isdigit() or ns.lower() in {'racecard','runner','greyhound','dog','trap','reserve'}:continue
  cand.append((n,ns))
 out=[];seen=set()
 for n,name in cand:
  k=(n,name.lower())
  if k not in seen:seen.add(k);out.append({'runner_number':n,'dog_name':name})
 return out
def parse_race_page(ref,debug_dir):
 html=get(ref['url']).text;runners=[]
 for root in extract_json_scripts(html):runners.extend(parse_runner_dicts(root))
 by_num={}
 for x in runners:
  if x['runner_number'] not in by_num:by_num[x['runner_number']]=clean_text(x['dog_name'])
 runners=[{'runner_number':n,'dog_name':by_num[n]} for n in sorted(by_num)]
 if not runners:
  soup=BeautifulSoup(html,'html.parser');lines=[clean_text(x) for x in soup.stripped_strings];tmp={}
  for i,line in enumerate(lines[:-1]):
   if re.fullmatch(r'[1-8]',line):
    nxt=clean_text(lines[i+1])
    if 2<=len(nxt)<=60 and not re.search(r'\d{1,2}:\d{2}',nxt):tmp.setdefault(int(line),nxt)
  runners=[{'runner_number':n,'dog_name':tmp[n]} for n in sorted(tmp)]
 if not runners:(debug_dir/f"failed_{ref.get('race_id') or int(time.time())}.html").write_text(html,encoding='utf-8',errors='ignore')
 return runners
def main():
 today=datetime.now().astimezone().strftime('%Y-%m-%d');base_dir=Path(__file__).resolve().parent;debug_dir=base_dir/'scrape_debug';debug_dir.mkdir(exist_ok=True)
 racecards_csv=base_dir/f'greyhound_racecards_{today}.csv';audit_csv=base_dir/f'greyhound_racecard_audit_{today}.csv';refs=parse_index(today)
 if not refs:raise SystemExit(f'No current-day race links found for {today}')
 rows=[];audits=[]
 for idx,ref in enumerate(refs,1):
  print(f"[{idx}/{len(refs)}] {ref.get('track','?')} {ref.get('race_time','?')}",flush=True)
  try:
   runners=parse_race_page(ref,debug_dir)
   for x in runners:rows.append({'date':today,'track':ref.get('track',''),'race_time':ref.get('race_time',''),'runner_number':x['runner_number'],'dog_name':x['dog_name'],'race_id':ref.get('race_id',''),'source':'Sporting Life','race_url':ref.get('url','')})
   audits.append({'date':today,'track':ref.get('track',''),'race_time':ref.get('race_time',''),'race_id':ref.get('race_id',''),'status':'OK' if runners else 'FAILED','runner_rows':len(runners),'source':'Sporting Life','race_url':ref.get('url',''),'error':'' if runners else 'No runners parsed'})
  except Exception as e:audits.append({'date':today,'track':ref.get('track',''),'race_time':ref.get('race_time',''),'race_id':ref.get('race_id',''),'status':'FAILED','runner_rows':0,'source':'Sporting Life','race_url':ref.get('url',''),'error':repr(e)})
  time.sleep(.15)
 with racecards_csv.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=['date','track','race_time','runner_number','dog_name','race_id','source','race_url']);w.writeheader();w.writerows(rows)
 with audit_csv.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=['date','track','race_time','race_id','status','runner_rows','source','race_url','error']);w.writeheader();w.writerows(audits)
 print(f'Races: {len(refs)} | Runner rows: {len(rows)} | Failed races: {sum(a["status"]!="OK" for a in audits)}')
if __name__=='__main__':main()
