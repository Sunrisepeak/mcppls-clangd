from pathlib import Path
import json,hashlib,collections,sys,gzip
q=Path(__file__).parent;sys.path.insert(0,str(q))
from tree_resource_window import stable_tree_window
root=q/'resource-four-arm-v2';summary=json.loads((root/'summary.json').read_text())
assert summary['latency_qualification'] is False and summary['all_explicit_performance_checks_pass']
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits','documentation'];key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
count=proof_count=0;details={}
for arm,data in summary['arms'].items():
 folder=root/arm;payload=gzip.decompress((folder/'report.json.gz').read_bytes());d=json.loads(payload)
 reference_payload=gzip.decompress((q/'four-arm'/arm/'report.json.gz').read_bytes());reference=json.loads(reference_payload)
 assert d['latency_qualification'] is False and d['starts']==3 and d['rounds']==30 and d['all_semantic_requests_passed']
 assert d['engine_sha256']==reference['engine_sha256']==data['engine_sha256'] and d['draft_source_sha256']==reference['draft_source_sha256']
 assert d['position']==reference['position'] and d['context']==reference['context']
 assert (folder/'cdb/compile_commands.json').read_bytes()==(q/'four-arm'/arm/'cdb/compile_commands.json').read_bytes()
 assert len(d['raw_results'])==len(reference['raw_results'])==3
 windows=[]
 for raw,old in zip(d['raw_results'],reference['raw_results']):
  assert raw['outcome']=='pass' and raw['exit_code']==0 and raw['readers_stopped']
  aa=raw['context_answers'];assert len(aa)==len(old['context_answers'])==62
  assert collections.Counter(a['phase'] for a in aa)=={'cold-open':1,'settled-warm':31,'edited':30}
  for a,b in zip(aa,old['context_answers']):
   assert a['semantic_pass'] and a['origin']['sema']>0 and not a['missing'] and not a['untyped_expected'] and not a['semantic_origin_failed'] and not a['index_origin_failed']
   assert a['phase']==b['phase'] and a['draft']==b['draft']
   assert collections.Counter(map(key,a['items']))==collections.Counter(map(key,b['items']))
  w=stable_tree_window(raw);w['rss_p95_kib']=w['memory']['tree_rss_sum_kib']['p95'];w['pss_p95_kib']=w['memory']['tree_pss_kib']['p95'];w['private_p95_kib']=w['memory']['tree_private_kib']['p95'];windows.append(w);count+=len(aa)
 assert windows==data['stable_observed_tree_resources']['windows']
 workload=json.loads(gzip.decompress((folder/'workload.json.gz').read_bytes()));assert workload['samples'] and not workload['errors'] and not workload['compiler_overlap'] and not workload['multiple_engine_overlap'] and workload['watcher_stopped']
 assert all(not row['compilers'] and len({e['pgid'] for e in row['engines']})<=1 for row in workload['samples'])
 assert 'Traceback (most recent call last)' not in (folder/'run.log').read_text()
 reuse=data['reused_raw_selected_insertions'];proof=(q/'four-arm'/arm/'selected-insertions.json').read_bytes()
 assert hashlib.sha256(proof).hexdigest()==reuse['proof_sha256'] and hashlib.sha256(reference_payload).hexdigest()==reuse['raw_report_sha256']
 proofs=json.loads(proof)['proofs'];assert len(proofs)==reuse['count'] and all(p['exit_code']==0 for p in proofs);proof_count+=len(proofs)
 details[arm]={'report_sha256':hashlib.sha256(payload).hexdigest(),'stable_windows':windows,'reused_raw_selected_insertions':len(proofs)}
for mode,c in summary['resource_comparisons'].items():
 b=summary['arms']['baseline-'+mode]['stable_observed_tree_resources'];a=summary['arms']['candidate-'+mode]['stable_observed_tree_resources']
 assert c['cpu_ratio_conservative']==a['cpu_upper_ms']/b['cpu_lower_ms']<1.2
 for metric in ['rss','pss','private']:assert c[metric+'_observed_p95_max_ratio']==a[metric+'_p95_max_kib']/b[metric+'_p95_max_kib']<1.2
assert count==744 and proof_count==82
report={'scope':'Final72 versus portable70 observed process-tree replay only. All elapsed times excluded; no physical cache/unsampled descendants/long-term/full-release proof. Original v1 observer failure excluded.','arms':details,'typed_sema_checks':count,'reused_raw_insertions':proof_count,'resource_comparisons':summary['resource_comparisons'],'all_checked_requirements_passed':True}
assert report==json.loads((q/'resource-four-arm-v2-audit.json').read_text())
print(json.dumps({'typed_sema_checks':count,'reused_raw_insertions':proof_count,'observed_tree_checks_pass':True}))
