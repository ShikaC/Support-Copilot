CREATE TABLE knowledge_releases (
    release_id VARCHAR(64) NOT NULL,
    release_version INT NOT NULL,
    corpus_checksum CHAR(64) NOT NULL,
    allowed_scopes_json VARCHAR(256) NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_by VARCHAR(128) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    approved_by VARCHAR(128),
    approved_at DATETIME(6),
    published_by VARCHAR(128),
    published_at DATETIME(6),
    version BIGINT NOT NULL,
    CONSTRAINT pk_knowledge_releases PRIMARY KEY (release_id),
    CONSTRAINT uk_knowledge_release_version UNIQUE (release_version)
);

CREATE TABLE knowledge_active_release (
    id VARCHAR(16) NOT NULL,
    singleton_key INT NOT NULL DEFAULT 1,
    release_id VARCHAR(64) NOT NULL,
    version BIGINT NOT NULL,
    CONSTRAINT pk_knowledge_active_release PRIMARY KEY (id),
    CONSTRAINT uk_knowledge_active_singleton UNIQUE (singleton_key),
    CONSTRAINT fk_knowledge_active_release FOREIGN KEY (release_id) REFERENCES knowledge_releases (release_id)
);
