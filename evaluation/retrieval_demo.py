"""Bounded live retrieval inspection, without LLM calls or held-out access."""

import argparse
import asyncio
import json
from pathlib import Path

from ai.retrieval.current_law import load_current_retriever
from backend.services.retrieval_inspection import inspect_retrieval
from evaluation.core_runner import prepare_plan, write_new
from evaluation.core_scoring import quantile
from evaluation.reviewed_current_law_dataset import require_reviewed_scoring


async def run(output: Path, numbers: list[int]) -> None:
    if output.exists():
        raise FileExistsError("demo output exists; choose a new run directory")
    if not 1 <= len(numbers) <= 15 or len(set(numbers)) != len(numbers) or any(n < 1 or n > 50 for n in numbers):
        raise ValueError("select 1–15 unique known questions")
    plan = prepare_plan("legacy", output / "plan.json")
    by_id = {q.id: q for q in plan.questions}
    # Gold is used only to report evidence coverage AFTER search; never passed to retrieval.
    gold = {c.id: c for c in require_reviewed_scoring()}
    retriever, client = load_current_retriever(plan.settings)
    results = []
    try:
        for number in numbers:
            identity = f"current_law_{number:03d}"
            question = by_id[identity]
            inspection = await inspect_retrieval(retriever, question.current_query, plan.settings.top_k)
            initial = set(inspection["initial_chunk_ids"])
            retrieved = {i for c in inspection["chunks"] if c['id'] in initial
                         for i in c['metadata'].get('source_processed_ids', [c['metadata']['processed_id']])}
            expanded = {i for c in inspection["chunks"]
                        for i in c['metadata'].get('source_processed_ids', [c['metadata']['processed_id']])}
            from evaluation.phase3_design import missing_facets
            positive = {f.id for f in gold[identity].gold.required_facets if f.required and f.support_state == 'positive_support'}
            row = {'id': identity, **inspection, 'positive_facets': len(positive),
                   'missing_after_search': [f for f in missing_facets(gold[identity], list(retrieved)) if f in positive],
                   'missing_after_expansion': [f for f in missing_facets(gold[identity], list(expanded)) if f in positive]}
            write_new(output / f'{identity}.json', row)
            results.append(row)
            print(identity, 'retrieval_ms=',round(row['timings_ms']['total_including_initialization']),
                  'missing=',row['missing_after_expansion'],flush=True)
    finally:
        client.close()
    times = [r['timings_ms']['total_including_initialization'] / 1000 for r in results]
    summary = {'kind':'selected_known_case_retrieval_inspection', 'cases':len(results), 'llm_calls':0,
               'mean_seconds':sum(times)/len(times), 'median_seconds':quantile(times,.5),
               'p95_seconds':quantile(times,.95), 'runtime_initialization_included':False,
               'positive_facets': sum(r['positive_facets'] for r in results),
               'covered_positive_facets': sum(r['positive_facets']-len(r['missing_after_expansion']) for r in results),
               'note':'Evidence membership against frozen gold; not semantic answer accuracy or held-out quality.'}
    write_new(output/'summary.json', summary)
    lines=['# Demo truy xuất cấu trúc + native hybrid', '',
           'Không gọi LLM; câu đã biết. Chỉ kiểm nguồn của các ý positive_support, không tính ý unknown là retrieval miss. Không phải accuracy câu trả lời.', '',
           '| Câu | Thời gian (s) | Facet chưa đủ nguồn sau tìm kiếm | Sau bổ sung |',
           '| --- | ---: | --- | --- |']
    for r in results:
        lines.append(f"| [{r['id']}]({r['id']}.json) | {r['timings_ms']['total_including_initialization']/1000:.2f} | {', '.join(r['missing_after_search']) or '—'} | {', '.join(r['missing_after_expansion']) or '—'} |")
    lines += ['', f"Mean {summary['mean_seconds']:.2f}s; median {summary['median_seconds']:.2f}s; p95 {summary['p95_seconds']:.2f}s.",
              'Đo sau khi mở runtime; chưa gồm cold start hoặc generation/verification.', '']
    for r in results:
        lines += [f"## {r['id']}", '', r['query'], '']
        for chunk in r['chunks']:
            kind = 'Bổ sung' if chunk['id'] in r['added_chunk_ids'] else 'Truy xuất'
            lines += [f"### {kind}: {chunk['citation']}", '', chunk['enriched_text'], '']
    write_new(output/'RETRIEVAL.md', '\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',type=int,action='append',dest='cases')
    args=parser.parse_args()
    asyncio.run(run(args.output,args.cases or [1,2,7,10,12,15,23,27,29,43,49,50]))
