"""Read-only DataMate Chat09 audits. No submission values or question IDs embedded."""
import argparse, collections, csv, datetime as dt, hashlib, json, pathlib, re, sqlite3, unicodedata
from decimal import Decimal, ROUND_HALF_UP
import openpyxl

FIELDS = ['Mã đơn hàng','Ngày đặt hàng','Trạng thái đơn hàng','Tên khách hàng','Tên sản phẩm','Số lượng sản phẩm','Giá sản phẩm','Tổng tiền','Đơn vị tính']

def fold(s):
    s = str(s or '').replace('đ','d').replace('Đ','D')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',s.casefold()) if unicodedata.category(c)!='Mn').split())

def canonical_product_key(s):
    return fold(s)

def top_k_customer(question):
    m = re.search(r'\b([1-9]\d?)\s*(?:khach(?:\s+hang)?)\b',fold(question))
    return int(m.group(1)) if m else None

def money(x):
    if isinstance(x,(int,float,Decimal)):return int(Decimal(str(x)))
    t=str(x or '').strip().casefold().replace(' ','').replace(',','').replace('.','').replace('đ','')
    scale=1000 if t.endswith('k') else 1
    if scale==1000:t=t[:-1]
    if not re.fullmatch(r'-?\d+',t):raise ValueError(f'Unsupported money {x!r}')
    return int(t)*scale

def date(x):
    if isinstance(x,(dt.datetime,dt.date)):return x.date() if isinstance(x,dt.datetime) else x
    return dt.datetime.strptime(str(x).strip(),'%d/%m/%Y').date()

def excel_lines(root,business,ruleset):
    if ruleset not in ('train','public_test'):raise ValueError('Explicit ruleset required')
    base=pathlib.Path(root)/ruleset/'data'/business
    if not base.exists():raise FileNotFoundError(base)
    paths=sorted(base.glob('BanHang_T*.xlsx')) if ruleset=='public_test' else sorted(base.glob('DonHang_ChiTiet.xlsx'))
    if not paths:raise ValueError('No recognized monthly sales workbook')
    for path in paths:
        wb=openpyxl.load_workbook(path,read_only=True,data_only=True)
        try:
            ws=wb['DonHang_ChiTiet']
            rows=iter(ws.values)
            for row in rows:
                if row and row[0]=='Mã đơn hàng':
                    header=list(row);break
            else:raise ValueError(f'Missing header {path}')
            if not set(FIELDS)<=set(header):raise ValueError(f'Unexpected schema {path}: {header}')
            for rownum,row in enumerate(rows,5):
                if not row or not row[0] or row[0]=='Mã đơn hàng':continue
                d=dict(zip(header,row));d['_path']=str(path);d['_row']=rownum
                yield d
        finally:wb.close()

def sales_audit(root,business,ruleset):
    # Read-only, header fields repeated on each line; reject any conflicting values.
    orders={}; lines=0; duplicate=0; seen=set(); variants=collections.defaultdict(set); values=[]
    for d in excel_lines(root,business,ruleset):
        oid=str(d['Mã đơn hàng']).strip(); day=date(d['Ngày đặt hàng']);status=fold(d['Trạng thái đơn hàng'])
        if not oid or status not in {'da hoan thanh','hoan thanh','huy','da huy','tra hang','da tra hang','dang giao','dang giao dich','da hoan hang'}:raise ValueError(f'Unrecognized order/status {oid} {status}')
        key=(oid,day,status)
        if oid in orders and orders[oid][:2]!=(day,status):raise ValueError(f'Conflicting header {oid}')
        orders.setdefault(oid,(day,status,0))
        # Duplicate export rows in same order; identical distinct orders remain distinct.
        signature=(oid,tuple(d.get(f) for f in FIELDS))
        if signature in seen:duplicate+=1;continue
        seen.add(signature)
        lines+=1
        amt=money(d['Tổng tiền']);values.append((oid,day,status,amt,d['Tên sản phẩm']))
        variants[canonical_product_key(d['Tên sản phẩm'])].add(str(d['Tên sản phẩm']).strip())
    eligible={'da hoan thanh','hoan thanh','dang giao'}
    monthly=collections.defaultdict(lambda:{'revenue':0,'orders':set(),'days':collections.Counter()})
    for oid,day,status,amt,name in values:
        if status not in eligible:continue
        key=day.strftime('%Y-%m');v=monthly[key];v['revenue']+=amt;v['orders'].add(oid);v['days'][day.isoformat()]+=amt
    out={}
    for k,v in sorted(monthly.items()):
        n=len(v['orders']); top=max(v['days'].values());maxday=min(d for d,a in v['days'].items() if a==top)
        out[k]={'revenue':v['revenue'],'orders':n,'aov':int((Decimal(v['revenue'])/n).quantize(Decimal(1),rounding=ROUND_HALF_UP)),'max_day':maxday,'max_revenue':top}
    return {'business':business,'ruleset':ruleset,'order_count':len(orders),'line_count':lines,'duplicate_export_rows':duplicate,'months':out,'alias_groups':{k:sorted(v) for k,v in variants.items() if len(v)>1}}

def sqlite_audit(path,ruleset):
    if ruleset not in ('train','public_test'):raise ValueError('Explicit ruleset required')
    c=sqlite3.connect('file:'+str(pathlib.Path(path).resolve())+'?mode=ro',uri=True)
    try:
        q=lambda s:c.execute(s).fetchone()[0]
        h=q('select count(*) from don_hang'); l=q('select count(*) from chi_tiet_don')
        hdist=q('select count(distinct MaHoaDon) from don_hang');ldist=q('select count(distinct MaHoaDon) from chi_tiet_don')
        unmatched=q('select count(*) from chi_tiet_don d left join don_hang h on h.MaHoaDon=d.MaHoaDon where h.MaHoaDon is null')
        joined=q('select count(*) from don_hang h join chi_tiet_don d on h.MaHoaDon=d.MaHoaDon')
        repeated=q('select count(*) from (select MaHoaDon,SoThuTu,count(*) n from chi_tiet_don group by 1,2 having n>1)')
        exact_duplicates=q('select coalesce(sum(n-1),0) from (select count(*) n from chi_tiet_don group by IDCuaHang,MaHoaDon,SoThuTu,MaHangHoa,DonViTinh,SL,SLQuyDoi,GiaDonVi,ChietKhau,TriGia,GiaVonLucBan having n>1)')
        ret=q('select count(distinct MaHoaDon) from tra_hang')
        statuses=dict(c.execute('select TinhTrang,count(*) from don_hang group by 1'))
        return {'path':str(path),'ruleset':ruleset,'headers':h,'lines':l,'distinct_headers':hdist,'distinct_line_orders':ldist,'unmatched_lines':unmatched,'joined_rows':joined,'duplicate_line_keys':repeated,'exact_duplicate_rows':exact_duplicates,'returned_orders_in_returns_table':ret,'statuses':statuses,'cardinality_pass':h==hdist and l==joined and unmatched==0 and repeated==exact_duplicates}
    finally:c.close()

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--out',required=True);z=a.parse_args()
    root=pathlib.Path(z.root);out=pathlib.Path(z.out);out.mkdir(parents=True,exist_ok=True)
    audits={'monthly':sales_audit(root,'dev_002','public_test'),'sqlite':[sqlite_audit(root/'train/data/biz_123/pos.sqlite','train'),sqlite_audit(root/'public_test/data/dev_006/pos.sqlite','public_test')]}
    (out/'raw_audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2),encoding='utf8')
    print('wrote',out/'raw_audit.json')
if __name__=='__main__':main()
