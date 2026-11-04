import './setup-dom.mjs';

import assert from 'node:assert/strict';
import { describe, it, afterEach, beforeEach } from 'node:test';

import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import Home from '../../src/app/page';

const tiff = (name: string, size = 1024) =>
  new File([new Uint8Array(size)], name, { type: 'image/tiff', lastModified: 1000 });

const dropFiles = (dropzone: Element, files: File[]) =>
  fireEvent.drop(dropzone, { dataTransfer: { files } });

const selectFiles = (input: Element, files: File[]) =>
  fireEvent.change(input, { target: { files } });

const fetchMock = (handler: (input: unknown, init?: RequestInit) => Promise<Response>) => {
  const calls: Array<{ input: unknown; init?: RequestInit }> = [];
  const stub = async (input: unknown, init?: RequestInit) => {
    calls.push({ input, init });
    return handler(input, init);
  };
  globalThis.fetch = stub as unknown as typeof fetch;
  return calls;
};

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });

describe('TIFF Merger page', () => {
  beforeEach(() => {
    // jsdom lacks URL.createObjectURL; the component calls window.URL.createObjectURL on success.
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

  it('renders the dropzone with the merge button disabled', () => {
    render(React.createElement(Home));

    assert.ok(screen.getByRole('heading', { name: 'TIFF Merger' }));
    const merge = screen.getByRole('button', { name: /merge tiffs/i });
    assert.equal((merge as HTMLButtonElement).disabled, true);
  });

  it('highlights the dropzone while dragging over it', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', {
      name: /add tiff files/i,
    });

    fireEvent.dragOver(dropzone);
    assert.match(dropzone.className, /active/);

    fireEvent.dragLeave(dropzone);
    assert.doesNotMatch(dropzone.className, /active/);
  });

  it('adds TIFFs via drag and drop and merges them', async () => {
    const calls = fetchMock(async () => new Response(new Blob(['tiff']), { status: 200 }));
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [
      tiff('a.tif'),
      tiff('b.tiff'),
    ]);

    assert.ok(screen.getByText('2 files selected'));

    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByText('Merged 2 files.'));
    });
    assert.equal(calls.length, 1);
    const init = calls[0].init;
    assert.equal((init?.body as FormData).getAll('files').length, 2);
  });

  it('rejects a drop containing no TIFF files', () => {
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [
      new File(['x'], 'notes.txt'),
    ]);

    assert.ok(screen.getByRole('alert').textContent?.includes('Only .tif and .tiff'));
    assert.equal(screen.queryByText(/selected/), null);
  });

  it('adds files picked through the input and lists them', () => {
    render(React.createElement(Home));

    const input = document.querySelector('.file-input') as HTMLInputElement;
    selectFiles(input, [tiff('scan.tif')]);

    assert.ok(screen.getByText('1 file selected'));
    assert.ok(screen.getByText('scan.tif'));
  });

  it('deduplicates files with identical name, size and mtime', () => {
    render(React.createElement(Home));

    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    dropFiles(dropzone, [tiff('dup.tif', 10)]);
    dropFiles(dropzone, [tiff('dup.tif', 10)]);

    assert.ok(screen.getByText('1 file selected'));
  });

  it('caps the selection at 20 files and says so', () => {
    render(React.createElement(Home));

    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    dropFiles(
      dropzone,
      Array.from({ length: 25 }, (_, index) => tiff(`p${index}.tif`, 10))
    );

    assert.ok(screen.getByRole('alert').textContent?.includes('at most 20'));
    assert.ok(screen.getByText('20 files selected'));
  });

  it('removes a file from the list', () => {
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [
      tiff('keep.tif', 10),
      tiff('drop.tif', 10),
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Remove drop.tif' }));

    assert.ok(screen.queryByText('drop.tif') === null);
    assert.ok(screen.getByText('keep.tif'));
  });

  it('refuses to merge more than the 4 MB request cap', async () => {
    const calls = fetchMock(async () => jsonResponse(200, {}));
    render(React.createElement(Home));

    const big = new File([new Uint8Array(5 * 1024 * 1024)], 'big.tif');
    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [big]);

    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    assert.ok(screen.getByRole('alert').textContent?.includes('more than the 4 MB'));
    assert.equal(calls.length, 0);
  });

  it('shows the server-provided error message on failure', async () => {
    fetchMock(async () => jsonResponse(400, { error: 'page 3 is not a TIFF' }));
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('page 3 is not a TIFF'));
    });
  });

  it('falls back to a fixed message when the error body is not JSON', async () => {
    fetchMock(async () => new Response('<html>nope</html>', { status: 500 }));
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('unexpected response'));
    });
  });

  it('falls back to a status message when the error JSON carries no error field', async () => {
    fetchMock(async () => jsonResponse(500, { what: 'no error key' }));
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('status 500'));
    });
  });

  it('reports a timeout as a timeout, not as a generic failure', async () => {
    fetchMock(async () => {
      throw new DOMException('timed out', 'TimeoutError');
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('took too long'));
    });
  });

  it('surfaces a generic failure message', async () => {
    fetchMock(async () => {
      throw new Error('connection reset');
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('connection reset'));
    });
  });
});
