const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function readDetail(payload, fallback) {
  if (!payload) return fallback;
  const { detail } = payload;
  if (typeof detail === "string") return detail;
  // FastAPI reports validation failures as a list of field errors. Surface the
  // first one in plain language rather than dumping the whole structure.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
    return field ? `${field}: ${first.msg}` : first.msg;
  }
  return fallback;
}

async function request(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Could not reach the server. Is the backend running?", 0);
  }

  if (response.status === 204) return null;

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      readDetail(payload, `Request failed with status ${response.status}`),
      response.status,
    );
  }
  return payload;
}

export const api = {
  register: (body) => request("/api/auth/register", { method: "POST", body }),
  login: (body) => request("/api/auth/login", { method: "POST", body }),
  me: (token) => request("/api/auth/me", { token }),

  limits: () => request("/api/limits"),
  programs: () => request("/api/programs"),
  program: (code) => request(`/api/programs/${encodeURIComponent(code)}`),

  courses: (token, { search, subject, includeSlots = true } = {}) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (subject) params.set("subject", subject);
    if (!includeSlots) params.set("include_slots", "false");
    const query = params.toString();
    return request(`/api/courses${query ? `?${query}` : ""}`, { token });
  },
  subjects: (token) => request("/api/courses/subjects", { token }),

  plans: (token) => request("/api/plans", { token }),
  plan: (token, planId) => request(`/api/plans/${planId}`, { token }),
  createPlan: (token, body) => request("/api/plans", { method: "POST", body, token }),
  renamePlan: (token, planId, name) =>
    request(`/api/plans/${planId}`, { method: "PATCH", body: { name }, token }),
  deletePlan: (token, planId) => request(`/api/plans/${planId}`, { method: "DELETE", token }),

  placeCourse: (token, planId, courseId, termIndex) =>
    request(`/api/plans/${planId}/courses`, {
      method: "POST",
      body: { course_id: courseId, term_index: termIndex },
      token,
    }),
  moveCourse: (token, planId, courseId, termIndex) =>
    request(`/api/plans/${planId}/courses/${courseId}`, {
      method: "PATCH",
      body: { term_index: termIndex },
      token,
    }),
  removeCourse: (token, planId, courseId) =>
    request(`/api/plans/${planId}/courses/${courseId}`, { method: "DELETE", token }),
  swapCourse: (token, planId, courseId, replacementCourseId) =>
    request(`/api/plans/${planId}/courses/${courseId}/swap`, {
      method: "POST",
      body: { replacement_course_id: replacementCourseId },
      token,
    }),
  autofill: (token, planId) => request(`/api/plans/${planId}/autofill`, { method: "POST", token }),

  // Undo and redo both come through here: one atomic request that sets the
  // plan to exactly the snapshot given, whatever the operation being reversed.
  replacePlacements: (token, planId, placements) =>
    request(`/api/plans/${planId}/placements`, { method: "PUT", body: { placements }, token }),

  eligible: (token, planId, { termIndex, subject, slotTag, excludeSlots } = {}) => {
    const params = new URLSearchParams({ term_index: String(termIndex) });
    if (subject) params.set("subject", subject);
    if (slotTag) params.set("slot_tag", slotTag);
    if (excludeSlots) params.set("exclude_slots", "true");
    return request(`/api/plans/${planId}/eligible?${params}`, { token });
  },

  switchTo: (token, planId, programCode) =>
    request(`/api/plans/${planId}/switch/${encodeURIComponent(programCode)}`, { token }),

  share: (token, planId) => request(`/api/plans/${planId}/share`, { method: "POST", token }),
  unshare: (token, planId) => request(`/api/plans/${planId}/share`, { method: "DELETE", token }),
  sharedPlan: (shareToken) => request(`/api/shared/${encodeURIComponent(shareToken)}`),

  exportCsvUrl: (planId) => `${BASE_URL}/api/plans/${planId}/export.csv`,
};

/**
 * Download the CSV export.
 *
 * The export endpoint needs the Authorization header, so it cannot be a plain
 * link. Fetching it as a blob and clicking a temporary object URL is the way to
 * get an authenticated response into the browser's downloads.
 */
export async function downloadCsv(token, planId, filename) {
  const response = await fetch(api.exportCsvUrl(planId), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new ApiError(`Export failed with status ${response.status}`, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoking immediately can cancel the download in some browsers.
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}
