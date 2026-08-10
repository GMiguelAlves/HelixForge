# REPORT_CONTEXT

Validates the Report API v1 inventory and all explicit manifests. Association
uses manifest types and stable IDs; staged path order and filenames have no
scientific meaning. Missing optional components are retained as
`not_requested`, never converted to zero.
