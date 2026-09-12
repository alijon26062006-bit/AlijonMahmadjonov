ALTER TABLE IF EXISTS projects DROP CONSTRAINT IF EXISTS projects_assistant_session_fk;
DROP TABLE IF EXISTS assistant_sessions, project_invitations, project_attachments,
  project_features, project_specialisations, project_skills, projects;
DROP FUNCTION IF EXISTS projects_refresh_search_doc();
