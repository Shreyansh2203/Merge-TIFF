'use client';

import { useState, useRef } from 'react';

export default function Home() {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const fileInputRef = useRef(null);

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
  };

  const addFiles = (newFiles) => {
    const tiffFiles = newFiles.filter(
      file => file.name.toLowerCase().endsWith('.tif') || file.name.toLowerCase().endsWith('.tiff')
    );
    
    setFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name));
      const uniqueNewFiles = tiffFiles.filter(f => !existingNames.has(f.name));
      return [...prev, ...uniqueNewFiles];
    });
  };

  const removeFile = (indexToRemove) => {
    setFiles(files.filter((_, index) => index !== indexToRemove));
  };

  const handleMerge = async () => {
    if (files.length === 0) return;
    
    setIsMerging(true);
    
    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch('/api/merge', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to merge files');
      }

      // Create a download link for the blob
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      // Create a dynamic filename from the files
      let outName = 'merged_document.tif';
      if (files.length > 0) {
        const basenames = files.map(f => f.name.replace(/\.[^/.]+$/, ""));
        if (basenames.length <= 4) {
          outName = basenames.join('_') + '_merged.tif';
        } else {
          outName = basenames.slice(0, 3).join('_') + `_and_${basenames.length - 3}_more_merged.tif`;
        }
      }
      
      a.download = outName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setIsMerging(false);
    }
  };

  return (
    <main className="container">
      <div className="glass-panel">
        <h1>TIFF Merger</h1>
        <p className="subtitle">Combine multiple TIFF files effortlessly.</p>
        
        <div 
          className={`dropzone ${isDragging ? 'active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
        >
          <div className="dropzone-icon">📄</div>
          <div className="dropzone-text">
            Drag & drop TIFF files here,<br/>or click to select
          </div>
          <input 
            type="file" 
            multiple 
            accept=".tif,.tiff" 
            ref={fileInputRef}
            onChange={handleFileSelect}
            style={{ display: 'none' }} 
          />
        </div>

        {files.length > 0 && (
          <div className="file-list">
            {files.map((file, index) => (
              <div key={`${file.name}-${index}`} className="file-item">
                <span>{file.name}</span>
                <button onClick={() => removeFile(index)} title="Remove file">&times;</button>
              </div>
            ))}
          </div>
        )}

        <button 
          className="btn-primary" 
          onClick={handleMerge} 
          disabled={files.length === 0 || isMerging}
        >
          {isMerging ? (
            <><span className="spinner"></span> Merging...</>
          ) : (
            'Merge TIFFs'
          )}
        </button>
      </div>
    </main>
  );
}
