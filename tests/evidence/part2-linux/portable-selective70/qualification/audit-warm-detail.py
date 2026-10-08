from pathlib import Path
import json,statistics,sys
root=Path(sys.argv[1]);audit={'scope':'Private instrumented GCC70 attribution only; not release qualification. Span sums are nested and not additive.','arms':{}}
names=['Sema completion','Completion module validation','Completion textual validation','Completion prepare instance','Completion begin source','Completion end source','Completion teardown','Completion semantic execution','Populate CodeCompleteResult','Merge and score results','Completion assemble results','Completion assemble candidate','Completion candidate string','Completion candidate builder','Completion documentation symbol ID']
for mode in ['headers','modules']:
 p=root/mode;d=json.loads((p/'report.json').read_text());w=json.loads((p/'workload.json').read_text());assert d['all_semantic_requests_passed'] and not w['compiler_overlap'] and not w['multiple_engine_overlap'] and not w['errors'] and w['watcher_stopped']
 ev=[x for x in json.loads((p/'trace.json').read_text())['traceEvents'] if x.get('ph')=='X'];sema=sorted([x for x in ev if x['name']=='Sema completion'],key=lambda x:x['ts']);assert len(sema)==8
 warm=[]
 for i in [1,3,5,7]:
  s=sema[i];row={}
  for name in names:
   spans=[x for x in ev if x['name']==name and x.get('tid')==s.get('tid') and x['ts']>=s['ts'] and x['ts']+x['dur']<=s['ts']+s['dur']+1]
   row[name]={'count':len(spans),'sum_ms':sum(x['dur'] for x in spans)/1000}
  warm.append(row)
 med={name:round(statistics.median(x[name]['sum_ms'] for x in warm),4) for name in names}
 audit['arms'][mode]={'semantic_pass':True,'sampled_workload_pass':True,'warm_requests':warm,'median_span_sum_ms':med};print(mode,med)
(root/'attribution-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
