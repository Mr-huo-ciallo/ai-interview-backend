CREATE DATABASE IF NOT EXISTS ai_interview
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'ai_interview_user'@'localhost'
  IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

GRANT ALL PRIVILEGES ON ai_interview.* TO 'ai_interview_user'@'localhost';

FLUSH PRIVILEGES;
