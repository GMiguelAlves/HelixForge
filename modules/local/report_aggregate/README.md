# REPORT_AGGREGATE

Creates the presentation-neutral Report API v1 object. It reads only values
embedded in manifests or supplied files whose checksums are declared by those
manifests. Missing metrics remain null or absent; status is never converted to
a scientific count.
