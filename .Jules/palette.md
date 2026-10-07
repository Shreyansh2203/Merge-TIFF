## 2024-11-20 - Surfacing cumulative file sizes

**Learning:** For bounded upload systems with size limits (like the 4MB limit in this app), surfacing cumulative file size before submission prevents frustrating trial-and-error user experiences. It helps users manage their uploads better and avoids wasted round trips. Added `aria-live="polite"` to also help screen-reader users follow size additions.
**Action:** When designing batch file uploads with constraints, display cumulative totals upfront to preempt rejection and ensure the summary is available to assistive tech.
