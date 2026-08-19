#!/usr/bin/env python3
import csv,json,re,time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
BASE='https://www.timeform.com';INDEX_URL=BASE+'/greyhound-racing/racecards'
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0 Safari/537.36','Accept-Language':'en-GB,en;q=0.9','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Cache-Control':'no-cache','Pragma':'no-cache'}
session=requests.Session();session.headers.update(HEADERS)
def clean(v):return re.sub(r'\s+',' ',str(v or '')).strip()
def display_name(v):
 v=clean(v);return ' '.join(p.title() if p.isupper() else p for p in v.split())
def get(url,timeout=30):
 r=session.get(url,timeout=timeout,allow_redirects=True);r.raise_for_status();return r
def walk(obj):
 if isinstance(obj,dict):
  yield obj
  for v in obj.values():yield from walk(v)
 elif isinstance(obj,list):
  for v in obj:yield from walk(v)
def json_roots(html):
 soup=BeautifulSoup(html,'html.parser');roots=[]
 for s in soup.find_all('script'):
  txt=(s.string or s.get_text() or '').strip();typ=(s.get('type') or '').lower()
  if txt and (typ in ('application/json','application/ld+json') or txt.startswith('{') or txt.startswith('[')):
   try:roots.append(json.loads(txt))
   except:pass
 return roots
def parse_race_url(url):
 m=re.search(r'/greyhound-racing/racecards/([^/]+)/(\d{3,4})/(\d{4}-\d{2}-\d{2})/(\d+)',url,re.I)
 if not m:return None
 slug,hhmm,date_s,race_id=m.groups();hhmm=hhmm.zfill(4)
 return {'Date':date_s,'Track':slug.replace('-',' ').title(),'RaceTime':hhmm[:2]+':'+hhmm[2:],'RaceID':race_id,'RaceURL':url}
def discover_races(date_s):
 html=get(INDEX_URL).text;refs={}
 def add(url):
  full=urljoin(BASE,url);p=parse_race_url(full)
  if p and p['Date']==date_s:refs[full]=p
 soup=BeautifulSoup(html,'html.parser')
 for a in soup.find_all('a',href=True):
  if '/greyhound-racing/racecards/' in (a.get('href') or ''):add(a['href'])
 for m in re.finditer(r'["\']([^"\']*/greyhound-racing/racecards/[^"\']+)["\']',html,re.I):add(m.group(1).replace('\\/','/'))
 for root in json_roots(html):
  for item in walk(root):
   if not isinstance(item,dict):continue
   for k in ('url','href','raceUrl','raceURL','link'):
    v=item.get(k)
    if isinstance(v,str) and '/greyhound-racing/racecards/' in v:add(v)
 return sorted(refs.values(),key=lambda x:(x['Track'],x['RaceTime'],x['RaceID']))
def extract_distance_grade(text):
 m=re.search(r'\bThe\s+(\d{3,4}m)\s+\d{1,2}:\d{2}\s+([A-Z]{1,3}\d{0,2}|OR|OPEN|HCP)\b',text,re.I)
 if m:return m.group(1),m.group(2).upper()
 dm=re.search(r'\b(\d{3,4})\s*m\b',text,re.I);gm=re.search(r'\b((?:A|D|S|H|P)\d{1,2}|OR|OPEN|HCP)\b',text,re.I)
 return ((dm.group(1)+'m') if dm else '',gm.group(1).upper() if gm else '')
def extract_verdict(text):
 m=re.search(r"Analyst(?:'s)?\s+Verdict\s+1\.\s*(.+?)\s+Bet\s*[→>-]+\s*2\.\s*(.+?)\s+Bet\s*[→>-]+\s*3\.\s*(.+?)\s+Bet\s*[→>-]+",text,re.I|re.S)
 if not m:return '','',''
 return tuple(display_name(clean(v)) for v in m.groups())
def extract_analysis(text):
 narrative='';forecast='';smart=''
 m=re.search(r"Analyst(?:'s)?\s+Verdict\s+1\..+?\s+Bet\s*[→>-]+\s*2\..+?\s+Bet\s*[→>-]+\s*3\..+?\s+Bet\s*[→>-]+\s*(.+?)(?=\s+FC:|\s+TC:|\s+Betting Forecast:|\s+Smart Stats|\s+\d{1,2}:\d{2}\s+\w+\s+Racecard)",text,re.I|re.S)
 if m:narrative=clean(m.group(1))
 m=re.search(r'Betting Forecast:\s*(.+?)(?=\s+Smart Stats|\s+\d{1,2}:\d{2}\s+.+?\s+Racecard|$)',text,re.I|re.S)
 if m:forecast=clean(m.group(1))
 m=re.search(r'Smart Stats\s+(.+?)(?=\s+\d{1,2}:\d{2}\s+.+?\s+Racecard|$)',text,re.I|re.S)
 if m:smart=clean(m.group(1))
 return narrative,forecast,smart
def parse_race(ref):
 soup=BeautifulSoup(get(ref['RaceURL']).text,'html.parser');text=clean(soup.get_text(' ',strip=True));distance,grade=extract_distance_grade(text);v1,v2,v3=extract_verdict(text);narr,forecast,smart=extract_analysis(text);issues=[]
 if not (v1 and v2 and v3):issues.append('VERDICT_INCOMPLETE')
 if not distance:issues.append('DISTANCE_MISSING')
 if not grade:issues.append('GRADE_MISSING')
 return {**ref,'Distance':distance,'Grade':grade,'AnalystVerdict1':v1,'AnalystVerdict2':v2,'AnalystVerdict3':v3,'AnalystNarrative':narr,'BettingForecast':forecast,'SmartStats':smart,'Status':'COMPLETE' if not issues else 'CHECK','Issues':';'.join(issues)}
def main():
 today=datetime.now().astimezone().strftime('%Y-%m-%d');out=Path(__file__).resolve().parent/f'timeform_races_{today}.csv';refs=discover_races(today)
 if not refs:raise SystemExit(f'No Timeform greyhound races discovered for {today}')
 rows=[]
 for i,ref in enumerate(refs,1):
  print(f"[{i}/{len(refs)}] {ref['Track']} {ref['RaceTime']}",flush=True)
  try:rows.append(parse_race(ref))
  except Exception as e:rows.append({**ref,'Distance':'','Grade':'','AnalystVerdict1':'','AnalystVerdict2':'','AnalystVerdict3':'','AnalystNarrative':'','BettingForecast':'','SmartStats':'','Status':'FAILED','Issues':repr(e)})
  time.sleep(.35)
 fields=['Date','Track','RaceTime','RaceID','RaceURL','Distance','Grade','AnalystVerdict1','AnalystVerdict2','AnalystVerdict3','AnalystNarrative','BettingForecast','SmartStats','Status','Issues']
 with out.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 print(f'Races: {len(rows)} | Complete: {sum(r["Status"]=="COMPLETE" for r in rows)}')
if __name__=='__main__':main()
