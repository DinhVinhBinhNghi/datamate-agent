"""Isolated J builder. Require exact G parent, recompute from read-only raw, fail closed."""
import argparse,hashlib,json,pathlib,re,sys,datetime as dt
from chat09_raw import sales_audit,fold
G_SHA='3af7a104c16e41249419c9cc9260ac68ef80c68141e8df32b4af2880952b88dd'

def period(q):
    s=fold(q)
    m=re.search(r'\b(?:thang\s*|th\s*|t\s*)?(\d{1,2})\s*[/\-]\s*(20\d{2}|\d{2})\b',s)
    if not m:m=re.search(r'\bthang\s*(\d{1,2})\s+nam\s+(20\d{2})\b',s)
    if not m:raise ValueError('Cannot parse explicit month/year: '+q)
    month,year=map(int,m.groups())
    if year<100:year+=2000
    if month not in range(1,13):raise ValueError(q)
    return f'{year:04d}-{month:02d}'

def family(q):
    s=fold(q)
    if re.search(r'trung binh\s*(?:moi|1)?\s*don',s) and re.search(r'gia tri|doanh thu',s):return 'aov'
    if re.search(r'ngay (?:mo|nao)',s) and re.search(r'nhieu tien nhat|dat nhat|doanh thu',s):return 'max_day'
    return None

def load(path):return [json.loads(l) for l in path.read_text(encoding='utf8').splitlines() if l.strip()]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--parent',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
    root=pathlib.Path(a.root);parent=pathlib.Path(a.parent);out=pathlib.Path(a.output_dir)
    if hashlib.sha256(parent.read_bytes()).hexdigest()!=G_SHA:raise ValueError('Frozen parent hash mismatch')
    qs=load(root/'public_test/questions.jsonl');rows=load(parent)
    if len(qs)!=1000 or [q['id'] for q in qs]!=[r['id'] for r in rows]:raise ValueError('Question order or count mismatch')
    if sum(r['type']!='abstain' for r in rows)!=24:raise ValueError('Unexpected parent coverage')
    metrics=sales_audit(root,'dev_002','public_test')['months'];new=[];diff=[]
    for q,old in zip(qs,rows):
        fam=family(q['question']) if q['business_id']=='dev_002' else None
        if fam is None:continue
        key=period(q['question'])
        if key not in metrics:raise ValueError('Month outside data')
        if old['type']!='abstain':raise ValueError('Would modify answered G row')
        value=metrics[key][fam]
        fresh={'id':q['id'],'type':'number' if fam=='aov' else 'date','answer':value}
        new.append(fresh);diff.append({'id':q['id'],'question':q['question'],'family':fam,'period':key,'old':old,'new':fresh,'source':'raw monthly Excel'})
    if len(diff)!=5 or {d['family'] for d in diff}!={'aov','max_day'} or sum(d['family']=='aov' for d in diff)!=3:raise ValueError('Expected exactly 3 AOV + 2 max-day')
    byid={r['id']:r for r in new};merged=[byid.get(r['id'],r) for r in rows]
    if sum(a!=b for a,b in zip(rows,merged))!=5:raise AssertionError('Unexpected diff')
    if any(a['type']!='abstain' and a!=b for a,b in zip(rows,merged)):raise AssertionError('G changed')
    for r in merged:
        if r['type']=='number' and (isinstance(r.get('answer'),bool) or not isinstance(r.get('answer'),(int,float))):raise ValueError('Bad number')
        if r['type']=='date':dt.date.fromisoformat(r['answer'])
    out.mkdir(parents=True,exist_ok=True)
    target=out/'candidate_j_from_g.jsonl';report=out/'candidate_j_diff.json';manifest=out/'candidate_j_freeze.json'
    for file in (target,report,manifest):
        if file.exists():raise FileExistsError(f'Frozen output exists: {file}')
    payload=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in merged).encode('utf8')
    # Exclusive creation: never overwrite frozen files.
    with target.open('xb') as f:f.write(payload)
    report.write_text(json.dumps(diff,ensure_ascii=False,indent=2),encoding='utf8')
    manifest.write_text(json.dumps({'parent_sha256':G_SHA,'candidate_sha256':hashlib.sha256(payload).hexdigest(),'answered':29,'added':5,'diff_ids':[d['id'] for d in diff],'ruleset':'public_test','raw_recomputed':True,'structural_validation':'local checks pass; run D:\\ZALO validator separately','submitted':False},ensure_ascii=False,indent=2),encoding='utf8')
    print(manifest.read_text(encoding='utf8'))
if __name__=='__main__':main()
