# Tests

`run_stub_tests.sh` compiles and executes the four workflow graphs with process
stub blocks. It does not run scientific tools.

The `validation/` datasets will hold golden scientific outputs. They are kept
separate from syntax/stub tests because byte-for-byte comparison is not valid
for every bioinformatics format.

