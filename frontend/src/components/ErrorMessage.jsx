function ErrorMessage({ message, title = "Action needed" }) {
  if (!message) {
    return null;
  }

  return (
    <section className="message error-message" role="alert">
      <strong>{title}</strong>
      <span>{message}</span>
    </section>
  );
}

export default ErrorMessage;
