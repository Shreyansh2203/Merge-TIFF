## 2024-10-24 - Accessible Disabled States
**Learning:** Using the native `disabled` attribute on interactive elements like buttons removes them from the tab sequence. This prevents screen reader and keyboard users from navigating to the element to understand why it's disabled, as they can't access any explanatory tooltips or ARIA properties.
**Action:** Use `aria-disabled="true"` combined with JavaScript logic to prevent the action, and CSS `[aria-disabled="true"]` to handle disabled styling, ensuring elements remain discoverable.
