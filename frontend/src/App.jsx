import AuthPage from "./components/auth/AuthPage";
import Dashboard from "./components/dashboard/Dashboard";
import { useRagDocsApp } from "./hooks/useRagDocsApp";

function App() {
  const app = useRagDocsApp();

  if (!app.token || !app.user) {
    return (
      <AuthPage
        authMode={app.authMode}
        busy={app.busy}
        error={app.error}
        form={app.form}
        notice={app.notice}
        onAuthModeChange={app.setAuthMode}
        onFormChange={(field, value) =>
          app.setForm((current) => ({ ...current, [field]: value }))
        }
        onSubmit={app.handleAuthSubmit}
      />
    );
  }

  return (
    <Dashboard
      busy={app.busy}
      clearingHistory={app.clearingHistory}
      documents={app.documents}
      error={app.error}
      history={app.history}
      notice={app.notice}
      question={app.question}
      selectedDocs={app.selectedDocs}
      uploading={app.uploading}
      user={app.user}
      onAsk={app.handleAsk}
      onClearHistory={app.handleClearHistory}
      onLogout={app.clearSession}
      onQuestionChange={app.setQuestion}
      onToggleDocument={app.toggleDocument}
      onUpload={app.handleUpload}
    />
  );
}

export default App;
