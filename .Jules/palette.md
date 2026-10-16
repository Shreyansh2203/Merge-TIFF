## 2026-10-16 - Accessible Disabled Buttons
**Learning:** Native `disabled` attributes remove buttons from the tab sequence, preventing keyboard users from discovering them or reading their tooltips to understand why they are disabled.
**Action:** Use `aria-disabled="true"` with CSS attribute selectors instead of `:disabled`, and ensure JS event handlers check the disabled state to block actions.
