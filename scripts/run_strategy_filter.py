import csv,json,re
from collections import defaultdict
from datetime import datetime
from fractions import Fraction
RACECARDS='racecards/latest_racecards.csv';AUDIT='racecards/latest_audit.csv';TIMEFORM='timeform/latest_timeform_races.csv';OUTPUT='strategy_filtered_tips.csv';OUTPUT2='strategy_filtered_tips_2.csv';DETAIL='strategy_filter_audit.csv';SUMMARY='strategy_filter_summary.json'
STRATEGIES={'Nottingham':{'name':'UK LAY Nottingham Trap 6','traps':{6:(1.01,100)}},'Central Park':{'name':'UK LAY Central Park Trap 3,4','traps':{3:(10,110),4:(10,110)}},'Monmore':{'name':'UK LAY Monmore Trap 2,5,6','traps':{2:(4,100),5:(4,100),6:(4,100)}},'Doncaster':{'name':'UK LAY Doncaster Trap 2,6','traps':{2:(6,120),6:(6,120)}},'Harlow':{'name':'UK LAY Harlow Trap 2,4','traps':{2:(12,100),4:(12,100)}},'Valley':{'name':'UK LAY Valley Trap 1,3,4','traps':{1:(4,100),3:(4,100),4:(4,100)}},'Romford':{'name':'UK LAY Romford Trap 1,2,6','traps':{1:(4,100),2:(4,100),6:(4,100)}},'Sunderland':{'name':'UK LAY Sunderland Trap 4','traps':{4:(9,100)}},'Towcester':{'name':'UK LAY Towcester Trap 1,5,6','traps':{1:(4,100),5:(4,100),6:(4,100)}},'Kinsley':{'name':'UK LAY Kinsley Trap 5,6','traps':{5:(4,100),6:(4,100)}},'Yarmouth':{'name':'UK LAY Yarmouth Trap 1,3,6','traps':{1:(6,50),3:(6,50),6:(6,50)}}}
SOURCE_CONFIG='authoritative 11-strategy six-runner baseline 2026-08-25; Oxford and Swindon removed'
def norm(s):return re.sub(r'[^a-z0-9]+','',(s or '').lower())
def malformed_name(s):
 s=(s or '').strip();return (not s) or (not re.search(r'[A-Za-z]',s)) or len(s)<2
def frac_to_decimal(text):
 t=text.strip();return float(Fraction(t))+1.0 if '/' in t else float(t)+1.0
def parse_forecast(text):
 out=[]
 if not text:return out
 for part in [p.strip() for p in text.split(',') if p.strip()]:
  m=re.match(r'^(\d+(?:/\d+)?|\d+(?:\.\d+)?)\s+(.+)$',part)
  if not m:continue
  try:dec=frac_to_decimal(m.group(1))
  except:continue
  out.append({'frac':m.group(1),'dec':dec,'name':m.group(2).strip()})
 return out
def forecast_status(entries,candidate):
 if not entries:return None,None,None,'NO_FORECAST'
 target=norm(candidate);matches=[e for e in entries if norm(e['name'])==target]
 if not matches:return None,None,None,'NOT_FOUND'
 e=matches[0];prices=sorted(x['dec'] for x in entries)
 if len(prices)<3:return None,e['frac'],e['dec'],'INSUFFICIENT'
 threshold=prices[2];less=sum(1 for x in entries if x['dec']<threshold);tied=sum(1 for x in entries if x['dec']==threshold);rank=1+sum(1 for x in entries if x['dec']<e['dec'])
 if e['dec']<threshold:state='TOP3'
 elif e['dec']==threshold:state='BOUNDARY_TIE' if less<3 and less+tied>3 else 'TOP3'
 else:state='OUTSIDE_TOP3'
 return rank,e['frac'],e['dec'],state
with open(RACECARDS,encoding='utf-8-sig',newline='') as f:race_rows=list(csv.DictReader(f))
with open(AUDIT,encoding='utf-8-sig',newline='') as f:audit_rows=list(csv.DictReader(f))
with open(TIMEFORM,encoding='utf-8-sig',newline='') as f:tf_rows=list(csv.DictReader(f))
if not race_rows or not tf_rows:raise SystemExit('Missing current source data')
today=race_rows[0]['date']
if any(r['date']!=today for r in race_rows):raise SystemExit('Mixed racecard dates')
if any(r['date']!=today for r in audit_rows):raise SystemExit('Audit date mismatch')
if any(r['Date']!=today for r in tf_rows):raise SystemExit('Timeform date mismatch')
races=defaultdict(list)
for r in race_rows:races[(r['date'],r['track'],r['race_time'])].append(r)
malformed_races=set();malformed_details=[]
for key,rows in races.items():
 bad=[r for r in rows if malformed_name(r.get('dog_name'))]
 if bad:malformed_races.add(key);malformed_details.extend(bad)
six_runner_races=set()
for key,rows in races.items():
 if key in malformed_races:continue
 traps=[];valid=True
 for r in rows:
  try:trap=int(r['runner_number'])
  except:valid=False;break
  if trap<1 or trap>6:valid=False;break
  traps.append(trap)
 if valid and len(rows)==6 and len(set(traps))==6 and set(traps)=={1,2,3,4,5,6}:six_runner_races.add(key)
