# Retained effort diagnostic evidence v1

Permanent, curated archive of the completed 2026-10-02 diagnostic, frozen source `95b07ea260d19771810e7748eb61fbbb50db2174`. This archive contains reports, original diagnostic tools, aggregate results for all 33 variants, verification evidence and selected witnesses. It contains no frozen production-source tree and no full duplicate JSONL run logs.

- Read [REPORT_TH.md](REPORT_TH.md) together with [ERRATA_TH.md](ERRATA_TH.md).
- [all_metrics.csv](all_metrics.csv): all 8 groups / 11 subcases / 3 effort levels, including failures/worsening.
- [recovery.csv](recovery.csv), [delivery_decomposition.csv](delivery_decomposition.csv), [summary_outcomes.json](summary_outcomes.json): accounting and recovery.
- [determinism_baseline_matrix.json](determinism_baseline_matrix.json): persisted repeated-record equality, original-kernel e=1 agreement and per-tick witness hashes.
- [selected_evidence.json](selected_evidence.json): selected original records; selection rules/provenance are in the file, not favorable-outcome sampling.
- manifest/checks/final_audit/completed/worsening and original before/after source/tool hash inventories are retained.
- [provenance.json](provenance.json) maps every byte-identical retained file and derived evidence to original inputs and hashes. `artifact_hashes.original.json` includes hashes for omitted logs; `archive_hashes.json` hashes the permanent archive itself.

`original_tools/` preserves the original Python files byte-for-byte. They are evidence, not a portable runner: their relative paths expect the original `out/effort-diagnostic-95b07ea-20261002/` layout and the original frozen source path in manifest. A future explicitly authorized reproduction must restore that layout or review a separate path-only adaptation and verify the frozen source hashes. Do not execute these tools as part of reading this archive. No tools were rerun to create this archive.

No policy/controller was implemented or installed. [Controller specification v1](../../../docs/food_effort_controller_v1/SPEC_TH.md) is a design proposal, not verified safety or implementation authorization.
