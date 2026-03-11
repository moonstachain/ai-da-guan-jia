#!/usr/bin/env python3
"""Build a local restore bundle for the next Mac."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path


def expand_path(value: str, workspace_root: Path) -> Path:
    expanded = value.replace("$WORKSPACE_ROOT", str(workspace_root))
    return Path(os.path.expandvars(os.path.expanduser(expanded))).resolve()


def copy_asset(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_bundle(
    manifest_path: Path,
    output_dir: Path,
    workspace_root: Path,
    include_history: bool,
) -> tuple[Path, Path, list[dict[str, object]]]:
    manifest = load_manifest(manifest_path)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    bundle_name = f"codex-new-mac-restore-{timestamp}"
    staging_root = output_dir / bundle_name
    archive_path = output_dir / f"{bundle_name}.tar.gz"

    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    included_assets: list[dict[str, object]] = []
    asset_groups = [("secret_assets", True)]
    if include_history:
        asset_groups.append(("optional_history_assets", False))

    for group_name, required_default in asset_groups:
        for asset in manifest.get(group_name, []):
            source = expand_path(asset["source"], workspace_root)
            destination = staging_root / asset["bundle_path"]
            required = bool(asset.get("required", required_default))
            if not source.exists():
                if required:
                    raise FileNotFoundError(f"required asset is missing: {source}")
                continue
            copy_asset(source, destination)
            included_assets.append(
                {
                    "id": asset["id"],
                    "source": str(source),
                    "bundle_path": str(Path(asset["bundle_path"])),
                }
            )

    shutil.copy2(manifest_path, staging_root / "migration-manifest.json")
    metadata = {
        "bundle_name": bundle_name,
        "created_at": datetime.now().astimezone().isoformat(),
        "workspace_root": str(workspace_root),
        "include_history": include_history,
        "included_assets": included_assets,
    }
    (staging_root / "bundle-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(staging_root, arcname=bundle_name)

    return staging_root, archive_path, included_assets


def encrypt_archive(archive_path: Path, env_name: str) -> Path:
    encrypted_path = archive_path.with_suffix(archive_path.suffix + ".enc")
    passphrase = os.environ.get(env_name)
    if not passphrase:
        passphrase = getpass.getpass(f"Passphrase for {encrypted_path.name}: ")
    env = os.environ.copy()
    env[env_name] = passphrase
    subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-pbkdf2",
            "-salt",
            "-in",
            str(archive_path),
            "-out",
            str(encrypted_path),
            "-pass",
            f"env:{env_name}",
        ],
        check=True,
        env=env,
    )
    return encrypted_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="migration-manifest.json",
        help="Path to the migration manifest.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/migration",
        help="Directory where the bundle should be created.",
    )
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Include optional historical Codex state in the archive.",
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Encrypt the generated tar.gz archive with openssl.",
    )
    parser.add_argument(
        "--passphrase-env",
        default="RESTORE_BUNDLE_PASSPHRASE",
        help="Environment variable that contains the encryption passphrase.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = Path.cwd().resolve()
    manifest_path = expand_path(args.manifest, workspace_root)
    output_dir = expand_path(args.output_dir, workspace_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    staging_root, archive_path, included_assets = build_bundle(
        manifest_path=manifest_path,
        output_dir=output_dir,
        workspace_root=workspace_root,
        include_history=args.include_history,
    )

    result: dict[str, object] = {
        "staging_root": str(staging_root),
        "archive_path": str(archive_path),
        "included_assets": included_assets,
    }

    if args.encrypt:
        encrypted_path = encrypt_archive(archive_path, args.passphrase_env)
        result["encrypted_archive_path"] = str(encrypted_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
