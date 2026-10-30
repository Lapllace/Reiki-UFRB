/** Caminhos oficiais da API FastAPI consumidos pelo frontend. */
export const endpoints = {
  auth: {
    me: "/auth/me",
    login: "/auth/login",
    logout: "/auth/logout",
  },
  locations: "/locations",
  sessions: {
    week: "/sessions",
  },
  enrollments: {
    create: "/enrollments",
    mine: "/me/enrollments",
    cancel: (id: string) => `/enrollments/${encodeURIComponent(id)}/cancel`,
  },
  notifications: {
    list: "/me/notifications",
    markRead: (id: string) => `/me/notifications/${encodeURIComponent(id)}/read`,
  },
  instructor: {
    availability: "/instructor/availability",
    sessions: "/instructor/sessions",
    roster: (sessionId: string) =>
      `/instructor/sessions/${encodeURIComponent(sessionId)}/roster`,
    cancelSession: (sessionId: string) =>
      `/instructor/sessions/${encodeURIComponent(sessionId)}/cancel`,
    coverInvites: "/instructor/cover-invites",
    acceptCover: (inviteId: string) =>
      `/instructor/cover-invites/${encodeURIComponent(inviteId)}/accept`,
  },
  coordination: {
    cycle: (weekStart: string) =>
      `/coordination/cycles/${encodeURIComponent(weekStart)}`,
    sessions: "/coordination/sessions",
    roster: (sessionId: string) =>
      `/coordination/sessions/${encodeURIComponent(sessionId)}/roster`,
    coverRequests: "/coordination/cover-requests",
    reallocations: "/coordination/reallocations",
    applyReallocation: (id: string) =>
      `/coordination/reallocations/${encodeURIComponent(id)}/apply`,
    dismissReallocation: (id: string) =>
      `/coordination/reallocations/${encodeURIComponent(id)}/dismiss`,
    events: "/coordination/events",
  },
} as const;
