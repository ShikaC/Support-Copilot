# Synthetic quality report contract fixtures

These hand-authored reports are shared by the React schema tests and Java report reader tests. They contain no customer data, model responses, downloaded evaluation cases, or measured quality results.

`live.json` contains three synthetic outcomes (one normal, one insufficient-evidence result, one timeout). `business.json` repeats those three cases at concurrency 1 and 2, so it has six samples and three distinct cases. Unmeasured human-review and business metrics remain zero or null.

`manifest.json` pins the exact SHA-256 bytes of the two reports for the Java reader integrity checks. The source-file checksum inside each report is a synthetic schema input, not evidence of an external source file. If a report changes, regenerate its manifest checksum with Node crypto and rerun both consumers. These files are test inputs and must never be presented as live evaluation evidence.
