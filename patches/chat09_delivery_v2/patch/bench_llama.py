"""Optional llama.cpp typed-intent benchmark. No SQL/code generation; not a submission gate."""
import argparse,json,pathlib,subprocess,time,hashlib,random,collections,re,statistics
from chat09_raw import fold,top_k_customer
from build_j import period,family

def reference(q):
    s=q['question'];f=family(s)
    try:p=period(s)
    except ValueError:p=None
    return {'family':f or 'other','period':p,'top_k':top_k_customer(s)}

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--llama-cli',required=True);a.add_argument('--model',required=True);a.add_argument('--out',required=True);a.add_argument('--threads',type=int,default=8);a.add_argument('--timeout',type=int,default=90);v=a.parse_args()
    root=pathlib.Path(v.root);qs=[json.loads(x) for x in (root/'train/questions.jsonl').open(encoding='utf8')]
    rng=random.Random(9);by=collections.defaultdict(list)
    for q in qs:by[q['business_id']].append(q)
    sample=[]
    for b in sorted(by):sample.extend(rng.sample(by[b],min(2,len(by[b]))))
    sample=sample[:50]
    grammar='root ::= "{" ws "\\\"family\\\"" ws ":" ws string ws "," ws "\\\"period\\\"" ws ":" ws (string | "null") ws "," ws "\\\"top_k\\\"" ws ":" ws (number | "null") ws "}" ws\nstring ::= "\\\"" [^"\\\\]* "\\\""\nnumber ::= [0-9]+\nws ::= [ \\t\\n]*\n'
    out=pathlib.Path(v.out);out.mkdir(parents=True,exist_ok=True);gp=out/'intent.gbnf';gp.write_text(grammar)
    results=[]
    for q in sample:
        exemplars=[]
        for other in sorted(by):
            if other!=q['business_id']:
                e=by[other][0];exemplars.append((e['question'],reference(e)))
            if len(exemplars)==3:break
        prompt='Return only JSON typed intent with family, period YYYY-MM or null, top_k integer or null. Never output SQL or code.\n'+''.join('Question: '+s+'\nJSON: '+json.dumps(r,ensure_ascii=False)+'\n' for s,r in exemplars)+'Question: '+q['question']+'\nJSON:'
        start=time.monotonic();err=None;parsed=None
        try:
            cp=subprocess.run([v.llama_cli,'-m',v.model,'-t',str(v.threads),'-n','100','--grammar-file',str(gp),'-p',prompt],capture_output=True,text=True,timeout=v.timeout)
            if cp.returncode:err='llama exit '+str(cp.returncode)
            else:
                matches=re.findall(r'\{[^{}]*\}',cp.stdout)
                parsed=json.loads(matches[-1]) if matches else None
        except (subprocess.TimeoutExpired,ValueError) as ex:err=type(ex).__name__
        ref=reference(q)
        results.append({'business':q['business_id'],'question_hash':hashlib.sha256(q['question'].encode()).hexdigest(),'seconds':round(time.monotonic()-start,3),'json_valid':isinstance(parsed,dict),'family_correct':parsed is not None and parsed.get('family')==ref['family'],'period_correct':parsed is not None and parsed.get('period')==ref['period'],'top_k_correct':parsed is not None and parsed.get('top_k')==ref['top_k'],'error':err})
    (out/'llm_results.json').write_text(json.dumps(results,indent=2));print('n',len(results),'json_valid',sum(r['json_valid'] for r in results),'median_seconds',statistics.median(r['seconds'] for r in results))
if __name__=='__main__':main()
