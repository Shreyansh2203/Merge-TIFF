## 2025-01-20 - Transparent Upload Limits in Dropzone
**Learning:** Hard backend limits (like request size maximums) can cause frustrating post-action errors if hidden from the user until upload time. Users are better served when these bounds are surfaced proactively in file-selection summaries and dropzone areas.
**Action:** When working on file upload forms with strict size or quantity constraints, display the limit directly in the dropzone label (and its `aria-label`) and dynamically show the current footprint compared to the limit as files are selected.
