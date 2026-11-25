"""
retrain.py — CLI and scheduling entry points for model retraining.

Provides:
- Manual retraining command
- Scheduled retraining runner (for cron/systemd)
- Configuration management
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from typing import Any

from edup.logging import configure_logging, logger_models
from edup.models import get_registry
from edup.models.registry import PromotionCriteria

# Global flag for graceful shutdown
_shutdown_requested = False


def _signal_handler(signum: int, frame: Any) -> None:
    global _shutdown_requested
    logger_models.info("Received signal %d, initiating graceful shutdown", signum)
    _shutdown_requested = True


def run_manual_retrain(
    auto_promote: bool = False,
    min_r2: float = -1.0,
    max_rmse: float = float("inf"),
    max_mae: float = float("inf"),
    must_beat_baseline: bool = True,
) -> dict[str, Any]:
    """Run a manual retraining job."""
    configure_logging()
    logger_models.info("Starting manual retraining (auto_promote=%s)", auto_promote)

    registry = get_registry()

    criteria = PromotionCriteria(
        min_r2=min_r2,
        max_rmse=max_rmse,
        max_mae=max_mae,
        must_beat_baseline=must_beat_baseline,
    )

    result = registry.run_retraining(
        acceptance_criteria=criteria,
        auto_promote=auto_promote,
    )

    job_id = f"manual_{int(time.time())}"
    registry.log_retraining_job(job_id, result["status"], result)

    logger_models.info("Manual retraining completed: %s", result["status"])
    return result


def run_scheduled_retrain() -> dict[str, Any]:
    """Run a scheduled retraining job using configured criteria."""
    configure_logging()
    logger_models.info("Starting scheduled retraining")

    registry = get_registry()
    config = registry.get_retraining_config()

    if not config.enabled:
        logger_models.info("Scheduled retraining is disabled; skipping")
        return {"status": "disabled", "message": "Scheduled retraining is disabled"}

    # Check for overlapping jobs (simple file-based lock)
    log_dir = config.resolve_log_dir(registry.registry_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    lock_file = log_dir / ".retraining.lock"
    if lock_file.exists():
        # Check if lock is stale (older than 6 hours)
        try:
            lock_age = time.time() - lock_file.stat().st_mtime
            if lock_age < 6 * 3600:
                logger_models.warning("Another retraining job appears to be running; skipping")
                return {"status": "skipped", "message": "Overlapping job detected"}
            else:
                logger_models.warning("Stale lock file found; removing and proceeding")
                lock_file.unlink()
        except OSError:
            pass

    # Create lock
    lock_file.write_text(str(os.getpid()))

    try:
        result = registry.run_retraining(
            acceptance_criteria=config.acceptance_criteria,
            auto_promote=False,  # Scheduled runs never auto-promote
        )

        job_id = f"scheduled_{int(time.time())}"
        registry.log_retraining_job(job_id, result["status"], result)

        logger_models.info("Scheduled retraining completed: %s", result["status"])
        return result

    finally:
        # Release lock
        try:
            lock_file.unlink()
        except OSError:
            pass


def daemon_mode(interval_seconds: int = 3600) -> None:
    """Run in daemon mode, checking for scheduled retraining at intervals."""
    configure_logging()
    logger_models.info("Starting retraining daemon (interval=%ds)", interval_seconds)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    registry = get_registry()

    while not _shutdown_requested:
        try:
            config = registry.get_retraining_config()
            if config.enabled:
                # Simple cron-like check: run if it's been more than 24 hours since last run
                logs = registry.get_retraining_logs(limit=1)
                last_run = None
                if logs:
                    try:
                        last_run = time.mktime(
                            time.strptime(logs[0]["timestamp_utc"][:19], "%Y-%m-%dT%H:%M:%S")
                        )
                    except Exception:
                        pass

                now = time.time()
                should_run = last_run is None or (now - last_run) >= 24 * 3600

                if should_run:
                    logger_models.info("Scheduled retraining triggered by daemon")
                    run_scheduled_retrain()

        except Exception:
            logger_models.exception("Error in retraining daemon loop")

        # Sleep in small increments to allow quick shutdown
        for _ in range(interval_seconds):
            if _shutdown_requested:
                break
            time.sleep(1)

    logger_models.info("Retraining daemon stopped")


def show_registry_status() -> None:
    """Display current registry status."""
    configure_logging()
    registry = get_registry()

    active = registry.get_active_version()
    versions = registry.list_versions()
    config = registry.get_retraining_config()

    print("=== EduPro Model Registry Status ===")
    print(f"Registry directory: {registry.registry_dir}")
    print(f"Active version: {active.version if active else 'None'}")
    if active:
        print(f"  Model: {active.model_name} ({active.model_type})")
        print(f"  Artifact: {active.artifact_filename}")
        print(f"  Training date: {active.training_date_utc}")
        print(f"  Promoted at: {active.promoted_at_utc}")
        print(f"  Promoted by: {active.promoted_by}")
        print(f"  Status: {active.status}")
    print(f"\nTotal versions: {len(versions)}")
    print("\nAll versions (newest first):")
    for v in versions:
        marker = " -> ACTIVE" if active and v.version == active.version else ""
        print(f"  {v.version}: {v.model_name} [{v.status}]{marker}")
        print(f"    Trained: {v.training_date_utc}")
        if v.metrics.get("selected_test"):
            test = v.metrics["selected_test"]
            print(f"    Test RMSE: {test.get('RMSE', 'N/A'):.3f}, MAE: {test.get('MAE', 'N/A'):.3f}, R2: {test.get('R2', 'N/A'):.3f}")

    print("\n=== Retraining Configuration ===")
    print(f"Enabled: {config.enabled}")
    print(f"Schedule: {config.schedule_cron}")
    print(f"Max concurrent jobs: {config.max_concurrent_jobs}")
    print(f"Acceptance criteria: {config.acceptance_criteria.to_dict()}")


def promote_version(version: str, min_r2: float = -1.0, max_rmse: float = float("inf"), max_mae: float = float("inf")) -> bool:
    """Promote a specific version to active (requires approved status)."""
    configure_logging()
    registry = get_registry()

    criteria = PromotionCriteria(
        min_r2=min_r2,
        max_rmse=max_rmse,
        max_mae=max_mae,
        must_beat_baseline=True,
    )

    try:
        registry.promote(version, criteria, promoted_by="cli")
        logger_models.info("Successfully promoted version %s", version)
        return True
    except Exception as exc:
        logger_models.error("Promotion failed: %s", exc)
        return False


def approve_version(version: str, min_r2: float = -1.0, max_rmse: float = float("inf"), max_mae: float = float("inf")) -> bool:
    """Approve a candidate version for promotion."""
    configure_logging()
    registry = get_registry()

    criteria = PromotionCriteria(
        min_r2=min_r2,
        max_rmse=max_rmse,
        max_mae=max_mae,
        must_beat_baseline=True,
    )

    try:
        registry.approve_candidate(version, criteria, approved_by="cli")
        logger_models.info("Successfully approved version %s", version)
        return True
    except Exception as exc:
        logger_models.error("Approval failed: %s", exc)
        return False


def reject_version(version: str, reason: str = "") -> bool:
    """Reject a candidate version."""
    configure_logging()
    registry = get_registry()

    try:
        registry.reject_candidate(version, reason=reason, rejected_by="cli")
        logger_models.info("Successfully rejected version %s", version)
        return True
    except Exception as exc:
        logger_models.error("Rejection failed: %s", exc)
        return False


def archive_version(version: str) -> bool:
    """Archive a model version."""
    configure_logging()
    registry = get_registry()

    try:
        registry.archive_version(version, archived_by="cli")
        logger_models.info("Successfully archived version %s", version)
        return True
    except Exception as exc:
        logger_models.error("Archival failed: %s", exc)
        return False


def rollback_version(version: str | None = None) -> bool:
    """Rollback to a previous version."""
    configure_logging()
    registry = get_registry()

    try:
        registry.rollback(version)
        logger_models.info("Successfully rolled back%s", f" to {version}" if version else "")
        return True
    except Exception as exc:
        logger_models.error("Rollback failed: %s", exc)
        return False


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="EduPro Model Retraining and Registry Management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Manual retrain
    retrain_parser = subparsers.add_parser("retrain", help="Run manual model retraining")
    retrain_parser.add_argument("--auto-promote", action="store_true", help="Automatically promote if validation passes")
    retrain_parser.add_argument("--min-r2", type=float, default=-1.0, help="Minimum R2 for promotion")
    retrain_parser.add_argument("--max-rmse", type=float, default=float("inf"), help="Maximum RMSE for promotion")
    retrain_parser.add_argument("--max-mae", type=float, default=float("inf"), help="Maximum MAE for promotion")
    retrain_parser.add_argument("--no-beat-baseline", action="store_true", help="Don't require beating baseline")

    # Scheduled retrain (for cron)
    subparsers.add_parser("scheduled", help="Run scheduled retraining (for cron/systemd)")

    # Daemon mode
    daemon_parser = subparsers.add_parser("daemon", help="Run retraining daemon")
    daemon_parser.add_argument("--interval", type=int, default=3600, help="Check interval in seconds")

    # Status
    subparsers.add_parser("status", help="Show registry status")

    # Promote
    promote_parser = subparsers.add_parser("promote", help="Promote a version to active")
    promote_parser.add_argument("version", help="Version to promote")
    promote_parser.add_argument("--min-r2", type=float, default=-1.0)
    promote_parser.add_argument("--max-rmse", type=float, default=float("inf"))
    promote_parser.add_argument("--max-mae", type=float, default=float("inf"))

    # Rollback
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to previous version")
    rollback_parser.add_argument("version", nargs="?", help="Specific version to rollback to (default: most recent legacy)")

    # Config
    config_parser = subparsers.add_parser("config", help="Manage retraining configuration")
    config_parser.add_argument("--enable", action="store_true", help="Enable scheduled retraining")
    config_parser.add_argument("--disable", action="store_true", help="Disable scheduled retraining")
    config_parser.add_argument("--schedule", help="Cron schedule (e.g., '0 2 * * 0')")
    config_parser.add_argument("--min-r2", type=float)
    config_parser.add_argument("--max-rmse", type=float)
    config_parser.add_argument("--max-mae", type=float)

    # Approve
    approve_parser = subparsers.add_parser("approve", help="Approve a candidate version for promotion")
    approve_parser.add_argument("version", help="Version to approve")
    approve_parser.add_argument("--min-r2", type=float, default=-1.0)
    approve_parser.add_argument("--max-rmse", type=float, default=float("inf"))
    approve_parser.add_argument("--max-mae", type=float, default=float("inf"))

    # Reject
    reject_parser = subparsers.add_parser("reject", help="Reject a candidate version")
    reject_parser.add_argument("version", help="Version to reject")
    reject_parser.add_argument("--reason", default="", help="Reason for rejection")

    # Archive
    archive_parser = subparsers.add_parser("archive", help="Archive a model version")
    archive_parser.add_argument("version", help="Version to archive")

    args = parser.parse_args()

    if args.command == "retrain":
        result = run_manual_retrain(
            auto_promote=args.auto_promote,
            min_r2=args.min_r2,
            max_rmse=args.max_rmse,
            max_mae=args.max_mae,
            must_beat_baseline=not args.no_beat_baseline,
        )
        print(f"Status: {result['status']}")
        if result.get("candidate_version"):
            print(f"Candidate version: {result['candidate_version']}")
        if result.get("validation_issues"):
            print(f"Validation issues: {result['validation_issues']}")
        if result.get("error"):
            print(f"Error: {result['error']}")
        return 0 if result["status"] in ("candidate_ready", "promoted") else 1

    elif args.command == "scheduled":
        result = run_scheduled_retrain()
        print(f"Status: {result['status']}")
        if result.get("candidate_version"):
            print(f"Candidate version: {result['candidate_version']}")
        if result.get("validation_issues"):
            print(f"Validation issues: {result['validation_issues']}")
        return 0 if result["status"] in ("candidate_ready", "disabled") else 1

    elif args.command == "daemon":
        daemon_mode(args.interval)
        return 0

    elif args.command == "status":
        show_registry_status()
        return 0

    elif args.command == "promote":
        success = promote_version(
            args.version,
            min_r2=args.min_r2,
            max_rmse=args.max_rmse,
            max_mae=args.max_mae,
        )
        return 0 if success else 1

    elif args.command == "rollback":
        success = rollback_version(args.version)
        return 0 if success else 1

    elif args.command == "config":
        registry = get_registry()
        config = registry.get_retraining_config()

        if args.enable:
            config.enabled = True
        if args.disable:
            config.enabled = False
        if args.schedule:
            config.schedule_cron = args.schedule
        if args.min_r2 is not None:
            config.acceptance_criteria.min_r2 = args.min_r2
        if args.max_rmse is not None:
            config.acceptance_criteria.max_rmse = args.max_rmse
        if args.max_mae is not None:
            config.acceptance_criteria.max_mae = args.max_mae

        registry.save_retraining_config(config)
        print("Configuration updated:")
        print(f"  Enabled: {config.enabled}")
        print(f"  Schedule: {config.schedule_cron}")
        print(f"  Acceptance: {config.acceptance_criteria.to_dict()}")
        return 0

    elif args.command == "approve":
        success = approve_version(
            args.version,
            min_r2=args.min_r2,
            max_rmse=args.max_rmse,
            max_mae=args.max_mae,
        )
        return 0 if success else 1

    elif args.command == "reject":
        success = reject_version(args.version, reason=args.reason)
        return 0 if success else 1

    elif args.command == "archive":
        success = archive_version(args.version)
        return 0 if success else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
