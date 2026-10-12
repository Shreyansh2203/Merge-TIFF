## 2024-05-16 - File Upload Size Limits and A11y
**Learning:** When strict file size limits exist (e.g., 4MB total), surfacing individual and total file sizes is critical for user understanding. Adding `aria-live="polite"` to the summary ensures screen readers are aware when files are added or removed, making the limit constraints discoverable for all users.
**Action:** Always display file sizes in upload queues, especially when there are strict limits, and use live regions to announce file count/size changes dynamically.
