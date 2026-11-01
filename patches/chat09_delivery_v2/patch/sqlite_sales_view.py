"""Read-only scoped POS sales view, two independent monthly calculations."""
import argparse,collections,datetime as dt,json,pathlib,sqlite3,math
from decimal import Decimal,ROUND_HALF_UP
import pandas as pd

def audit(path,ruleset):
    if ruleset not in ('train','public_test'):raise ValueError('Explicit ruleset required')
    c=sqlite3.connect('file:'+str(pathlib.Path(path).resolve())+'?mode=ro',uri=True)
    try:
        headers=pd.read_sql_query('select MaHoaDon,ThoiGianLap,NgayLap,TinhTrang from don_hang',c)
        lines=pd.read_sql_query('select * from chi_tiet_don',c)
        returned=set(r[0] for r in c.execute('select distinct MaHoaDon from tra_hang'))
        if headers.MaHoaDon.duplicated().any():raise ValueError('Header not unique')
        if not set(lines.MaHoaDon)<=set(headers.MaHoaDon):raise ValueError('Orphan line')
        if not set(headers.TinhTrang)<=set(['completed','shipping','cancelled','returned']):raise ValueError('Status unknown')
        if set(headers.loc[headers.TinhTrang=='returned','MaHoaDon'])!=returned:raise ValueError('Return status mismatch')
        if not headers.ThoiGianLap.str.match(r'^20\d\d-\d\d-\d\d ').all():raise ValueError('Unknown date format')
        if not lines.SLQuyDoi.notna().all():raise ValueError('Unit conversion missing')
        # Python/pandas path: dedupe identical lines within order by complete row.
        detail=lines.drop_duplicates();h=headers.assign(day=headers.ThoiGianLap.str.slice(0,10),month=headers.ThoiGianLap.str.slice(0,7))
        joined=detail.merge(h,on='MaHoaDon',validate='many_to_one')
        joined=joined[(joined.TinhTrang.isin(['completed','shipping'])) & (~joined.MaHoaDon.isin(returned))]
        rev=joined.groupby('month').TriGia.sum().to_dict()
        daily=joined.groupby(['month','day']).TriGia.sum()
        order_counts=h[h.TinhTrang.isin(['completed','shipping']) & (~h.MaHoaDon.isin(returned))].groupby('month').MaHoaDon.nunique().to_dict()
        all_counts=h.groupby('month').MaHoaDon.nunique().to_dict()
        cancel_counts=h[h.TinhTrang=='cancelled'].groupby('month').MaHoaDon.nunique().to_dict()
        py={}
        for m,n in order_counts.items():
            ds=daily[m];mx=ds.max();py[m]={'revenue':int(rev[m]),'orders':int(n),'cancel_rate':float((Decimal(100*cancel_counts.get(m,0))/Decimal(all_counts[m])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),'aov':int((Decimal(int(rev[m]))/int(n)).quantize(Decimal(1),rounding=ROUND_HALF_UP)),'max_day':min(ds[ds==mx].index),'max_day_revenue':int(mx)}
        months=sorted(py)
        for i,m in enumerate(months):
            if i:py[m]['growth_prev_percent']=float(((Decimal(py[m]['revenue'])/Decimal(py[months[i-1]]['revenue'])-1)*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        # Independent SQL path, detail de-duplicated across all columns, header only once.
        fields=','.join('"'+x.replace('"','""')+'"' for x in lines.columns)
        sql=f'''with detail as (select distinct {fields} from chi_tiet_don),
          eligible as (select MaHoaDon,substr(ThoiGianLap,1,7) month,substr(ThoiGianLap,1,10) day from don_hang where TinhTrang in ('completed','shipping') and MaHoaDon not in (select MaHoaDon from tra_hang))
          select month,day,sum(TriGia) revenue,count(*) lines from detail join eligible using (MaHoaDon) group by month,day'''
        sql_daily={(m,d):(int(v),int(n)) for m,d,v,n in c.execute(sql)}
        sql_month=collections.Counter();sql_lines=collections.Counter()
        for (m,d),(v,n) in sql_daily.items():sql_month[m]+=v;sql_lines[m]+=n
        if {m:int(v) for m,v in rev.items()}!=dict(sql_month):raise AssertionError('SQL and pandas revenue disagree')
        if len(detail)!=len(lines)-lines.duplicated().sum():raise AssertionError('Dedup count mismatch')
        if not all(int(daily[m][d])==v for (m,d),(v,_) in sql_daily.items()):raise AssertionError('Daily SQL and pandas disagree')
        return {'ruleset':ruleset,'headers':len(h),'detail_raw':len(lines),'detail_dedup':len(detail),'eligible_headers':sum(order_counts.values()),'months':py,'sql_pandas_equal':True,'date_source':'ThoiGianLap ISO; NgayLap text cross-check pending'}
    finally:c.close()

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',required=True);a.add_argument('--out',required=True);x=a.parse_args();root=pathlib.Path(x.root);out=pathlib.Path(x.out);out.mkdir(parents=True,exist_ok=True)
    result={b:audit(root/s/'data'/b/'pos.sqlite',s) for s,b in [('train','biz_123'),('public_test','dev_006')]}
    (out/'sqlite_view_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('SQL/pandas passed for',list(result))
if __name__=='__main__':main()
