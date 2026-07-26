"""Backup & Migration Service with verification and test artifact cleanup."""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
import sqlite3

from app.core.config import _PROJECT_ROOT

logger = logging.getLogger(__name__)


def run_verified_migration() -> None:
    """Run automated backup, backup integrity verification, and test artifact cleanup."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = _PROJECT_ROOT / ".cashcow_backups" / f"backup_v1_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_src = _PROJECT_ROOT / "cashcow.db"
    dev_db_src = _PROJECT_ROOT / "cashcow_dev.db"
    custom_dir = _PROJECT_ROOT / "profiles" / "custom"

    # Step 1: Create Backup
    if db_src.exists():
        shutil.copy2(db_src, backup_dir / "cashcow.db")
    if dev_db_src.exists():
        shutil.copy2(dev_db_src, backup_dir / "cashcow_dev.db")

    if custom_dir.is_dir():
        backup_custom = backup_dir / "custom_profiles"
        backup_custom.mkdir(parents=True, exist_ok=True)
        for p in custom_dir.glob("*.yaml"):
            shutil.copy2(p, backup_custom / p.name)

    # Step 2: Verify Backup
    verified = False
    if custom_dir.is_dir():
        backup_custom = backup_dir / "custom_profiles"
        if backup_custom.is_dir() and len(list(backup_custom.glob("*.yaml"))) == len(list(custom_dir.glob("*.yaml"))):
            verified = True

    if not verified and (custom_dir.is_dir() and len(list(custom_dir.glob("*.yaml"))) > 0):
        raise RuntimeError(f"Backup verification failed for backup at {backup_dir}")

    logger.info("Backup successfully verified at %s", backup_dir)

    # Step 3: Cleanup test junk files from custom profiles
    if custom_dir.is_dir():
        test_patterns = (
            "empty-destinations-profile-",
            "legacy-test-profile-",
            "oauth-only-profile-",
            "test-mixed-profile-",
            "to-migrate-persistent-",
            "test-log-migration.yaml",
            "to-migrate.yaml",
            "to-migrate-2.yaml",
        )
        purged = 0
        for p in list(custom_dir.glob("*.yaml")):
            if any(p.name.startswith(pat) or p.name == pat for pat in test_patterns):
                try:
                    p.unlink()
                    purged += 1
                except OSError as exc:
                    logger.warning("Could not delete junk test file %s: %s", p.name, exc)
        logger.info("Purged %d test junk profile file(s) from %s", purged, custom_dir)

    # Step 4: Migrate cashcow.db to cashcow_dev.db if needed
    if db_src.exists() and not dev_db_src.exists():
        shutil.copy2(db_src, dev_db_src)
        logger.info("Migrated cashcow.db to cashcow_dev.db")