candidates=[]
for r in race_rows:
 key=(r['date'],r['track'],r['race_time'])
 if key in malformed_races or key not in six_runner_races:continue
 s=STRATEGIES.get(r['track'])
 if not s:continue
 try:trap=int(r['runner_number'])
 except:continue
 if trap not in s['traps']:continue
 lo,hi=s['traps'][trap];candidates.append({**r,'strategy':s['name'],'StrategyMinPrice':lo,'StrategyMaxPrice':hi})
tf={(r['Date'],r['Track'],r['RaceTime']):r for r in tf_rows};analysed=[];counts=defaultdict(int);retained=[]
for c in candidates:
 key=(c['date'],c['track'],c['race_time']);t=tf.get(key);row={**c,'Grade':'','Distance':'','AnalystVerdictPosition':'','ForecastRank':'','ForecastFractional':'','ForecastDecimal':'','ForecastState':'','ExclusionCategory':'','Reason':'','Status':'RETAINED'}
 if not t or t.get('Status')!='COMPLETE' or not all((t.get('AnalystVerdict1','').strip(),t.get('AnalystVerdict2','').strip(),t.get('AnalystVerdict3','').strip())):
  row['Status']='EXCLUDED';row['ExclusionCategory']='TIMEFORM_RACE_DISCARDED';row['Reason']='Timeform race missing/incomplete or Analyst Verdict top 3 incomplete';counts['timeform_discard']+=1;analysed.append(row);continue
 counts['complete_coverage']+=1;row['Grade']=t.get('Grade','');row['Distance']=t.get('Distance','');av=[t.get('AnalystVerdict1',''),t.get('AnalystVerdict2',''),t.get('AnalystVerdict3','')];apos='OUTSIDE_TOP3'
 for i,n in enumerate(av,1):
  if norm(n)==norm(c['dog_name']):apos=str(i);break
 row['AnalystVerdictPosition']=apos;entries=parse_forecast(t.get('BettingForecast',''));frank,ffrac,fdec,fstate=forecast_status(entries,c['dog_name']);row['ForecastRank']='' if frank is None else frank;row['ForecastFractional']='' if ffrac is None else ffrac;row['ForecastDecimal']='' if fdec is None else round(fdec,4);row['ForecastState']=fstate
 if apos!='OUTSIDE_TOP3':row['Status']='EXCLUDED';row['ExclusionCategory']='ANALYST_TOP3';row['Reason']=f'Timeform Analyst Verdict #{apos}';counts['analyst_top3']+=1;analysed.append(row);continue
 if fstate=='TOP3':row['Status']='EXCLUDED';row['ExclusionCategory']='FORECAST_TOP3';row['Reason']=f'Timeform Betting Forecast top 3 (rank {frank}, {ffrac}; decimal {fdec:.2f})';counts['forecast_top3']+=1;analysed.append(row);continue
 if fstate=='BOUNDARY_TIE':counts['forecast_boundary_tie']+=1;row['Reason']='Forecast tie crosses third-place boundary; retained absent stronger evidence'
 elif frank==4:counts['forecast4_reviewed']+=1;row['Reason']=f'Forecast #4 reviewed ({ffrac}; decimal {fdec:.2f}); retained absent converging danger evidence'
 retained.append(row);analysed.append(row)
headers=['Provider','SelectionName','MarketType','StartTime','BetType','Size','MinPrice','MaxPrice','BSP']
def write_output(path,provider):
 with open(path,'w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=headers);w.writeheader()
  for r in retained:
   dt=datetime.strptime(r['date']+' '+r['race_time'],'%Y-%m-%d %H:%M')
   w.writerow({'Provider':provider,'SelectionName':r['dog_name'],'MarketType':'WIN','StartTime':dt.strftime('%d/%m/%Y %H:%M'),'BetType':'LAY','Size':1,'MinPrice':r['StrategyMinPrice'],'MaxPrice':r['StrategyMaxPrice'],'BSP':'FALSE'})
write_output(OUTPUT,'Daily Strategy Filter')
write_output(OUTPUT2,'Daily Strategy 2')
fields=['date','track','race_time','runner_number','dog_name','strategy','StrategyMinPrice','StrategyMaxPrice','Distance','Grade','AnalystVerdictPosition','ForecastRank','ForecastFractional','ForecastDecimal','ForecastState','Status','ExclusionCategory','Reason']
with open(DETAIL,'w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in analysed:w.writerow({k:r.get(k,'') for k in fields})
summary={'date':today,'malformed_races':len(malformed_races),'malformed_rows':[{'track':r['track'],'race_time':r['race_time'],'runner_number':r['runner_number'],'dog_name':r['dog_name']} for r in malformed_details],'six_runner_races':len(six_runner_races),'raw_candidates':len(candidates),'complete_timeform_candidates':counts['complete_coverage'],'timeform_race_discards':counts['timeform_discard'],'analyst_top3_exclusions':counts['analyst_top3'],'forecast_top3_exclusions':counts['forecast_top3'],'forecast_boundary_ties':counts['forecast_boundary_tie'],'forecast4_reviewed':counts['forecast4_reviewed'],'additional_risk_exclusions':0,'retained':len(retained),'source_config':SOURCE_CONFIG}
summary['complete_timeform_pct']=round(100*summary['complete_timeform_candidates']/summary['raw_candidates'],2) if summary['raw_candidates'] else 0
with open(SUMMARY,'w',encoding='utf-8') as f:json.dump(summary,f,indent=2)
print(json.dumps(summary,indent=2))
