import { useRef, useState } from "react";

function UploadZone({ disabled, onFileSelected }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  function openPicker() {
    if (!disabled) {
      inputRef.current?.click();
    }
  }

  function handleInputChange(event) {
    const file = event.target.files?.[0] || null;
    onFileSelected(file);
    event.target.value = "";
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    if (disabled) {
      return;
    }
    const file = event.dataTransfer.files?.[0] || null;
    onFileSelected(file);
  }

  return (
    <section
      className={`upload-zone ${isDragging ? "dragging" : ""} ${
        disabled ? "disabled" : ""
      }`}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragging(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragging(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setIsDragging(false);
      }}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        id="docx-upload"
        className="sr-only"
        type="file"
        aria-label="DOCX file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleInputChange}
        disabled={disabled}
      />
      <div className="upload-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M12 3a1 1 0 0 1 .7.29l4 4a1 1 0 0 1-1.4 1.42L13 6.41V15a1 1 0 1 1-2 0V6.41L8.7 8.71a1 1 0 0 1-1.4-1.42l4-4A1 1 0 0 1 12 3Z" />
          <path d="M5 14a1 1 0 0 1 1 1v3h12v-3a1 1 0 1 1 2 0v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1Z" />
        </svg>
      </div>
      <div>
        <h2>Upload DOCX</h2>
        <p>Drag and drop one DOCX file here, or browse from your computer.</p>
      </div>
      <button
        className="secondary-button"
        type="button"
        onClick={openPicker}
        disabled={disabled}
      >
        Browse File
      </button>
    </section>
  );
}

export default UploadZone;
