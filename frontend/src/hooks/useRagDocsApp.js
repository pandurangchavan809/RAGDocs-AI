import { useEffect, useState } from "react";
import api, { setAuthToken } from "../api";
import { emptyForm, emptyNotice, TOKEN_KEY, USER_KEY } from "../constants/app";

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
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
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

  async function loadDashboard() {
    try {
      const [docsRes, historyRes] = await Promise.all([
        api.get("/documents"),
        api.get("/chat/history"),
      ]);
      setDocuments(docsRes.data);
      setHistory(historyRes.data);
    } catch (err) {
      handleError(err, "Could not load your workspace.");
    }
  }

  function saveSession(nextToken, nextUser) {
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    setError("");
  }

  function clearSession() {
    setToken("");
    setUser(null);
    setDocuments([]);
    setSelectedDocs([]);
    setHistory([]);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setAuthToken("");
  }

  function handleError(err, fallbackMessage) {
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
        saveSession(response.data.token, response.data.user);
        setForm(emptyForm);
      }
    } catch (err) {
      handleError(err, `Could not ${authMode}.`);
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post("/documents/upload", formData);
      event.target.value = "";
      showNotice("PDF uploaded successfully.");
      await loadDashboard();
    } catch (err) {
      handleError(err, "Could not upload this PDF.");
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

  function toggleDocument(id) {
    setSelectedDocs((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  }

  async function handleAsk(event) {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }

    const pendingQuestion = question.trim();
    setBusy(true);
    setError("");
    setQuestion("");

    try {
      const response = await api.post("/chat", {
        question: pendingQuestion,
        document_ids: selectedDocs,
      });

      setHistory((current) => [
        ...current,
        {
          id: response.data.message_id,
          question: pendingQuestion,
          answer: response.data.answer,
          sources: response.data.sources,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setQuestion(pendingQuestion);
      handleError(err, "Could not get an answer right now.");
    } finally {
      setBusy(false);
    }
  }

  return {
    authMode,
    busy,
    clearingHistory,
    documents,
    error,
    form,
    history,
    notice,
    question,
    selectedDocs,
    token,
    uploading,
    user,
    clearSession,
    handleAsk,
    handleAuthSubmit,
    handleClearHistory,
    handleUpload,
    setAuthMode,
    setForm,
    setQuestion,
    toggleDocument,
  };
}
