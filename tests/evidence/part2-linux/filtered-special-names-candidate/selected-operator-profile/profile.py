from pathlib import Path
import json,subprocess,hashlib
base=Path(__file__).parent;out=base/'selected-operator-profile';out.mkdir(exist_ok=True)
if any(out.iterdir()):raise SystemExit('refusing overwrite of profile evidence')
src=Path('/tmp/mcppls-filtered-special-names/clang/lib/Serialization/ASTReader.cpp')
text=src.read_text();text='#include <array>\n#include <time.h>\n'+text
anchor='  auto NameMayMatch = takeCompletionNameFilter(DC);\n  DeclsMap Decls;'
addition='''  auto NameMayMatch = takeCompletionNameFilter(DC);
  bool ProfileSelected = NameMayMatch && isa<NamespaceDecl>(DC);
  std::array<uint64_t, 16> ProfileCounts{}, ProfileCPU{};
  auto ThreadCPU = [] {
    timespec T{};
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &T);
    return uint64_t(T.tv_sec) * 1000000000 + T.tv_nsec;
  };
  DeclsMap Decls;'''
assert text.count(anchor)==1;text=text.replace(anchor,addition)
anchor='      NamedDecl *ND = cast<NamedDecl>(GetDecl(ID));'
addition='''      auto ProfileBegin = ProfileSelected ? ThreadCPU() : 0;
      NamedDecl *ND = cast<NamedDecl>(GetDecl(ID));
      if (ProfileSelected) {
        auto Kind = unsigned(ND->getDeclName().getNameKind());
        ++ProfileCounts[Kind];
        ProfileCPU[Kind] += ThreadCPU() - ProfileBegin;
      }'''
position=text.index(anchor,text.index('void ASTReader::completeVisibleDeclsMap('));text=text[:position]+addition+text[position+len(anchor):]
anchor='  // Selected names are complete; the context as a whole may still contain'
addition='''  if (ProfileSelected) {
    llvm::errs() << "SelectedDeclProfile {\\"context\\":\\""
                 << cast<NamespaceDecl>(DC)->getQualifiedNameAsString()
                 << "\\",\\"kinds\\":[";
    for (unsigned I = 0; I != ProfileCounts.size(); ++I) {
      if (I) llvm::errs() << ",";
      llvm::errs() << "{\\"kind\\":" << I << ",\\"ids\\":" << ProfileCounts[I]
                   << ",\\"get_decl_cpu_ns\\":" << ProfileCPU[I] << "}";
    }
    llvm::errs() << "]}\\n";
  }

  // Selected names are complete; the context as a whole may still contain'''
assert text.count(anchor)==1;text=text.replace(anchor,addition)
profile_src=out/'ASTReader.cpp';profile_src.write_text(text)
entry=next(e for e in json.loads((base/'compile-args.json').read_text()) if e['name']=='ASTReader.cpp')
args=entry['argv'].copy();args[args.index('-c')+1]=str(profile_src);args[args.index('-o')+1]=str(out/'ASTReader.cpp.o');args+=['-I'+str(src.parent)]
(out/'compile-args.json').write_text(json.dumps(args,indent=2)+'\n')
with (out/'compile.log').open('w') as f:r=subprocess.run(args,cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT)
print('compile',r.returncode,flush=True)
if r.returncode:raise SystemExit(r.returncode)
args=json.loads((base/'clangd-link-args.json').read_text());args=[str(out/'ASTReader.cpp.o') if a.endswith('/lib-objects/ASTReader-completion-spelling.cpp.o') else a for a in args];args[args.index('-o')+1]=str(out/'clangd')
(out/'link-args.json').write_text(json.dumps(args,indent=2)+'\n')
with (out/'link.log').open('w') as f:r=subprocess.run(args,cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT)
print('link',r.returncode,flush=True)
if r.returncode:raise SystemExit(r.returncode)
(out/'identity.json').write_text(json.dumps({'scope':'Private name-kind/count and thread CPU attribution only; compiler/build overlap and clock overhead, not latency qualification or production patch.','base_production_source_commit':'31c43d3a2','profile_source_sha256':hashlib.sha256(profile_src.read_bytes()).hexdigest(),'engine_sha256':hashlib.sha256((out/'clangd').read_bytes()).hexdigest()},indent=2)+'\n')
