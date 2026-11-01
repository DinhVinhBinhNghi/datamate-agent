import json,pathlib,sys,hashlib,collections
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from chat09_raw import canonical_product_key,top_k_customer
from build_j import family,period
root=pathlib.Path(__file__).resolve().parent.parent
x=json.loads((root/'artifacts/chat09/raw_audit.json').read_text(encoding='utf8'))
expected={'2025-01':(210199000,2989,70324),'2025-06':(221770500,3185,69630),'2025-11':(219225000,3032,72304)}
for month,(rev,n,aov) in expected.items():
    z=x['monthly']['months'][month];assert (z['revenue'],z['orders'],z['aov'])==(rev,n,aov)
assert x['monthly']['months']['2025-11']['max_day']=='2025-11-02'
assert x['monthly']['months']['2025-07']['max_day']=='2025-07-27'
assert canonical_product_key(' Cà phê  sữa (M) ')==canonical_product_key('ca phe sua (m)')
assert top_k_customer('Th9/2025 3 khách nào chi nhiều tiền nhất?')==3
assert top_k_customer('Th9/2025 khách nào chi nhiều tiền nhất?') is None
assert all(s['cardinality_pass'] for s in x['sqlite'])
qs=[json.loads(l) for l in (root/'work/public_test/questions.jsonl').open(encoding='utf8')]
selected=[(family(q['question']),period(q['question'])) for q in qs if q['business_id']=='dev_002' and family(q['question'])]
assert collections.Counter(f for f,p in selected)=={'aov':3,'max_day':2}
print('PASS: raw J five checks, lexical K/L checks, POS cardinality, J dynamic selection (no parent/validator checked)')
