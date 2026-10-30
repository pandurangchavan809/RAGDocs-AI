import { useState } from "react";

import AuthPage from "./components/auth/AuthPage";
import ChatView from "./components/chat/ChatView";
import NoticeBanner from "./components/shared/NoticeBanner";
import Sidebar from "./components/sidebar/Sidebar";
import UploadDialog from "./components/sidebar/UploadDialog";
import { useRagDocsApp } from "./hooks/useRagDocsApp";

function App() {
  const app = useRagDocsApp();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

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

  const openUpload = () => {
    app.setError("");
    setSidebarOpen(false);
    setUploadOpen(true);
  };

  const closeUpload = () => {
    app.setError("");
    setUploadOpen(false);
  };

  return (
    <div className="flex h-full overflow-hidden">
      <NoticeBanner notice={app.notice} />
      <Sidebar
        app={app}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onOpenUpload={openUpload}
      />
      <ChatView
        app={app}
        onOpenSidebar={() => setSidebarOpen(true)}
        onOpenUpload={openUpload}
      />
      <UploadDialog
        error={app.error}
        open={uploadOpen}
        uploading={app.uploading}
        onClose={closeUpload}
        onUpload={app.handleUpload}
      />
    </div>
  );
}

export default App;
