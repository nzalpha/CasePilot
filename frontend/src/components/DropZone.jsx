import React, { useRef, useState } from "react";

function isPdf(file) {
  return file && file.name.toLowerCase().endsWith(".pdf");
}

export default function DropZone({
  selectedFile,
  validationMessage,
  onFileAccepted,
  onFileRejected
}) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  function acceptFile(file) {
    if (!file) {
      return;
    }

    if (!isPdf(file)) {
      onFileRejected("Only PDF files are accepted.");
      return;
    }

    onFileAccepted(file);
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    acceptFile(event.dataTransfer.files[0]);
  }

  function handleBrowse(event) {
    acceptFile(event.target.files[0]);
    event.target.value = "";
  }

  return (
    <div className="field">
      <span>PDF file</span>
      <button
        type="button"
        className={isDragging ? "drop-zone dragging" : "drop-zone"}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <span className="drop-zone-title">
          {selectedFile ? selectedFile.name : "Drop a PDF here or browse"}
        </span>
        <span className="drop-zone-meta">.pdf only</span>
      </button>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleBrowse}
      />
      {validationMessage && <p className="notice error">{validationMessage}</p>}
    </div>
  );
}
