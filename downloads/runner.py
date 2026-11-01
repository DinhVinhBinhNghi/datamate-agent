"""Evaluate the supported train business without cross-business leakage."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from datamate.eval.metrics import summarize
from datamate.eval.scorer import score
from datamate.run import process_question


def run(root, answers_path, output):
    questions = [json.loads(s) for s in (root/'train/questions.jsonl').read_text(encoding='utf-8-sig').splitlines() if s]
    references = {row['id']: row for row in (json.loads(s) for s in answers_path.read_text(encoding='utf-8-sig').splitlines() if s)}
    business_ids = sorted({q['business_id'] for q in questions})
    supported = 'biz_129'
    if supported not in business_ids or len(references) != len(questions):
        raise ValueError('training inventory mismatch')
    # This split never puts two questions from one business in different partitions.
    held_out = [b for b in business_ids if b != supported]
    manifest = {'version':'chat06-group3-v1','split_key':'business_id',
                'development_business_ids':[supported], 'validation_business_ids':held_out[:14],
                'holdout_business_ids':held_out[14:],
                'limitation':'No supported business in validation or holdout; no calibrated threshold can be selected.'}
    output.mkdir(parents=True, exist_ok=True)
    (output/'split_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    started=time.perf_counter()
    with (output/'development_results.jsonl').open('w',encoding='utf-8') as sink:
        for q in questions:
            if q['business_id'] != supported:
                continue
            prediction, evidence = process_question(q,root,'train')
            row={'id':q['id'],'business_id':supported,'family':(evidence.get('plan') or {}).get('operation'),
                 'answer_type':prediction['type'],'error_layer':evidence.get('error_layer'),
                 'decision':evidence['decision'],'outcome':score(prediction,references[q['id']]),
                 'elapsed_seconds':evidence['elapsed_seconds']}
            rows.append(row)
            sink.write(json.dumps(row,ensure_ascii=False)+'\n')
    summary=summarize(rows)
    summary.update({'business_id':supported,'runtime_seconds':round(time.perf_counter()-started,3),
                    'error_layers':dict(Counter(r['error_layer'] or 'none' for r in rows)),
                    'by_operation':{op:summarize([r for r in rows if r['family']==op]) for op in sorted({r['family'] for r in rows},key=str)},
                    'validation_answer_metrics':None,'holdout_answer_metrics':None,
                    'threshold':'hard gates only; no calibrated probability'})
    (output/'metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',type=Path,default=Path.cwd())
    parser.add_argument('--answers',type=Path,default=Path('train/answers.jsonl'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/eval/chat06_group3'))
    args=parser.parse_args()
    answers_path = args.answers if args.answers.is_absolute() else args.project_root / args.answers
    run(args.project_root.resolve(),answers_path.resolve(),args.output.resolve())


if __name__=='__main__':
    main()
