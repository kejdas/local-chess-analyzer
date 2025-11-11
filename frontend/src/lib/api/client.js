// API client for backend communication

// Prefer relative API calls so the frontend (Nginx) can proxy /api → backend.
// Allow overriding via Vite env for local dev if needed.
const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) || '';

console.log('[API Client] Using API_BASE_URL:', API_BASE_URL);
console.log('[API Client] Browser location:', window.location.href);

/**
 * Generic fetch wrapper with error handling
 */
async function apiFetch(url, options = {}) {
  try {
    const fullUrl = `${API_BASE_URL}${url}`;
    console.log('[API Client] Fetching:', fullUrl);
    const response = await fetch(fullUrl, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const status = response.status;
      const contentType = response.headers.get('content-type') || '';
      let serverMessage = null;
      try {
        if (contentType.includes('application/json')) {
          const json = await response.json();
          serverMessage = json?.detail || json?.message || null;
        } else {
          const text = await response.text();
          // If body looks like HTML, don't surface raw HTML to users
          const looksLikeHtml = /<\s*html[\s>]/i.test(text) || /<\s*body[\s>]/i.test(text) || /<[^>]+>/.test(text);
          serverMessage = looksLikeHtml ? null : (text || null);
        }
      } catch {
        // ignore parsing errors
      }

      let friendly = '';
      if (status === 504) {
        friendly = 'Request timed out (504). The server may be busy or starting. Please try again shortly.';
      } else if (status === 409) {
        friendly = serverMessage || 'A sync is already in progress. Please check status or try again soon.';
      } else if (status >= 500) {
        friendly = serverMessage ? `Server error (${status}): ${serverMessage}` : 'Server error. Please try again.';
      } else if (status === 404) {
        friendly = serverMessage || 'Not found.';
      } else if (status === 400) {
        friendly = serverMessage || 'Bad request. Please review your input.';
      } else if (status === 401 || status === 403) {
        friendly = serverMessage || 'Not authorized.';
      } else {
        friendly = serverMessage ? serverMessage : `Request failed with status ${status}.`;
      }

      console.error('[API Client] Error response:', status, serverMessage || '(no message)');
      throw new Error(friendly);
    }

    const data = await response.json();
    console.log('[API Client] Success:', data);
    return data;
  } catch (error) {
    // Normalize network errors
    if (error?.name === 'TypeError' || /NetworkError/i.test(String(error))) {
      const message = 'Network error. Please check your connection and that the backend is reachable.';
      console.error('[API Client] Fetch failed (network):', error);
      throw new Error(message);
    }
    console.error('[API Client] Fetch failed:', error);
    throw error; // already friendly
  }
}

// Settings API
export async function getSettings() {
  return apiFetch('/api/settings');
}

export async function updateSettings(settings) {
  return apiFetch('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

// System Resources API
export async function getSystemResources() {
  return apiFetch('/api/system-resources');
}

// Sync API
export async function startSync(username = null, limitMonths = null) {
  const body = {};
  if (username) body.username = username;
  if (limitMonths) body.limit_months = limitMonths;

  return apiFetch('/api/sync', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getSyncStatus() {
  return apiFetch('/api/sync/status');
}

// Games API
export async function getGames(skip = 0, limit = 100, filters = {}, sort = {}) {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString()
  });

  // Add optional filters
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  if (filters.status) params.append('status', filters.status);
  if (filters.time_class) params.append('time_class', filters.time_class);

  // Add sorting
  if (sort.sort_by) params.append('sort_by', sort.sort_by);
  if (sort.sort_order) params.append('sort_order', sort.sort_order);

  return apiFetch(`/api/games?${params.toString()}`);
}

export async function getGame(gameId) {
  return apiFetch(`/api/games/${gameId}`);
}

export async function getGamesStats() {
  return apiFetch('/api/games/stats');
}

// Database Management API
export async function clearDatabase() {
  return apiFetch('/api/database/clear', {
    method: 'DELETE',
  });
}

export async function downloadDatabase() {
  try {
    const url = `${API_BASE_URL}/api/database/download`;
    console.log('[API Client] Downloading database from:', url);

    // Create a temporary link and trigger download
    const link = document.createElement('a');
    link.href = url;
    link.download = 'games.db';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    return { success: true };
  } catch (error) {
    console.error('[API Client] Download failed:', error);
    throw error;
  }
}

export async function uploadDatabase(file) {
  try {
    console.log('[API Client] Uploading database file:', file.name);

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/database/upload`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header - browser will set it with boundary for multipart/form-data
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('[API Client] Upload error:', response.status, error);
      throw new Error(`Upload failed: ${response.status} - ${error}`);
    }

    const data = await response.json();
    console.log('[API Client] Upload success:', data);
    return data;
  } catch (error) {
    console.error('[API Client] Upload failed:', error);
    throw error;
  }
}

// Game Analysis API
export async function analyzeGame(gameId) {
  return apiFetch(`/api/games/${gameId}/analyze`, {
    method: 'POST',
  });
}

export async function getGameAnalysis(gameId) {
  return apiFetch(`/api/games/${gameId}/analysis`);
}

export async function bulkAnalyzeGames(gameIds, concurrency = 3, skipAlreadyAnalyzed = true) {
  return apiFetch('/api/games/bulk-analyze', {
    method: 'POST',
    body: JSON.stringify({
      game_ids: gameIds,
      concurrency,
      skip_already_analyzed: skipAlreadyAnalyzed,
    }),
  });
}
