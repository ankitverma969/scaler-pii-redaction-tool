import { formatFileSize } from "../utils/file";

function SelectedFile({ file, disabled, onRemove }) {
  if (!file) {
    return null;
  }

  return (
    <section className="selected-file" aria-label="Selected document">
      <div className="file-badge" aria-hidden="true">
        DOCX
      </div>
      <div className="file-details">
        <p className="file-name" title={file.name}>
          {file.name}
        </p>
        <p>{formatFileSize(file.size)} · DOCX Document</p>
      </div>
      <button
        className="text-button"
        type="button"
        onClick={onRemove}
        disabled={disabled}
      >
        Remove
      </button>
    </section>
  );
}

export default SelectedFile;
