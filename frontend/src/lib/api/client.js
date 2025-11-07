// API client for backend communication

// Use the hostname from the browser, but change port to backend port
const API_BASE_URL = window.location.hostname === 'localhost'
  ? 'http://localhost:42069'
  : `http://${window.location.hostname}:42069`;

console.log('[API Client] Using API_BASE_URL:', API_BASE_URL);
console.log('[API Client] Browser location:', window.location.href);

/**
 * Generic fetch wrapper with error handling
 */
async function apiFetch(url, options = {}) {
  try {
    console.log('[API Client] Fetching:', `${API_BASE_URL}${url}`);
    const response = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('[API Client] Error response:', response.status, error);
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    console.log('[API Client] Success:', data);
    return data;
  } catch (error) {
    console.error('[API Client] Fetch failed:', error);
    throw error;
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
