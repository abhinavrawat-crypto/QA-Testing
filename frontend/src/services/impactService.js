import api from './api'

export const indexingService = {
  indexRepo: (connectionId, repoId) =>
    api.post(`/indexing/repos/${connectionId}/${repoId}`),
  getStats: (repoId) =>
    api.get(`/indexing/repos/${repoId}/stats`),
}

export const impactService = {
  runAnalysis: (storyIds, repoIds) =>
    api.post('/analysis/impact', { story_ids: storyIds, repo_ids: repoIds }),
  getRun: (runId) =>
    api.get(`/analysis/impact/${runId}`),
  listRuns: () =>
    api.get('/analysis/impact'),
}
