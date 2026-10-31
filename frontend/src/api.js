import axios from "axios";

import { REFRESH_KEY, TOKEN_KEY } from "./constants/app";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:5000/api",
});

let refreshInFlight = null;

// Requests that fail together share one refresh, so renewal costs a single call.
function refreshAccessToken() {
  refreshInFlight ??= axios
    .post(`${api.defaults.baseURL}/auth/refresh`, null, {
      headers: { Authorization: `Bearer ${localStorage.getItem(REFRESH_KEY)}` },
    })
    .then((response) => {
      // Skip saving if the user logged out while this was running.
      if (localStorage.getItem(REFRESH_KEY)) {
        localStorage.setItem(TOKEN_KEY, response.data.token);
        setAuthToken(response.data.token);
      }
      return response.data.token;
    })
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

api.interceptors.response.use(undefined, async (error) => {
  const { config, response } = error;
  const canRenew =
    response?.status === 401 &&
    config &&
    !config.renewed &&
    !config.url?.startsWith("/auth/") &&
    localStorage.getItem(REFRESH_KEY);
  if (!canRenew) {
    throw error;
  }

  let token;
  try {
    token = await refreshAccessToken();
  } catch {
    // Report the original 401, which sends the user back to the login page.
    throw error;
  }
  config.renewed = true;
  config.headers.Authorization = `Bearer ${token}`;
  return api(config);
});

export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

// Axios can't read a response body as it arrives in the browser, so this uses fetch.
export async function streamChat(body, { signal, onEvent }) {
  const send = () =>
    fetch(`${api.defaults.baseURL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: api.defaults.headers.common.Authorization,
      },
      body: JSON.stringify(body),
      signal,
    });

  let response = await send();
  if (response.status === 401 && localStorage.getItem(REFRESH_KEY)) {
    // If renewal fails, the original 401 below sends the user to the login page.
    const renewed = await refreshAccessToken().catch(() => null);
    if (renewed) {
      response = await send();
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(data.msg || "Could not get an answer right now.");
    error.response = { status: response.status, data };
    throw error;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      return;
    }
    buffer += value;
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      if (part.startsWith("data: ")) {
        onEvent(JSON.parse(part.slice(6)));
      }
    }
  }
}

export default api;
