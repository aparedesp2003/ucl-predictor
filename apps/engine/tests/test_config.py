from engine.config import REPO_ROOT, Settings


def test_repo_root_points_at_monorepo_root():
    assert (REPO_ROOT / "pnpm-workspace.yaml").is_file()


def test_sqlalchemy_url_uses_psycopg_driver():
    settings = Settings(_env_file=None, database_url="postgresql://u:p@host:5432/db")
    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"


def test_sqlalchemy_url_accepts_postgres_scheme():
    settings = Settings(_env_file=None, database_url="postgres://u:p@host:5432/db")
    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"
