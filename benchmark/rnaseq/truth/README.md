# Truth artifacts

Generated truth files are not committed. The generation workflow places them below a directory
named by the SHA-256 of `synthetic_design.json` and the prepared reference
manifest. Required files are listed in that JSON.

Gene/transcript identifiers, sample order and condition levels are immutable.
Every metric joins by explicit IDs; row position is never treated as identity.
Generated truth tables and simulated read checksums are included in the audit
bundle so the exact simulation can be regenerated.
