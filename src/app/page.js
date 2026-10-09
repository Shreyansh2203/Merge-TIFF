'use client';

import { useRef, useState } from 'react';

import { buildOutputName } from '../lib/downloadName.mjs';

const MAX_FILE_COUNT = 20;
const MAX_REQUEST_BYTES = 4 * 1024 * 1024;
// The function's own maxDuration is 30 s (vercel.json); the client waits a
// little longer so a slow upload does not get cut off mid-merge, then gives up
// instead of spinning forever on a stalled connection.
const MERGE_TIMEOUT_MS = 90_000;

function fileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function totalBytes(fileList) {
  return fileList.reduce((sum, file) => sum + file.size, 0);
}

export default function Home() {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const fileInputRef = useRef(null);

  const openPicker = () => {
    fileInputRef.current?.click();
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(Array.from(e.target.files));
    }
    e.target.value = '';
  };

  const addFiles = (newFiles) => {
    const tiffFiles = newFiles.filter((file) =>
      /\.tiff?$/i.test(file.name)
    );

    if (tiffFiles.length === 0) {
      setError('Only .tif and .tiff files can be merged.');
      return;
    }

    const existing = new Set(files.map(fileKey));
    const unique = tiffFiles.filter((file) => !existing.has(fileKey(file)));
    // The server rejects more than MAX_FILE_COUNT files; keep what fits and
    // say so up front rather than failing after the upload has round-tripped.
    const accepted = unique.slice(0, Math.max(MAX_FILE_COUNT - files.length, 0));

    if (accepted.length < unique.length) {
      setError(
        `This service merges at most ${MAX_FILE_COUNT} files at once; the rest were not added.`
      );
    } else {
      setError('');
    }
    setNotice('');

    setFiles([...files, ...accepted]);
  };

  const removeFile = (indexToRemove) => {
    setFiles((prev) => prev.filter((_, index) => index !== indexToRemove));
    setError('');
    setNotice('');
  };

  const readErrorMessage = async (response) => {
    const body = await response.text();
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed.error === 'string' && parsed.error) {
        return parsed.error;
      }
    } catch {
      return 'The server returned an unexpected response.';
    }
    return `Request failed with status ${response.status}.`;
  };

  const handleMerge = async () => {
    if (files.length === 0) {
      return;
    }

    // The server enforces the same cap, but finding out before uploading is
    // the difference between an instant message and a wasted 4 MB round trip.
    if (totalBytes(files) > MAX_REQUEST_BYTES) {
      setError(
        'These files add up to more than the 4 MB this service accepts in one request. Remove some and try again.'
      );
      return;
    }

    setIsMerging(true);
    setError('');
    setNotice('');

    try {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file);
      });

      const response = await fetch('/api/merge', {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(MERGE_TIMEOUT_MS),
      });

      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = buildOutputName(files.map((file) => file.name));
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Revoking on a 0 ms timeout can fire before the browser has started
      // reading the blob (a known Firefox failure mode that drops the
      // download), so give the download time to actually begin.
      window.setTimeout(() => window.URL.revokeObjectURL(url), 10_000);

      setNotice(`Merged ${files.length} file${files.length === 1 ? '' : 's'}.`);
    } catch (mergeError) {
      if (mergeError instanceof DOMException && mergeError.name === 'TimeoutError') {
        setError(
          'The merge took too long and was stopped. Try fewer or smaller files.'
        );
      } else {
        setError(
          mergeError instanceof Error
            ? mergeError.message
            : 'Failed to merge files.'
        );
      }
    } finally {
      setIsMerging(false);
    }
  };

  const currentBytes = totalBytes(files);
  const isOverSizeLimit = currentBytes > MAX_REQUEST_BYTES;
  const displayError = isOverSizeLimit
    ? 'These files add up to more than the 4 MB this service accepts in one request. Remove some and try again.'
    : error;

  return (
    <main className="container">
      <div className="glass-panel">
        <h1>TIFF Merger</h1>
        <p className="subtitle">Combine multiple TIFF files effortlessly.</p>

        {displayError && (
          <p className="alert" role="alert">
            {displayError}
          </p>
        )}
        {notice && (
          <p className="alert alert-success" role="status">
            {notice}
          </p>
        )}

        <button
          type="button"
          className={`dropzone ${isDragging ? 'active' : ''}`}
          onClick={openPicker}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          aria-label="Add TIFF files. Drag and drop, or press Enter to browse."
        >
          <span className="dropzone-icon" aria-hidden="true">
            &#128196;
          </span>
          <span className="dropzone-text">
            Drag &amp; drop TIFF files here,
            <br />
            or click to select
          </span>
        </button>

        <input
          type="file"
          multiple
          accept=".tif,.tiff"
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="file-input"
          tabIndex={-1}
          aria-hidden="true"
        />

        {files.length > 0 && (
          <>
            <p className="file-list-summary">
              {files.length} file{files.length === 1 ? '' : 's'} selected ({(currentBytes / (1024 * 1024)).toFixed(2)} MB)
            </p>
            <div className="file-list">
              {files.map((file, index) => (
                <div key={`${fileKey(file)}-${index}`} className="file-item">
                  <span>{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    title={`Remove ${file.name}`}
                    aria-label={`Remove ${file.name}`}
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        <button
          type="button"
          className="btn-primary"
          onClick={handleMerge}
          disabled={files.length === 0 || isMerging || isOverSizeLimit}
          aria-busy={isMerging}
          title={isOverSizeLimit ? 'Total file size exceeds the 4MB limit' : undefined}
        >
          {isMerging ? (
            <>
              <span className="spinner" aria-hidden="true" /> Merging...
            </>
          ) : (
            'Merge TIFFs'
          )}
        </button>
      </div>
    </main>
  );
}
