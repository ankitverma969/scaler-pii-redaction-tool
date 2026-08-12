function Header() {
  return (
    <header className="app-header">
      <div>
        <p className="eyebrow">Scaler AI Labs Assignment</p>
        <h1>PII Redaction Tool</h1>
      </div>
      <p className="header-copy">
        Detect and replace personally identifiable information in DOCX documents
        with synthetic alternatives while preserving document structure.
      </p>
    </header>
  );
}

export default Header;
