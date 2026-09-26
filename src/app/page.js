'use client';

import { useRef, useState } from 'react';

const MAX_STEM_LENGTH = 40;
const MAX_OUTPUT_STEM_LENGTH = 120;
const UNSAFE_FILENAME_CHARS = /[\u0000-\u001f\u007f/\\:*?"<>|]/g;

function buildOutputName(names) {
  const stems = names
    .map((name) =>
      name
        .replace(UNSAFE_FILENAME_CHARS, '')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\.[^.]+$/, '')
        .slice(0, MAX_STEM_LENGTH)
        .trim()
    )
    .filter(Boolean);

  if (stems.length === 0) {
    return 'merged_document.tif';
  }

  const summary =
    stems.length <= 4
      ? stems.join('_')
      : `${stems.slice(0, 3).join('_')}_and_${stems.length - 3}_more`;

  return `${summary.slice(0, MAX_OUTPUT_STEM_LENGTH)}_merged.tif`;
}

function fileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
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

    setError('');
    setNotice('');

    setFiles((prev) => {
      const existing = new Set(prev.map(fileKey));
      return [...prev, ...tiffFiles.filter((f) => !existing.has(fileKey(f)))];
    });
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
      window.setTimeout(() => window.URL.revokeObjectURL(url), 0);

      setNotice(`Merged ${files.length} file${files.length === 1 ? '' : 's'}.`);
    } catch (mergeError) {
      setError(
        mergeError instanceof Error
          ? mergeError.message
          : 'Failed to merge files.'
      );
    } finally {
      setIsMerging(false);
    }
  };

  return (
    <main className="container">
      <div className="glass-panel">
        <h1>TIFF Merger</h1>
        <p className="subtitle">Combine multiple TIFF files effortlessly.</p>

        {error && (
          <p className="alert" role="alert">
            {error}
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
              {files.length} file{files.length === 1 ? '' : 's'} selected
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
          disabled={files.length === 0 || isMerging}
          aria-busy={isMerging}
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
