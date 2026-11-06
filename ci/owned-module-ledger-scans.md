# Bounded ledger scans and candidate leases

Patch 0045 reduces cold owned-cache lookup and admission work. A fallback
lookup previously attempted a lease open for every slot, including unused
slots and records for unrelated module keys. A 4096-slot cache therefore
performed thousands of failed file operations for one absent key. Admission
also read each of the two record banks with a separate positional transfer.

The implementation reads sixteen adjacent slot pairs at a time while holding
the existing ledger lock. Each pair retains checksum, sequence, kind and field
validation, selecting the same newest valid bank as an individual read. The
persistent layout, slot limit, payload charges and durability protocol do not
change. A truncated or ambiguous record fails the scan.

Lookup copies only stable matching slot numbers, releases the ledger lock,
and then acquires their leases. The slot list is a filter. After acquisition,
the existing lookup rereads the record and checks the key, generation, lease
identity, namespace identity, payload size, complete bundle inventory and
caller validation. Concurrent publication or collection cannot turn the
earlier filter into authority to use a generation. Missing keys are not cached
between calls. The existing validated slot hint remains the first attempt.

Admission uses the same bounded reads under its existing lock. It accounts
for every selected record, checks the charged total for overflow, and obtains
and validates an exclusive lease before selecting a free slot. Pressure,
cleanup and the durable transition to a reservation retain their existing
behavior.

`PrerequisiteModulesTest.cpp` covers a seventeen-slot table and its partial
chunk, publication by another cache instance after an earlier miss, validated
hints, live lease protection, admission limits, a truncated ledger, and an
ambiguous unused tail bank. Existing owned-cache tests retain changed-payload,
replacement, crash, collection and concurrency controls. Complete native and
image builds and four-host functional and cold/warm performance acceptance
remain required before the patch leaves `stabilizing`.
