CREATE DATABASE IF NOT EXISTS lost_found_portal
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lost_found_portal;

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(160) NOT NULL,
  description TEXT NOT NULL,
  item_type ENUM('lost', 'found') NOT NULL,
  location VARCHAR(160) NOT NULL,
  status ENUM('open', 'recovered') NOT NULL DEFAULT 'open',
  image_object_name VARCHAR(512),
  image_url VARCHAR(2048),
  owner_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_items_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX ix_items_status_type (status, item_type),
  INDEX ix_items_location (location),
  INDEX ix_items_created_at (created_at)
) ENGINE=InnoDB;
