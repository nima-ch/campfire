#!/usr/bin/env python3
"""
Backup and restore functionality for Campfire Emergency Helper.
Handles corpus database, audit logs, and configuration backup/restore.
"""

import os
import sys
import json
import shutil
import tarfile
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CampfireBackup:
    """Backup and restore manager for Campfire system."""
    
    def __init__(self):
        self.backup_items = {
            "corpus_db": os.getenv("CAMPFIRE_CORPUS_DB", "corpus/processed/corpus.db"),
            "audit_db": os.getenv("CAMPFIRE_AUDIT_DB", "data/audit.db"),
            "policy_file": os.getenv("CAMPFIRE_POLICY_PATH", "policy.md"),
            "config_files": [
                "pyproject.toml",
                "uv.lock",
                "Makefile",
                ".gitignore"
            ],
            "logs_dir": "logs",
            "data_dir": "data"
        }
    
    def create_backup(self, backup_path: str, include_logs: bool = False) -> bool:
        """Create a complete system backup."""
        logger.info(f"Creating backup: {backup_path}")
        
        backup_file = Path(backup_path)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "version": self._get_version(),
            "backup_type": "full",
            "include_logs": include_logs,
            "items": {}
        }
        
        try:
            with tarfile.open(backup_file, "w:gz") as tar:
                # Backup corpus database
                corpus_path = Path(self.backup_items["corpus_db"])
                if corpus_path.exists():
                    logger.info(f"Backing up corpus database: {corpus_path}")
                    tar.add(corpus_path, arcname="corpus.db")
                    metadata["items"]["corpus_db"] = {
                        "original_path": str(corpus_path),
                        "size": corpus_path.stat().st_size,
                        "modified": corpus_path.stat().st_mtime
                    }
                else:
                    logger.warning(f"Corpus database not found: {corpus_path}")
                
                # Backup audit database
                audit_path = Path(self.backup_items["audit_db"])
                if audit_path.exists():
                    logger.info(f"Backing up audit database: {audit_path}")
                    tar.add(audit_path, arcname="audit.db")
                    metadata["items"]["audit_db"] = {
                        "original_path": str(audit_path),
                        "size": audit_path.stat().st_size,
                        "modified": audit_path.stat().st_mtime
                    }
                else:
                    logger.info("Audit database not found (will be created on restore)")
                
                # Backup policy file
                policy_path = Path(self.backup_items["policy_file"])
                if policy_path.exists():
                    logger.info(f"Backing up policy file: {policy_path}")
                    tar.add(policy_path, arcname="policy.md")
                    metadata["items"]["policy_file"] = {
                        "original_path": str(policy_path),
                        "size": policy_path.stat().st_size,
                        "modified": policy_path.stat().st_mtime
                    }
                
                # Backup configuration files
                config_files = []
                for config_file in self.backup_items["config_files"]:
                    config_path = Path(config_file)
                    if config_path.exists():
                        logger.info(f"Backing up config file: {config_path}")
                        tar.add(config_path, arcname=f"config/{config_file}")
                        config_files.append(str(config_path))
                
                metadata["items"]["config_files"] = config_files
                
                # Backup logs if requested
                if include_logs:
                    logs_path = Path(self.backup_items["logs_dir"])
                    if logs_path.exists():
                        logger.info(f"Backing up logs directory: {logs_path}")
                        tar.add(logs_path, arcname="logs")
                        metadata["items"]["logs_dir"] = str(logs_path)
                
                # Backup additional data directory
                data_path = Path(self.backup_items["data_dir"])
                if data_path.exists():
                    logger.info(f"Backing up data directory: {data_path}")
                    # Exclude audit.db as it's backed up separately
                    for item in data_path.iterdir():
                        if item.name != "audit.db":
                            tar.add(item, arcname=f"data/{item.name}")
                
                # Add metadata
                metadata_json = json.dumps(metadata, indent=2)
                info = tarfile.TarInfo(name="backup_metadata.json")
                info.size = len(metadata_json.encode())
                tar.addfile(info, fileobj=tarfile.io.BytesIO(metadata_json.encode()))
            
            logger.info(f"✅ Backup created successfully: {backup_file}")
            logger.info(f"Backup size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            # Clean up partial backup
            if backup_file.exists():
                backup_file.unlink()
            return False
    
    def restore_backup(self, backup_path: str, force: bool = False) -> bool:
        """Restore system from backup."""
        logger.info(f"Restoring from backup: {backup_path}")
        
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False
        
        try:
            # Read backup metadata
            with tarfile.open(backup_file, "r:gz") as tar:
                try:
                    metadata_file = tar.extractfile("backup_metadata.json")
                    if metadata_file:
                        metadata = json.loads(metadata_file.read().decode())
                        logger.info(f"Backup created: {metadata['timestamp']}")
                        logger.info(f"Backup version: {metadata.get('version', 'unknown')}")
                    else:
                        logger.warning("No metadata found in backup")
                        metadata = {}
                except KeyError:
                    logger.warning("No metadata found in backup")
                    metadata = {}
                
                # Check if files exist and prompt for confirmation
                if not force:
                    conflicts = []
                    
                    # Check corpus database
                    corpus_path = Path(self.backup_items["corpus_db"])
                    if corpus_path.exists():
                        conflicts.append(str(corpus_path))
                    
                    # Check audit database
                    audit_path = Path(self.backup_items["audit_db"])
                    if audit_path.exists():
                        conflicts.append(str(audit_path))
                    
                    if conflicts:
                        logger.warning("The following files will be overwritten:")
                        for conflict in conflicts:
                            logger.warning(f"  - {conflict}")
                        
                        response = input("Continue with restore? (y/N): ")
                        if response.lower() != 'y':
                            logger.info("Restore cancelled")
                            return False
                
                # Create backup of existing files
                backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Restore corpus database
                if "corpus.db" in tar.getnames():
                    corpus_path = Path(self.backup_items["corpus_db"])
                    if corpus_path.exists():
                        backup_corpus = corpus_path.with_suffix(f".backup_{backup_timestamp}")
                        shutil.copy2(corpus_path, backup_corpus)
                        logger.info(f"Backed up existing corpus to: {backup_corpus}")
                    
                    corpus_path.parent.mkdir(parents=True, exist_ok=True)
                    tar.extract("corpus.db", path=corpus_path.parent)
                    shutil.move(corpus_path.parent / "corpus.db", corpus_path)
                    logger.info(f"✅ Restored corpus database: {corpus_path}")
                
                # Restore audit database
                if "audit.db" in tar.getnames():
                    audit_path = Path(self.backup_items["audit_db"])
                    if audit_path.exists():
                        backup_audit = audit_path.with_suffix(f".backup_{backup_timestamp}")
                        shutil.copy2(audit_path, backup_audit)
                        logger.info(f"Backed up existing audit to: {backup_audit}")
                    
                    audit_path.parent.mkdir(parents=True, exist_ok=True)
                    tar.extract("audit.db", path=audit_path.parent)
                    shutil.move(audit_path.parent / "audit.db", audit_path)
                    logger.info(f"✅ Restored audit database: {audit_path}")
                
                # Restore policy file
                if "policy.md" in tar.getnames():
                    policy_path = Path(self.backup_items["policy_file"])
                    if policy_path.exists():
                        backup_policy = policy_path.with_suffix(f".backup_{backup_timestamp}")
                        shutil.copy2(policy_path, backup_policy)
                        logger.info(f"Backed up existing policy to: {backup_policy}")
                    
                    tar.extract("policy.md", path=".")
                    logger.info(f"✅ Restored policy file: {policy_path}")
                
                # Restore configuration files
                config_members = [m for m in tar.getmembers() if m.name.startswith("config/")]
                if config_members:
                    logger.info("Restoring configuration files...")
                    for member in config_members:
                        config_name = member.name.replace("config/", "")
                        config_path = Path(config_name)
                        
                        if config_path.exists():
                            backup_config = config_path.with_suffix(f".backup_{backup_timestamp}")
                            shutil.copy2(config_path, backup_config)
                            logger.info(f"Backed up existing config to: {backup_config}")
                        
                        tar.extract(member, path=".")
                        shutil.move(f"config/{config_name}", config_name)
                        logger.info(f"✅ Restored config: {config_name}")
                    
                    # Clean up config directory
                    config_dir = Path("config")
                    if config_dir.exists():
                        shutil.rmtree(config_dir)
                
                # Restore logs if present
                logs_members = [m for m in tar.getmembers() if m.name.startswith("logs/")]
                if logs_members:
                    logger.info("Restoring logs directory...")
                    logs_path = Path(self.backup_items["logs_dir"])
                    if logs_path.exists():
                        backup_logs = logs_path.with_suffix(f"_backup_{backup_timestamp}")
                        shutil.move(logs_path, backup_logs)
                        logger.info(f"Backed up existing logs to: {backup_logs}")
                    
                    for member in logs_members:
                        tar.extract(member, path=".")
                    logger.info(f"✅ Restored logs directory: {logs_path}")
                
                # Restore data directory
                data_members = [m for m in tar.getmembers() if m.name.startswith("data/") and not m.name.endswith("audit.db")]
                if data_members:
                    logger.info("Restoring additional data files...")
                    for member in data_members:
                        tar.extract(member, path=".")
                        logger.info(f"✅ Restored: {member.name}")
            
            logger.info("✅ Restore completed successfully!")
            logger.info("Please restart the Campfire service to apply changes.")
            return True
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False
    
    def list_backup_contents(self, backup_path: str) -> bool:
        """List contents of a backup file."""
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False
        
        try:
            with tarfile.open(backup_file, "r:gz") as tar:
                # Read metadata if available
                try:
                    metadata_file = tar.extractfile("backup_metadata.json")
                    if metadata_file:
                        metadata = json.loads(metadata_file.read().decode())
                        print(f"Backup Information:")
                        print(f"  Created: {metadata['timestamp']}")
                        print(f"  Version: {metadata.get('version', 'unknown')}")
                        print(f"  Type: {metadata.get('backup_type', 'unknown')}")
                        print(f"  Includes logs: {metadata.get('include_logs', False)}")
                        print()
                except KeyError:
                    print("No metadata available")
                    print()
                
                # List all files
                print("Backup Contents:")
                members = tar.getmembers()
                for member in sorted(members, key=lambda x: x.name):
                    if member.isfile():
                        size_mb = member.size / 1024 / 1024
                        print(f"  {member.name} ({size_mb:.2f} MB)")
                    elif member.isdir():
                        print(f"  {member.name}/ (directory)")
                
                total_size = sum(m.size for m in members if m.isfile())
                print(f"\nTotal size: {total_size / 1024 / 1024:.2f} MB")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to read backup: {e}")
            return False
    
    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity."""
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False
        
        try:
            logger.info(f"Verifying backup: {backup_file}")
            
            with tarfile.open(backup_file, "r:gz") as tar:
                # Check if all expected files are present
                members = tar.getnames()
                
                # Verify corpus database
                if "corpus.db" in members:
                    logger.info("✅ Corpus database found")
                else:
                    logger.warning("⚠️  Corpus database not found in backup")
                
                # Verify metadata
                if "backup_metadata.json" in members:
                    logger.info("✅ Backup metadata found")
                    
                    # Validate metadata
                    metadata_file = tar.extractfile("backup_metadata.json")
                    if metadata_file:
                        metadata = json.loads(metadata_file.read().decode())
                        required_fields = ["timestamp", "backup_type"]
                        for field in required_fields:
                            if field in metadata:
                                logger.info(f"✅ Metadata field '{field}': {metadata[field]}")
                            else:
                                logger.warning(f"⚠️  Missing metadata field: {field}")
                else:
                    logger.warning("⚠️  Backup metadata not found")
                
                # Test extraction of a small file
                try:
                    if "backup_metadata.json" in members:
                        tar.extractfile("backup_metadata.json").read()
                        logger.info("✅ File extraction test passed")
                except Exception as e:
                    logger.error(f"❌ File extraction test failed: {e}")
                    return False
            
            logger.info("✅ Backup verification completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup verification failed: {e}")
            return False
    
    def _get_version(self) -> str:
        """Get current Campfire version."""
        try:
            # Try to read version from pyproject.toml
            import tomllib
            with open("pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "unknown")
        except Exception:
            return "unknown"


def main():
    """Main backup/restore function."""
    parser = argparse.ArgumentParser(description="Campfire Backup and Restore Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create a backup")
    backup_parser.add_argument("path", help="Backup file path")
    backup_parser.add_argument("--include-logs", action="store_true", help="Include log files")
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("path", help="Backup file path")
    restore_parser.add_argument("--force", action="store_true", help="Force restore without confirmation")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List backup contents")
    list_parser.add_argument("path", help="Backup file path")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify backup integrity")
    verify_parser.add_argument("path", help="Backup file path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    backup_manager = CampfireBackup()
    
    if args.command == "backup":
        success = backup_manager.create_backup(args.path, args.include_logs)
    elif args.command == "restore":
        success = backup_manager.restore_backup(args.path, args.force)
    elif args.command == "list":
        success = backup_manager.list_backup_contents(args.path)
    elif args.command == "verify":
        success = backup_manager.verify_backup(args.path)
    else:
        parser.print_help()
        return
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()