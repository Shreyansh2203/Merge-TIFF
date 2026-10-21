## 2026-10-21 - Use aria-disabled instead of disabled for buttons
**Learning:** Using the native `disabled` attribute on buttons removes them from the tab sequence, preventing keyboard users from focusing them to read explanatory tooltips about why they are disabled.
**Action:** Use `aria-disabled="true"` instead of `disabled`, apply styles via `[aria-disabled="true"]`, and ensure click handlers return early when this attribute is set.
