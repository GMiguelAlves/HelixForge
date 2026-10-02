# MERGE_FASTQ_SINGLE

Native single-end companion to `MERGE_FASTQ`. It concatenates technical runs
in their declared order, preserves gzip members and compatibility filenames,
and records input/output checksums. It never creates an artificial R2 file.
