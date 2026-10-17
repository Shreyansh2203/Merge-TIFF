## 2023-10-24 - Accessibility Disabled Button Pattern
**Learning:** Replaced the native `disabled` attribute with `aria-disabled="true"` to ensure the button remains in the tab sequence and can display tooltips for screen reader and keyboard users.
**Action:** When creating disabled buttons, use `aria-disabled` and block clicks in JavaScript instead of using the native `disabled` attribute so context and reasoning can be provided.
