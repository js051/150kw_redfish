#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
create_package.py

說明:
  為一個多模組的 Monorepo 專案建立一個 增量式 或 全量式 的離線更新包。
  此腳本具備位置獨立性，可以放置在專案的任何子目錄中。它會自動偵測含有 `.git`
  的專案根目錄，並以此為基準執行所有操作。

特性:
  - 提供兩種打包模式：
    1. 增量模式：比較兩個 Git 版本，只打包差異內容。
    2. 全量模式：打包指定單一版本的所有內容，用於全新安裝或版本歸檔。
  - 只打包新增或版本變更的 Python 依賴（增量模式為差異打包，全量模式為全部打包）。
  - 產生一個 `delete.list` 檔案（僅增量模式）。
  - 整個過程完全基於 Git 資料庫，不受當前工作目錄狀態的影響。
  - 輸出為一個「確定性」的 .tar.gz 壓縮包，確保每次建構的結果完全一致。

使用方法:
  python3 /path/to/create_package.py <舊版本> <新版本> [選項]
  注意：在 `--full` 模式下，`舊版本` 參數會被忽略，可以隨意填寫（例如 'ignored'）。

使用範例 (從專案根目錄執行):

  --- 增量包範例 ---
  # 比較兩個標籤 (tag)，產生增量包
  python3 ./sidecar-redfish/etc/scripts/create_package.py v0.1.0 v0.3.1

  # 比較某個標籤和當前的最新程式碼 (HEAD)
  python3 ./sidecar-redfish/etc/scripts/create_package.py v0.3.1 HEAD

  --- 全量包範例 ---
  # 建立 v1.0.0 的完整發布包（舊版本參數會被忽略）
  python3 ./sidecar-redfish/etc/scripts/create_package.py ignored v1.0.0 --full

  --- 其他選項 ---
  # 指定輸出檔名，並在開發時強制執行（忽略工作目錄檢查）
  python3 ./sidecar-redfish/etc/scripts/create_package.py v0.1.0 v0.3.1 -o /tmp/my_update.tar.gz --force

必要條件:
  - Python 3.8+
  - Git 命令列工具
  - pip 命令列工具
  - `pathspec` 函式庫 (`pip install pathspec`)
