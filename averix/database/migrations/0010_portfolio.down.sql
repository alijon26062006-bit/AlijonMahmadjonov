ALTER TABLE IF EXISTS proposal_portfolio_links DROP CONSTRAINT IF EXISTS proposal_portfolio_history_fk;
ALTER TABLE IF EXISTS proposal_portfolio_links DROP CONSTRAINT IF EXISTS proposal_portfolio_project_fk;
DROP TABLE IF EXISTS completed_project_skills, completed_project_history,
  portfolio_links, portfolio_skills, portfolio_images, portfolio_projects;
DROP FUNCTION IF EXISTS portfolio_refresh_search_doc();
