import api from './api'

export const analysisService = {
  /** Score one or more stories */
  scoreStories: (storyIds, connectionId) =>
    api.post('/analysis/score', { story_ids: storyIds, connection_id: connectionId }),

  /** Get score history for a story */
  getScoreHistory: (storyId) =>
    api.get(`/analysis/score/story/${storyId}`),

  /** Approve a score result and write back to JIRA */
  approveScore: (scoreId, connectionId, edits = {}) =>
    api.post(`/analysis/score/${scoreId}/approve`, {
      connection_id: connectionId,
      edited_summary: edits.summary || null,
      edited_description: edits.description || null,
      edited_ac: edits.ac || null,
    }),

  /** Reject a score result */
  rejectScore: (scoreId) =>
    api.post(`/analysis/score/${scoreId}/reject`),
}
