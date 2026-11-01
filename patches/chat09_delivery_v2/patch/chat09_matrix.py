"""Read-only rule difference and exploratory opportunity matrix; labels are proposals."""
import argparse,csv,json,pathlib,re,collections,hashlib,zipfile

def section_rows(path):
    section='';subsection='';rows={}
    for line in path.read_text(encoding='utf8').splitlines():
        if line.startswith('## '):section=line[3:];subsection=''
        elif line.startswith('### '):subsection=line[4:]
        elif line.startswith('|') and not re.match(r'^\|[- :|]+\|$',line):
            fields=[s.strip() for s in line.strip('|').split('|')]
            if len(fields)>1 and fields[0] not in ('Luật','Cách nói','Cách ghi','type','Từ'):
                rows[(section+(' / '+subsection if subsection else ''),fields[0])]=' | '.join(fields[1:])
    return rows

def family(q):
    s=q.casefold()
    rules=[('unanswerable','không trả lời được|khong tra loi duoc'),('aov','trung bình.*đơn|trung binh.*don|bình quân.*đơn'),('cancel','huỷ|hủy|huy don|đơn bị huy'),('growth','tăng trưởng|tang truong|so với|so voi|thay đổi|thay doi'),('max_day','ngày nào.*nhất|ngay nao.*nhat|ngày mô.*nhất|ngay mo.*nhat'),('customer','khách|khach'),('product','mặt hàng|mat hang|món|mon|sản phẩm|san pham|size|ly '),('revenue','doanh thu|dthu|tiền bán|tien ban|thu về|thu ve|bán được.*tiền'),('orders','mấy đơn|may don|số đơn|so don|đơn hàng|don hang')]
    for name,pattern in rules:
        if re.search(pattern,s):return name
    return 'other'

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--out',required=True);z=a.parse_args()
    root=pathlib.Path(z.root);out=pathlib.Path(z.out);out.mkdir(parents=True,exist_ok=True)
    tr=section_rows(root/'train/rulebook.md');pu=section_rows(root/'public_test/rulebook.md')
    with (out/'rulebook_diff.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['section_and_key','train','public','calculation_impact'])
        for k in sorted(tr.keys()|pu.keys()):
            if tr.get(k)!=pu.get(k):w.writerow([' / '.join(k),tr.get(k,''),pu.get(k,''),'review before enabling related family'])
    qs=[json.loads(l) for l in (root/'public_test/questions.jsonl').open(encoding='utf8')]
    cnt=collections.Counter((q['business_id'],family(q['question'])) for q in qs)
    with (out/'opportunity_matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['business','family','question_count_heuristic','archetype_proposal','train_analogue_proposal','README_evidence','schema_evidence','grain_proposal','amount_status_date_proposal','semantic_risk','blocker','effort_proposal','stage'])
        for (biz,fam),n in sorted(cnt.items()):
            base=root/'public_test/data'/biz
            files=[p.name for p in base.iterdir() if p.is_file()]
            readme=(base/'README.md').read_text(encoding='utf8') if (base/'README.md').exists() else ''
            arch='POS SQLite' if 'pos.sqlite' in files else 'monthly Excel sales lines' if any(x.startswith('BanHang_T') for x in files) else 'CSV/Excel mixed; unverified'
            analogue='biz_123' if biz=='dev_006' else 'biz_102/103/104' if biz=='dev_002' else ''
            stage='mapping đề xuất' if analogue else 'đã scan'
            w.writerow([biz,fam,n,arch,analogue,'; '.join(readme.splitlines()[:5])[:350],', '.join(files[:12]),'header order / detail line' if analogue else 'unverified','TriGia/TinhTrang/NgayLap' if biz=='dev_006' else 'Tổng tiền/Trạng thái đơn hàng/Ngày đặt hàng' if biz=='dev_002' else 'unverified','medium: date, status, grain; high for industry/joins','train exact + semantics + public invariant missing' if biz!='dev_002' else 'family-specific gate required','medium' if analogue else 'high',stage])
    print('rows',len(cnt),'rule differences',sum(tr.get(k)!=pu.get(k) for k in tr.keys()|pu.keys()))
if __name__=='__main__':main()
