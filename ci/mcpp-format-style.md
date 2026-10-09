# Pinned mcpp formatting fallback

FEATURE-43 maps to product issue Sunrisepeak/mcpp-language-server#43. It is a
product feature rather than an upstream defect. Ledger validation accepts this
namespace without assigning a false UP identifier.

0012 registers a C++-only `mcpp` preset from the exact `.clang-format` at
mcpp-community/mcpp commit 74bcb859e60afc71ad759540d2de5344dda400e9. The original
snapshot and golden module fixture are in clangd/test/Inputs/mcpp-style.
Clang 23 produces identical output for the preset and snapshot. Project
configuration and an explicit user style still win. Two focused lit tests pass;
ConfigParseTest also checks the preset fields and unsupported language.

Packaging declares `format-style-mcpp` only after formatting through the final
stripped clangd bytes passes a canary. The product must require that capability
before sending this preset. No remote style lookup or project file writing is
involved. The preset remains stabilizing until the joint acceptance completes.
