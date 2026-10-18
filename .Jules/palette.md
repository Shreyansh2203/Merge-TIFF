## 2024-05-15 - Use aria-disabled instead of disabled
**Learning:** Native `disabled` attribute removes elements from the tab sequence, which makes disabled states invisible or inaccessible to keyboard navigation and screen readers.
**Action:** Always use `aria-disabled="true"` instead of `disabled` for actionable elements (like buttons) to maintain focusability, allowing for tooltip context, and enforce the disabled state logic in JavaScript.