"""

import argparse
import gzip
import io
import logging
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

# Check for required 'pathspec' library.
try:
    import pathspec
except ImportError:
    # Use a direct print here as logging might not be configured yet.
    print("\033[91mError: 'pathspec' library not found. Please install it with 'pip install pathspec'\033[0m", file=sys.stderr)
    sys.exit(1)

# --- Constants and Global Configuration ---

# Style class for console output colors.
class Style:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# A fixed timestamp for all file metadata to ensure deterministic builds.
FIXED_MTIME = 1735689600  # 2025-01-01 00:00:00 UTC

# Configure logging for clear, colored output.
LOGGING_FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT, stream=sys.stdout)
logging.addLevelName(logging.INFO, f"{Style.GREEN}{logging.getLevelName(logging.INFO)}{Style.END}")
logging.addLevelName(logging.WARNING, f"{Style.YELLOW}{logging.getLevelName(logging.WARNING)}{Style.END}")
logging.addLevelName(logging.ERROR, f"{Style.RED}{logging.getLevelName(logging.ERROR)}{Style.END}")


# --- Core Functions ---

def get_all_files(project_root, version):
    """Get a list of all files at a specific git version."""
    logging.info(f"--- Getting all files for a full package at version '{version}' ---")
    ls_tree_result = run_command(["git", "ls-tree", "-r", "--name-only", version], cwd=project_root)
    # Ensure consistent path separators
    all_files = [p.replace(os.sep, '/') for p in ls_tree_result.stdout.strip().splitlines()]
    logging.info(f"Found {len(all_files)} total files in the repository.")
    return all_files

def get_all_dependencies(project_root, version):
    """Get all dependencies from all requirements.txt files at a specific version."""
    logging.info("--- Getting all Python dependencies for a full package ---")
    all_deps = {}
    req_files_result = run_command(["git", "ls-tree", "-r", "--name-only", version], cwd=project_root)
    req_files = [p for p in req_files_result.stdout.splitlines() if p.endswith("requirements.txt")]

    for req_path_str in req_files:
        module_dir_path = Path(req_path_str).parent
        module_display_name = str(module_dir_path) if str(module_dir_path) != '.' else '<root>'
        
        content = get_file_content_from_git(project_root, version, req_path_str)
        packages = parse_requirements(content)
        
        if packages:
            logging.info(f"Module '{Style.BOLD}{module_display_name}{Style.END}': Found {len(packages)} dependencies.")
            all_deps[str(module_dir_path)] = [f"{pkg}=={ver}" for pkg, ver in packages.items()]
    
    if not all_deps:
        logging.info("No dependencies found.")
    return all_deps

def find_project_root() -> Path:
    """Find the project root by searching upwards for the .git directory."""
    current_path = Path(__file__).resolve().parent
    while current_path != current_path.parent:
        if (current_path / ".git").is_dir():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError("Fatal: Could not find project root (.git directory). Make sure the script is inside a Git repository.")

def run_command(command, check=True, capture_output=True, text=True, cwd=None, **kwargs):
    """Execute a subprocess command, handling errors gracefully."""
    try:
        # Run command from the specified working directory (cwd).
        result = subprocess.run(command, check=check, capture_output=capture_output, text=text, cwd=cwd, **kwargs)
        return result
    except FileNotFoundError:
        logging.error(f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {' '.join(command)}")
        # Output stderr if available, otherwise stdout, for better error reporting.
        logging.error(f"Stderr: {e.stderr.strip() if e.stderr else e.stdout.strip()}")
        sys.exit(1)

def preflight_checks(project_root, old_version, new_version, force=False):
    """Perform critical checks before starting the main process."""
    logging.info("--- Running Pre-flight Checks ---")
    
    # Check that git and pip are available.
    run_command(["git", "--version"], cwd=project_root)
    run_command(["pip", "--version"], cwd=project_root)
    
    # Verify that the provided git versions are valid.
    run_command(["git", "cat-file", "-e", f"{old_version}^{{commit}}"], cwd=project_root)
    run_command(["git", "cat-file", "-e", f"{new_version}^{{commit}}"], cwd=project_root)

    # Enforce a strictly clean working directory unless --force is used.
    if not force:
        status_result = run_command(["git", "status", "--porcelain"], cwd=project_root)
        if status_result.stdout:
            logging.error("Error: Working directory is not clean. Please commit or stash your changes.")
            logging.error(f"To override this check for development, use the {Style.BOLD}--force{Style.END} flag.")
            logging.error("Found uncommitted changes:\n" + status_result.stdout)
            sys.exit(1)
    else:
        logging.warning(f"{Style.BOLD}WARNING: Running in --force mode.{Style.END}")
        logging.warning("The working directory is not being checked for cleanliness.")
        logging.warning("This is NOT recommended for production builds.")

    logging.info("Pre-flight checks passed.")

def parse_requirements(content: str) -> dict:
    """
    Parse requirements.txt content into a {'package': 'version'} dictionary.
    NOTE: This is a basic parser. It does not support complex specifiers like
    '>=', '~=', or extras. This is a known trade-off for simplicity.
    """
    packages = {}
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split('==')
            if len(parts) == 2:
                packages[parts[0].strip()] = parts[1].strip()
    return packages

def get_file_content_from_git(project_root, version, file_path):
    """Retrieve the content of a specific file from a specific git version."""
    result = run_command(["git", "show", f"{version}:{file_path}"], check=False, cwd=project_root)
    return result.stdout if result.returncode == 0 else ""

def get_dependency_changes(project_root, old_version, new_version):
    """Compare all requirements.txt files to find new or updated dependencies."""
    logging.info("--- Analyzing Python dependency changes ---")
    changes = {}
    
    req_files_result = run_command(["git", "ls-tree", "-r", "--name-only", new_version], cwd=project_root)
    req_files = [p for p in req_files_result.stdout.splitlines() if p.endswith("requirements.txt")]

    for req_path_str in req_files:
        module_dir_path = Path(req_path_str).parent
        # Display root directory as '<root>' for better log clarity.
        module_display_name = str(module_dir_path) if str(module_dir_path) != '.' else '<root>'
        
        old_content = get_file_content_from_git(project_root, old_version, req_path_str)
        new_content = get_file_content_from_git(project_root, new_version, req_path_str)

        old_reqs = parse_requirements(old_content)
        new_reqs = parse_requirements(new_content)

        if old_reqs == new_reqs:
            continue

        module_changes = [f"{pkg}=={ver}" for pkg, ver in new_reqs.items() if pkg not in old_reqs or old_reqs[pkg] != ver]
        
        if module_changes:
            logging.info(f"Module '{Style.BOLD}{module_display_name}{Style.END}': Found {len(module_changes)} changed dependencies.")
            changes[str(module_dir_path)] = module_changes

    if not changes:
        logging.info("No dependency changes found.")
    
    return changes

def download_wheels(changes, temp_dir, py_version, platform):
    """Download specified wheels into module-specific subdirectories."""
    if not changes:
        return False
        
    logging.info("--- Downloading changed wheels ---")
    wheels_base_dir = temp_dir / "wheels"
    wheels_base_dir.mkdir()

    for module_path, packages in changes.items():
        target_dir = wheels_base_dir / module_path
        target_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Downloading for '{Style.BOLD}{module_path}{Style.END}': {len(packages)} packages")
        
        # NOTE: Using --no-deps is a conscious trade-off for speed. It relies on
        # requirements.txt being a complete freeze of all dependencies.
        requirements_content = "\n".join(packages)
        pip_command = [
            sys.executable, "-m", "pip", "download",
            "--dest", str(target_dir),
            "--platform", platform,
            "--python-version", py_version,
            "--only-binary=:all:",
            "--no-deps",
            "--requirement", "-",  # Read requirements from stdin
        ]
        result = run_command(pip_command, check=False, input=requirements_content)
        if result.returncode != 0:
            logging.warning(f"pip download may have failed for some packages in '{module_path}'.")

    return any(wheels_base_dir.rglob("*.whl"))

def get_file_diff(project_root, old_version, new_version):
    """Get lists of files to add/update (A,C,M,R) and files to delete (D,R)."""
    logging.info("--- Analyzing application file changes ---")
    
    # Use -z for null-termination to robustly handle all possible filenames.
    diff_result = run_command([
        "git", "diff-tree", "-r", "-z", "--no-commit-id", "--name-status",
        "--diff-filter=ACMRD", old_version, new_version
    ], cwd=project_root)

    files_to_add = []
    files_to_delete = []
    
    entries = diff_result.stdout.strip('\0').split('\0')
    i = 0
    while i < len(entries):
        status = entries[i]
        # Ensure all paths use POSIX separators ('/') for consistency.
        if status.startswith('R'):
            old_path = entries[i + 1].replace(os.sep, '/')
            new_path = entries[i + 2].replace(os.sep, '/')
            files_to_delete.append(old_path)
            files_to_add.append(new_path)
            i += 3
        else:
            path = entries[i + 1].replace(os.sep, '/')
            if status == 'D':
                files_to_delete.append(path)
            else:
                files_to_add.append(path)
            i += 2

    logging.info(f"Found {len(files_to_add)} files to add/update and {len(files_to_delete)} files to delete.")
    return files_to_add, files_to_delete

def filter_files_with_distignore(project_root, files_to_add):
    """Filter files using .distignore rules, which follow .gitignore syntax."""
    distignore_path = project_root / ".distignore"
    if not distignore_path.is_file():
        logging.warning("Warning: .distignore not found at project root. All changed files will be packaged.")
        return files_to_add

    logging.info(f"--- Applying .distignore rules from '{distignore_path}' ---")
    with open(distignore_path, "r", encoding="utf-8") as f:
        patterns = f.read()
    
    spec = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, patterns.splitlines())
    
    ignored_files = set(spec.match_files(files_to_add))
    final_files = [f for f in files_to_add if f not in ignored_files]

    if ignored_files:
        logging.info(f"Excluded {len(ignored_files)} files based on .distignore rules.")
    
    return final_files

def reset_tarinfo(ti: tarfile.TarInfo) -> tarfile.TarInfo:
    """Filter to reset tar metadata for deterministic output."""
    ti.mtime = FIXED_MTIME
    ti.uid = 0
    ti.gid = 0
    ti.uname = "root"
    ti.gname = "root"
    return ti

def create_archive(project_root, output_path, files_to_add, files_to_delete, temp_dir, new_version, has_wheels):
    """Create the final .tar.gz archive with deterministic properties."""
    logging.info(f"--- Creating archive: {Style.BOLD}{output_path}{Style.END} ---")
    
    tar_members = []

    # Prepare application files for archiving.
    if files_to_add:
        logging.info(f"Preparing {len(files_to_add)} application files...")
        
        # NOTE: For extremely large diffs, this `git ls-tree` command could exceed
        # command-line length limits. A chunking strategy would be needed for such cases.
        ls_tree_result = run_command(["git", "ls-tree", "-r", new_version] + files_to_add, cwd=project_root)
        file_modes = {line.split()[3]: int(line.split()[0], 8) for line in ls_tree_result.stdout.strip().splitlines()}
        
        for file_path_str in files_to_add:
            content_bytes = run_command(["git", "show", f"{new_version}:{file_path_str}"], text=False, cwd=project_root).stdout
            
            tarinfo = tarfile.TarInfo(name=f"app/{file_path_str}")
            tarinfo.size = len(content_bytes)
            # Fetch file permissions directly from Git to ensure accuracy.
            tarinfo.mode = file_modes.get(file_path_str, 0o644)
            tar_members.append((tarinfo, content_bytes))

    # Prepare delete.list for archiving.
    if files_to_delete:
        delete_content = "\n".join(files_to_delete).encode('utf-8')
        tarinfo = tarfile.TarInfo(name="delete.list")
        tarinfo.size = len(delete_content)
        tarinfo.mode = 0o644
        tar_members.append((tarinfo, delete_content))
    
    # Sort all members by name before adding for true determinism.
    tar_members.sort(key=lambda item: item[0].name)

    # Use gzip.GzipFile to control the header mtime for a fully deterministic archive.
    with gzip.GzipFile(filename=output_path, mode='wb', mtime=FIXED_MTIME) as gzf:
        with tarfile.open(fileobj=gzf, mode='w') as tar:
            # Add prepared file members.
            for tarinfo, content_bytes in tar_members:
                # Manually apply deterministic TarInfo properties.
                tarinfo = reset_tarinfo(tarinfo)
                with io.BytesIO(content_bytes) as bio:
                    tar.addfile(tarinfo, bio)
            
            # Add the entire 'wheels' directory structure.
            if has_wheels:
                logging.info("Adding wheels...")
                wheels_dir = temp_dir / "wheels"
                tar.add(wheels_dir, arcname="wheels", filter=reset_tarinfo)

def main():
    """Main execution flow: parse args, run checks, and build the package."""
    parser = argparse.ArgumentParser(
        description="Create an incremental update package for a Monorepo project.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("old_version", help="The old Git version (tag, commit, or branch).")
    parser.add_argument("new_version", help="The new Git version (tag, commit, or branch).")
    parser.add_argument("-o", "--output-file", help="Path for the output .tar.gz file.")
    parser.add_argument("--py-version", default="3.10", help="Python version for downloading wheels.")
    parser.add_argument("--platform", default="manylinux2014_x86_64", help="Platform for downloading wheels.")
    parser.add_argument("--force", action="store_true", help="Bypass the clean working directory check. For development use ONLY.")
    parser.add_argument("--full", action="store_true", help="Create a full package of the new_version, ignoring old_version.")
    args = parser.parse_args()

    try:
        project_root = find_project_root()
        logging.info(f"Project root detected at: {project_root}")
        
        # --- FILENAME AND MODE LOGIC ---
        if args.full:
            # Full package mode
            new_safe = args.new_version.replace('/', '-')
            output_path = Path.cwd() / f"ITG_Full-Package_{new_safe}.tar.gz"
            logging.info(f"{Style.BLUE}Starting FULL package creation for version: {args.new_version}{Style.END}")
            # In full mode, 'old_version' is conceptually the same as 'new_version' for checks
            preflight_checks(project_root, args.new_version, args.new_version, args.force)
        else:
            # Incremental package mode
            old_safe = args.old_version.replace('/', '-'); new_safe = args.new_version.replace('/', '-')
            output_path = Path.cwd() / f"ITG_Update_{old_safe}_to_{new_safe}.tar.gz"
            logging.info(f"{Style.BLUE}Starting INCREMENTAL package creation: {args.old_version} -> {args.new_version}{Style.END}")
            preflight_checks(project_root, args.old_version, args.new_version, args.force)
        
        if args.output_file:
            output_path = Path(args.output_file).resolve()
            
        with TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            # --- GATHER FILES AND DEPENDENCIES BASED ON MODE ---
            if args.full:
                dep_changes = get_all_dependencies(project_root, args.new_version)
                files_to_add = get_all_files(project_root, args.new_version)
                files_to_delete = [] # No delete list for full package
            else:
                dep_changes = get_dependency_changes(project_root, args.old_version, args.new_version)
                files_to_add, files_to_delete = get_file_diff(project_root, args.old_version, args.new_version)

            has_wheels = download_wheels(dep_changes, temp_dir, args.py_version, args.platform)
            final_files_to_add = filter_files_with_distignore(project_root, files_to_add)
            
            if final_files_to_add or has_wheels:
                create_archive(project_root, output_path, final_files_to_add, files_to_delete, temp_dir, args.new_version, has_wheels)
                logging.info(f"\n{Style.BOLD}--- Success! ---{Style.END}")
                logging.info(f"Package created at: {Style.BOLD}{output_path}{Style.END}")
            else:
                logging.warning("No changes detected or no files to package. No package was created.")

    except Exception as e:
        logging.error(f"\nAn unexpected error occurred: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()