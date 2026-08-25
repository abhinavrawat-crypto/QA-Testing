import api from './api'

export const discoveryService = {
  discoverUnmatched: (repoIds, similarityThreshold = 0.5) =>
    api.post('/discovery/unmatched', {
      repo_ids: repoIds,
      similarity_threshold: similarityThreshold,
    }),

  createJiraStory: (connectionId, projectKey, storyData, issueType = 'Story') =>
    api.post('/discovery/create-jira-story', {
      connection_id: connectionId,
      project_key: projectKey,
      summary: storyData.summary,
      description: storyData.description,
      acceptance_criteria: storyData.acceptance_criteria,
      issue_type: issueType,
    }),
}

export const codeGenService = {
  generateCode: (storyId, originalTestContent, scenarioDescription, targetFilePath, language = 'typescript', targetUrl = null) =>
    api.post('/code-gen/generate', {
      story_id: storyId,
      original_test_content: originalTestContent,
      scenario_description: scenarioDescription,
      target_file_path: targetFilePath,
      language,
      target_url: targetUrl,
    }),

  createPR: (connectionId, repoFullName, filePath, fileContent, jiraIssueKey, draft = false, customPRTitle = null) =>
    api.post('/code-gen/create-pr', {
      connection_id: connectionId,
      repo_full_name: repoFullName,
      file_path: filePath,
      file_content: fileContent,
      jira_issue_key: jiraIssueKey,
      draft,
      custom_pr_title: customPRTitle,
    }),
}
