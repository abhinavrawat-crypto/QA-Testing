import api from './api'

export const runnerService = {
  executeTest: (scriptCode, targetUrl = null, envVars = null, headed = false, timeoutSeconds = 60) =>
    api.post('/runner/execute', {
      script_code: scriptCode,
      target_url: targetUrl,
      env_vars: envVars,
      headed: headed,
      timeout_seconds: timeoutSeconds,
    }),

  getRunDetails: (runId) =>
    api.get(`/runner/runs/${runId}`),
}
