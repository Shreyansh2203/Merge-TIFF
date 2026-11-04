import './setup-dom.mjs';

import assert from 'node:assert/strict';
import { describe, it, afterEach, beforeEach } from 'node:test';

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';

import Home from '../../src/app/page';

const tiff = (name: string, size = 1024) =>
  new File([new Uint8Array(size)], name, { type: 'image/tiff', lastModified: 1000 });

describe('TIFF Merger accessibility', () => {
  beforeEach(() => {
    const windowUrl = window.URL as unknown as {
      createObjectURL?: (blob: Blob) => string;
      revokeObjectURL?: (url: string) => void;
    };
    windowUrl.createObjectURL = () => 'blob:mock-url';
    windowUrl.revokeObjectURL = () => undefined;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the page heading', () => {
    render(React.createElement(Home));
    assert.ok(screen.getByRole('heading', { name: 'TIFF Merger' }));
  });

  it('renders the dropzone with ARIA labeling', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    assert.ok(dropzone);
    assert.ok(dropzone.getAttribute('aria-label'));
  });

  it('renders alerts with role="alert"', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    const { fireEvent } = require('@testing-library/react');
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [new File(['x'], 'notes.txt')] },
    });

    const alert = screen.getByRole('alert');
    assert.ok(alert);
    assert.ok(alert.textContent?.includes('Only .tif and .tiff'));
  });

  it('renders file items with accessible remove buttons', () => {
    render(React.createElement(Home));
    const input = document.querySelector('.file-input') as HTMLInputElement;
    const { fireEvent } = require('@testing-library/react');
    fireEvent.change(input, { target: { files: [tiff('test.tif')] } });

    const removeButton = screen.getByRole('button', { name: /remove test\.tif/i });
    assert.ok(removeButton);
    assert.ok(removeButton.getAttribute('aria-label'));
  });

  it('renders merge button with disabled state when no files', () => {
    render(React.createElement(Home));
    const merge = screen.getByRole('button', { name: /merge tiffs/i });
    assert.equal((merge as HTMLButtonElement).disabled, true);
    assert.ok(merge.getAttribute('aria-busy') === 'false' || !merge.getAttribute('aria-busy'));
  });

  it('uses semantic HTML structure', () => {
    render(React.createElement(Home));
    assert.ok(document.querySelector('main'));
    assert.ok(document.querySelector('h1'));
  });
});
