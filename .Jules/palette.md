## 2024-05-24 - Accessible Disabled States
**Learning:** Native `disabled` attributes remove elements from the tab sequence, preventing keyboard and screen reader users from discovering the button and understanding why it's unavailable.
**Action:** Use `aria-disabled="true"` with JS-level event blocking to keep buttons focusable, allowing `title` or tooltip text to explain the disabled state.
