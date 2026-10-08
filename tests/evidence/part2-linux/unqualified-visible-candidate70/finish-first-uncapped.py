from pathlib import Path
import json,sys
root=Path(__file__).parent/'uncapped-correctness/first-column'
repo=Path('/home/speak/workspace/github/mcppls-clangd')
context_name='first-column'
reports={a:json.loads((root/a/'report.json').read_text()) for a in ['baseline-before','candidate','baseline-after']}
summary=json.loads((root/'summary.json').read_text())
summary['correction']='Initial control wrongly assumed unlimited engine limit implies index isIncomplete false. Preserve original failed run; offline completion compares actual returned fields and equal legacy incomplete flags, then actual insertions. No latency rerun or default-workload qualification.'
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits']
key=lambda i:json.dumps({f:i.get(f) for f in fields},sort_keys=True)
assert all(len(reports[a]['raw_results'][0]['context_answers'])==4 for a in ['baseline-before','candidate','baseline-after'])
for before,after,final in zip(*(reports[a]['raw_results'][0]['context_answers'] for a in ['baseline-before','candidate','baseline-after'])):
 assert before['phase']==after['phase']==final['phase'] and before['draft']==after['draft']==final['draft']
 if before['phase']=='cold-open':continue
 assert before['isIncomplete']==after['isIncomplete']==final['isIncomplete']
 assert sorted(map(key,before['items']))==sorted(map(key,after['items']))==sorted(map(key,final['items']))
summary['all_stable_item_edit_fields_equal']=True
sys.path.insert(0,str(repo/'tests/probes'))
from completion_insertion import apply,compile_insertion
ctx=json.loads((repo/'tests/probes/contexts/qt'/f'{context_name}.json').read_text())
import re
for arm,d in reports.items():
 proofs=[]
 answers=d['raw_results'][0]['context_answers'];selected=set()
 for phase in ['cold-open','settled-warm','edited']:
  indices=[i for i,a in enumerate(answers) if a['phase']==phase]
  selected.update([indices[0],indices[-1],max(indices,key=lambda i:answers[i]['elapsed_ms'])])
 for i in sorted(selected):
  a=answers[i]
  for sym in ctx['expected']:
   item=next(x for x in a['items'] if re.split(r'[(<]',x.get('filterText',x.get('label','')))[0].strip()==sym and (ctx.get('kind',{}).get(sym) is None or x.get('kind')==ctx['kind'][sym]))
   text=apply(a['draft'],d['position'],item,ctx.get('bindings',{}).get(sym,{}))
   row={'answer':i,'phase':a['phase'],'symbol':sym,'item':item};row.update(compile_insertion(Path('/home/speak/test/mcpp/qt-demo'),Path('/home/speak/test/mcpp/qt-demo/src/main.cpp'),text));proofs.append(row)
 (root/arm/'insertions.json').write_text(json.dumps(proofs,indent=2)+'\n')
 assert all(x['exit_code']==0 for x in proofs)
 summary['arms'][arm]['selected_gcc_insertions']=len(proofs)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('MATCHED_PASS',flush=True)
