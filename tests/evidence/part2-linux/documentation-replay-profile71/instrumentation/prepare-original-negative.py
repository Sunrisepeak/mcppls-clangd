from pathlib import Path
import json,shlex,hashlib
root=Path('/tmp/mcppls-part2-doc-detail71');root.mkdir(exist_ok=False)
source=Path('/dev/shm/mcppls-part2-completion-inputs71');rel='clang-tools-extra/clangd/'
for name in ['CodeComplete.cpp','CodeCompletionStrings.cpp']:
 s=(source/rel/name).read_text()
 if name=='CodeComplete.cpp':
  old='''        const auto DocComment = getDocComment(*ASTCtx, *C.SemaResult,
                                              /*CommentsFromHeaders=*/false);
        SetDoc(formatDocumentation(*SemaCCS, DocComment));'''
  new='''        trace::Span Detail("Candidate documentation total");
        auto DocComment = [&] {
          trace::Span Detail("Candidate documentation lookup");
          return getDocComment(*ASTCtx, *C.SemaResult,
                               /*CommentsFromHeaders=*/false);
        }();
        auto Formatted = [&] {
          trace::Span Detail("Candidate documentation annotations");
          return formatDocumentation(*SemaCCS, DocComment);
        }();
        trace::Span Parse("Candidate documentation parse");
        SetDoc(Formatted);'''
  assert s.count(old)==1;s=s.replace(old,new)
 else:
  s=s.replace('#include "Config.h"','#include "Config.h"\n#include "support/Trace.h"')
  for operand in ['ND','&Decl']:
   old='    RC = getCompletionComment(Ctx, '+operand+');';assert s.count(old)==1
   new='''    RC = [&] {
      trace::Span Detail("Documentation raw redeclaration lookup");
      auto *Comment = getCompletionComment(Ctx, '''+operand+''');
      SPAN_ATTACH(Detail, "found", bool(Comment));
      return Comment;
    }();''';s=s.replace(old,new)
  old='RC->getFormattedText(Ctx.getSourceManager(), Ctx.getDiagnostics())';assert s.count(old)==2
  s=s.replace(old,'''[&] {
          trace::Span Detail("Documentation raw text formatting");
          return RC->getFormattedText(Ctx.getSourceManager(), Ctx.getDiagnostics());
        }()''')
 (root/name).write_text(s)
entries=json.loads(Path('/home/speak/workspace/github/mcppls-clangd/build-linux-x64/compile_commands.json').read_text());recipes=[]
for name in ['CodeComplete.cpp','CodeCompletionStrings.cpp']:
 e=next(x for x in entries if x['file'].endswith('/clangd/'+name));a=shlex.split(e['command']);a=[x.replace('/home/speak/workspace/github/mcppls-clangd/llvm-project',str(source)) for x in a];a[a.index('-c')+1]=str(root/name);a[a.index('-o')+1]=str(root/(name+'.o'));a.insert(1,'-I'+str(source/rel));recipes.append({'name':name,'argv':a})
(root/'compile.json').write_text(json.dumps(recipes,indent=2)+'\n')
link=json.loads(Path('/tmp/mcppls-part2-completion-inputs71-build/clangd-link-args.json').read_text())
for name in ['CodeComplete.cpp','CodeCompletionStrings.cpp']:
 indexes=[i for i,x in enumerate(link) if x.endswith('/obj.clangDaemon.dir/'+name+'.o')];assert len(indexes)==1;link[indexes[0]]=str(root/(name+'.o'))
link[link.index('-o')+1]=str(root/'clangd');(root/'link.json').write_text(json.dumps(link,indent=2)+'\n')
(root/'identity.json').write_text(json.dumps({'scope':'Private71 trace instrumentation only. Two objects rebuilt; unchanged compatible71 consumers reused. Not production or release qualification.','source_commit':'0ea8fbc5f46c38e9abcde6ef2b360829fdbc1d0d','instrumented_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['CodeComplete.cpp','CodeCompletionStrings.cpp']}},indent=2)+'\n')
