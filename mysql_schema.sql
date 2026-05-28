-- RAGDocs AI MySQL schema
-- Import this into your MySQL or Aiven database before running the app.
-- This version targets the Aiven database shown in your screenshot: `defaultdb`.
-- If your Aiven database name changes again, update the USE line below.

USE defaultdb;

CREATE TABLE IF NOT EXISTS users (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,
  email VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  stored_name VARCHAR(255) NOT NULL,
  chunk_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_documents_user_id (user_id),
  CONSTRAINT fk_documents_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  question LONGTEXT NOT NULL,
  answer LONGTEXT NOT NULL,
  document_ids JSON NOT NULL,
  sources JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_chat_messages_user_id (user_id),
  CONSTRAINT fk_chat_messages_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
