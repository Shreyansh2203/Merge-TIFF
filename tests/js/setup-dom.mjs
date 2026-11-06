// Minimal jsdom environment for node:test component tests.
// Loaded before @testing-library/react and the component under test.
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
});

for (const key of [
  'window',
  'document',
  'navigator',
  'HTMLElement',
  'HTMLButtonElement',
  'HTMLInputElement',
  'Node',
  'NodeList',
  'Event',
  'CustomEvent',
  'KeyboardEvent',
  'MouseEvent',
  'DragEvent',
  'DataTransfer',
  'File',
  'FileList',
  'Blob',
]) {
  if (!(key in globalThis) && dom.window[key] !== undefined) {
    globalThis[key] = dom.window[key];
  }
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
