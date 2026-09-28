const apiBaseUrl = import.meta.env.VITE_BACKEND_API_URL || '/api';

export async function fetchHealth() {
  const response = await fetch(`${apiBaseUrl}/health`);

  if (!response.ok) {
    throw new Error(`A API respondeu com status ${response.status}.`);
  }

  return response.json();
}
