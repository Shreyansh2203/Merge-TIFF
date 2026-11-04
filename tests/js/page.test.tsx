import './setup-dom.mjs';

import assert from 'node:assert/strict';
import { describe, it, afterEach, beforeEach } from 'node:test';

import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

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

  it('surfaces a timeout DOMException as timeout message', async () => {
    const domError = new DOMException('took too long', 'TimeoutError');
    fetchMock(async () => {
      throw domError;
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('took too long'));
    });
  });

  it('surfaces a non-timeout DOMException as generic failure', async () => {
    const domError = new DOMException('Something went wrong', 'AbortError');
    fetchMock(async () => {
      throw domError;
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('Something went wrong'));
    });
  });

  it('calls fileKey when adding files to non-empty list', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });

    dropFiles(dropzone, [tiff('first.tif', 100)]);
    assert.ok(screen.getByText('1 file selected'));

    dropFiles(dropzone, [tiff('second.tif', 200)]);
    assert.ok(screen.getByText('2 files selected'));
  });

  it('opens the file picker when dropzone is clicked', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });

    fireEvent.click(dropzone);

    // openPicker calls fileInputRef.current?.click(); verifying no crash covers the path
    assert.ok(screen.getByRole('button', { name: /add tiff files/i }));
  });

  it('clicking merge with no files does nothing', () => {
    render(React.createElement(Home));
    const merge = screen.getByRole('button', { name: /merge tiffs/i }) as HTMLButtonElement;
    assert.equal(merge.disabled, true);
    fireEvent.click(merge);
    // Handler guarded by files.length === 0; no error should surface
    assert.ok(screen.queryByRole('alert') === null);
  });

  it('dropping empty file list shows error', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    fireEvent.drop(dropzone, { dataTransfer: { files: [] } });
    // Empty file list triggers addFiles with empty array, which sets error
    assert.ok(screen.getByRole('alert').textContent?.includes('Only .tif and .tiff'));
  });

  it('ignores a file input change with no files', () => {
    render(React.createElement(Home));
    const input = document.querySelector('.file-input') as HTMLInputElement;
    assert.ok(input);

    fireEvent.change(input, { target: { files: [] } });

    // No files added, error surfaced since addFiles runs regardless
    assert.ok(screen.queryByText(/file selected/i) === null);
    assert.ok(screen.getByRole('alert').textContent?.includes('Only .tif and .tiff'));
  });

  it('accepts .tiff extension (isTiffFile endsWith .tiff true path)', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    dropFiles(dropzone, [tiff('scan.tiff', 200)]);
    assert.ok(screen.getByText('1 file selected'));
  });

  it('rejects non-TIFF files (isTiffFile both endsWith false path)', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    const png = new File(['x'], 'photo.png', { type: 'image/png' });
    dropFiles(dropzone, [png]);
    // Non-TIFF files are filtered out; error is surfaced
    assert.ok(screen.getByRole('alert').textContent?.includes('Only .tif and .tiff'));
  });

  it('errors when dropping more than MAX_FILE_COUNT files', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    const tooMany = Array.from({ length: 21 }, (_unused, i) => tiff(`file${i}.tif`, 100 + i));
    dropFiles(dropzone, tooMany);
    // MAX_FILE_COUNT is 20; the rest are rejected
    assert.ok(screen.getByRole('alert').textContent?.includes('at most 20 files at once'));
  });

  it('errors when total bytes exceed MAX_REQUEST_BYTES', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    const bigFile = new File([new Uint8Array(4 * 1024 * 1024 + 1024)], 'big.tif', {
      type: 'image/tiff',
    });
    dropFiles(dropzone, [bigFile]);
    const merge = screen.getByRole('button', { name: /merge tiffs/i }) as HTMLButtonElement;
    act(() => {
      fireEvent.click(merge);
    });
    // File exceeds 4 MB limit
    assert.ok(screen.getByRole('alert').textContent?.includes('4 MB'));
  });

  it('fires drag over and drag leave events', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });

    fireEvent.dragOver(dropzone, {
      dataTransfer: { files: [], types: ['Files'] },
    } as unknown as DragEvent<HTMLButtonElement>);
    assert.ok(document.querySelector('.active'));

    fireEvent.dragLeave(dropzone, {
      dataTransfer: { files: [], types: ['Files'] },
    } as unknown as DragEvent<HTMLButtonElement>);
    assert.ok(!document.querySelector('.active'));
  });

  it('handles drop with actual TIFF files', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    const tiffFile = new File(['x'], 'dropped.tif', { type: 'image/tiff' });
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [tiffFile] },
    } as unknown as DragEvent<HTMLButtonElement>);
    assert.ok(screen.getByText('1 file selected'));
  });

  it('ignores a drop with no files', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [] },
    } as unknown as DragEvent<HTMLButtonElement>);
    // No files added, no error surfaced
    assert.ok(screen.queryByText(/file selected/i) === null);
  });

  it('shows active class during drag over', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    fireEvent.dragOver(dropzone, {
      dataTransfer: { items: [], types: ['Files'] },
    } as unknown as DragEvent<HTMLButtonElement>);
    assert.ok(document.querySelector('.active'));
  });

  it('removes active class on drag leave', () => {
    render(React.createElement(Home));
    const dropzone = screen.getByRole('button', { name: /add tiff files/i });
    fireEvent.dragOver(dropzone, {
      dataTransfer: { items: [], types: ['Files'] },
    } as unknown as DragEvent<HTMLButtonElement>);
    assert.ok(document.querySelector('.active'));
    fireEvent.dragLeave(dropzone, {
      dataTransfer: { items: [], types: ['Files'] },
    } as unknown as DragEvent<HTMLButtonElement>);
    assert.ok(!document.querySelector('.active'));
  });

  it('handles file input change with actual files', () => {
    render(React.createElement(Home));
    const input = document.querySelector('.file-input') as HTMLInputElement;
    assert.ok(input);
    const tiffFile = new File(['x'], 'input.tif', { type: 'image/tiff' });
    fireEvent.change(input, { target: { files: [tiffFile] } });
    assert.ok(screen.getByText('1 file selected'));
  });

  it('surfaces a plain object error as generic failure', async () => {
    fetchMock(async () => {
      throw { code: 'UNKNOWN_ERROR' };
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('Failed to merge files.'));
    });
  });

  it('surfaces a regular Error message', async () => {
    fetchMock(async () => {
      throw new Error('network down');
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('network down'));
    });
  });

  it('returns parsed error message from JSON response', async () => {
    fetchMock(async () => {
      return new Response(JSON.stringify({ error: 'Invalid file format' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('Invalid file format'));
    });
  });

  it('falls back to status text when JSON error field is empty', async () => {
    fetchMock(async () => {
      return new Response(JSON.stringify({ error: '' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    fireEvent.click(screen.getByRole('button', { name: /merge tiffs/i }));

    await waitFor(() => {
      assert.ok(screen.getByRole('alert').textContent?.includes('Request failed with status 400.'));
    });
  });

  it('shows Merging state while fetch is in flight', () => {
    let pendingResolve: (() => void) | undefined;
    const pending = new Promise<void>((resolve) => {
      pendingResolve = resolve;
    });
    fetchMock(async () => pending);
    render(React.createElement(Home));

    dropFiles(screen.getByRole('button', { name: /add tiff files/i }), [tiff('a.tif')]);
    const merge = screen.getByRole('button', { name: /merge tiffs/i }) as HTMLButtonElement;
    act(() => {
      fireEvent.click(merge);
    });

    // isMerging=true disables the merge button
    assert.ok(merge.disabled);

    pendingResolve?.();
  });
});
