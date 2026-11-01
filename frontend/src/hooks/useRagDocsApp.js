import { useEffect, useRef, useState } from "react";
import api, { setAuthToken, streamChat } from "../api";
import {
  DEMO_ACCOUNT,
  emptyForm,
  emptyNotice,
  MODEL_KEY,
  REFRESH_KEY,
  TOKEN_KEY,
  USER_KEY,
} from "../constants/app";

export function useRagDocsApp() {
  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem(USER_KEY);
    return saved ? JSON.parse(saved) : null;
  });
  const [authMode, setAuthMode] = useState("login");
  const [form, setForm] = useState(emptyForm);
  const [documents, setDocuments] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [history, setHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(null);
  const abortRef = useRef(null);
  const [config, setConfig] = useState(null);
  const [model, setModelState] = useState(
    localStorage.getItem(MODEL_KEY) || "auto"
  );
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [deletingDocs, setDeletingDocs] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(emptyNotice);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }
    loadDashboard();
    loadConfig();
  }, [token]);

  useEffect(() => {
    if (!notice.message) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setNotice(emptyNotice);
    }, 2800);

    return () => window.clearTimeout(timer);
  }, [notice]);

  // Drop a stale selection if the server no longer offers that model.
  useEffect(() => {
    if (config && model !== "auto" && !config.models.some((m) => m.id === model)) {
      setModel("auto");
    }
  }, [config, model]);

  function setModel(nextModel) {
    setModelState(nextModel);
    localStorage.setItem(MODEL_KEY, nextModel);
  }

  async function loadConfig() {
    try {
      const response = await api.get("/config");
      setConfig(response.data);
    } catch {
      // Chat still works on the backend default without the model list.
      setConfig(null);
    }
  }

  async function loadDashboard() {
    try {
      const [docsRes, historyRes] = await Promise.all([
        api.get("/documents"),
        api.get("/chat/history"),
      ]);
      setDocuments(docsRes.data);
      // Drop selections for documents that no longer exist.
      setSelectedDocs((current) =>
        current.filter((id) => docsRes.data.some((doc) => doc.id === id))
      );
      setHistory(historyRes.data);
    } catch (err) {
      handleError(err, "Could not load your workspace.");
    }
  }

  function saveSession(nextToken, nextRefreshToken, nextUser) {
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(REFRESH_KEY, nextRefreshToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    setError("");
  }

  function clearSession() {
    abortRef.current?.abort();
    setToken("");
    setUser(null);
    setDocuments([]);
    setSelectedDocs([]);
    setHistory([]);
    setConfig(null);
    setError("");
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    setAuthToken("");
  }

  function handleError(err, fallbackMessage) {
    // 401 means expired and 422 means invalid, except on the login routes themselves,
    // where 401 means a wrong password. Parallel requests can all land here.
    const status = err?.response?.status;
    const isAuthRoute = err?.config?.url?.startsWith("/auth/");
    if ((status === 401 || status === 422) && !isAuthRoute) {
      clearSession();
      setError("Your session expired. Please log in again.");
      return;
    }

    const message = err?.response?.data?.error || fallbackMessage;
    setError(message);
  }

  function showNotice(message, type = "success") {
    setNotice({ message, type });
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const endpoint = authMode === "login" ? "/auth/login" : "/auth/register";
      const payload =
        authMode === "login"
          ? { email: form.email, password: form.password }
          : form;
      const response = await api.post(endpoint, payload);

      if (authMode === "register") {
        setAuthMode("login");
        setForm({
          ...emptyForm,
          email: response.data.user?.email || form.email,
        });
        showNotice(
          response.data.message || "Account created successfully. Please log in."
        );
      } else {
        saveSession(
          response.data.token,
          response.data.refresh_token,
          response.data.user
        );
        setForm(emptyForm);
      }
    } catch (err) {
      handleError(err, `Could not ${authMode}.`);
    } finally {
      setBusy(false);
    }
  }

  async function handleDemoLogin() {
    setBusy(true);
    setError("");
    setAuthMode("login");
    try {
      const response = await api.post("/auth/login", DEMO_ACCOUNT);
      saveSession(
        response.data.token,
        response.data.refresh_token,
        response.data.user
      );
      setForm(emptyForm);
    } catch (err) {
      handleError(err, "Could not log in to the demo account.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file) {
    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post("/documents/upload", formData);
      showNotice("PDF uploaded successfully.");
      await loadDashboard();
      return true;
    } catch (err) {
      handleError(err, "Could not upload this PDF.");
      return false;
    } finally {
      setUploading(false);
    }
  }

  async function handleClearHistory() {
    if (!history.length || clearingHistory) {
      return;
    }

    const confirmed = window.confirm(
      "Clear only the chat history? Uploaded PDFs will stay safe."
    );
    if (!confirmed) {
      return;
    }

    setClearingHistory(true);
    setError("");
    try {
      const response = await api.delete("/chat/history");
      setHistory([]);
      showNotice(response.data.message || "Chat history cleared successfully.");
    } catch (err) {
      handleError(err, "Could not clear chat history.");
    } finally {
      setClearingHistory(false);
    }
  }

  async function deleteDocuments(path, confirmMessage, successMessage, failureMessage) {
    if (deletingDocs || busy || !window.confirm(confirmMessage)) {
      return;
    }

    setDeletingDocs(true);
    setError("");
    try {
      await api.delete(path);
      showNotice(successMessage);
    } catch (err) {
      handleError(err, failureMessage);
    } finally {
      // Reload even after a failure, because a delete-all can stop partway.
      await loadDashboard();
      setDeletingDocs(false);
    }
  }

  function handleDeleteDocument(doc) {
    return deleteDocuments(
      `/documents/${doc.id}`,
      `Delete "${doc.name}"? This can't be undone. Your chat history will stay.`,
      "Document deleted.",
      "Could not delete this document."
    );
  }

  function handleDeleteAllDocuments() {
    return deleteDocuments(
      "/documents",
      `Delete all ${documents.length} documents? This can't be undone. Your chat history will stay.`,
      "All documents deleted.",
      "Could not delete all documents."
    );
  }

  function toggleDocument(id) {
    setSelectedDocs((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  }

  async function askQuestion(text) {
    const asked = text.trim();
    if (!asked || busy) {
      return;
    }

    setBusy(true);
    setError("");
    setQuestion("");

    const controller = new AbortController();
    abortRef.current = controller;
    const live = {
      question: asked,
      answer: "",
      sources: [],
      model: null,
      steps: [],
      created_at: new Date().toISOString(),
    };
    setStreaming({ ...live });

    const applyEvent = (event) => {
      if (event.type === "error") {
        throw new Error(event.error);
      }
      if (event.type === "step") {
        const known = live.steps.some((step) => step.id === event.id);
        live.steps = known
          ? live.steps.map((step) => (step.id === event.id ? event : step))
          : [...live.steps, event];
      } else if (event.type === "token") {
        live.answer += event.text;
      } else if (event.type === "sources") {
        live.sources = event.sources;
      } else if (event.type === "model") {
        live.model = event.model;
      } else if (event.type === "done") {
        live.id = event.message_id;
        live.total_ms = event.total_ms;
      }
      setStreaming({ ...live });
    };

    try {
      await streamChat(
        { question: asked, document_ids: selectedDocs, model },
        { signal: controller.signal, onEvent: applyEvent }
      );
      if (!live.id) {
        throw new Error("The connection closed before the answer finished.");
      }
      setHistory((current) => [...current, live]);
    } catch (err) {
      if (err.name === "AbortError" && live.answer) {
        // A stopped answer stays on screen, but the backend doesn't save it.
        setHistory((current) => [
          ...current,
          { ...live, id: `stopped-${Date.now()}`, stopped: true },
        ]);
      } else if (err.name !== "AbortError") {
        setQuestion(asked);
        // fetch throws a TypeError ("Failed to fetch") when the server can't be reached.
        handleError(
          err,
          err instanceof TypeError
            ? "Could not reach the server. Please try again."
            : err.message || "Could not get an answer right now."
        );
      } else {
        setQuestion(asked);
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      setStreaming(null);
    }
  }

  function stopGenerating() {
    abortRef.current?.abort();
  }

  return {
    authMode,
    busy,
    clearingHistory,
    config,
    deletingDocs,
    documents,
    error,
    form,
    history,
    model,
    notice,
    question,
    selectedDocs,
    streaming,
    token,
    uploading,
    user,
    askQuestion,
    clearSession,
    handleAuthSubmit,
    handleClearHistory,
    handleDeleteAllDocuments,
    handleDeleteDocument,
    handleDemoLogin,
    handleUpload,
    setAuthMode,
    setError,
    setForm,
    setModel,
    setQuestion,
    stopGenerating,
    toggleDocument,
  };
}
