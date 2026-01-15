import argparse
import getpass
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import keyring
import requests

sys.path.insert(0, os.path.dirname(__file__))  # <-- add this line

from rbz.http import Options, build_session

# === LOAD CONFIG ===
DEFAULT_CONFIG = {
    "repo_branch": "main",
    "local_repo_path": "C:/Rapidbotz/mobilitas-rapidbotz-local-agent"
}

def load_config():
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                user_config = json.load(f)
                print("Loaded custom configuration from config.json.")
                return {**DEFAULT_CONFIG, **user_config}
        except json.JSONDecodeError:
            print("ERROR: config.json is invalid. Using default settings.")
    else:
        print("No config.json found. Using default settings.")
    return DEFAULT_CONFIG

CONFIG = load_config()
BRANCH = CONFIG["repo_branch"]
LOCAL_REPO_DIR = CONFIG["local_repo_path"]

# === CONSTANTS ===
GITHUB_REPO = "aaa-ncnu-ie/mobilitas-rapidbotz-local-agent"
CLONE_URL = "git@github.com:aaa-ncnu-ie/mobilitas-rapidbotz-local-agent.git"
SERVICE_NAME = "Rapidbotz"
SSH_DIR = Path.home() / ".ssh"
SSH_KEY = SSH_DIR / "id_ed25519"
SCRIPT_DIR = Path(__file__).resolve().parent
STATUS_FILE = SCRIPT_DIR / "bootstrapper-status.json"
LOCK_FILE = SCRIPT_DIR / "bootstrapper.lock"
VERSION_FILE = SCRIPT_DIR / "version.txt"

# === HTTP OPTIONS ===
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ca-bundle", help="Path to a custom CA bundle")
    parser.add_argument("--proxy", help="Proxy URL for both HTTP and HTTPS")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (unsafe; for local testing only)",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Print diagnostic information and exit without making changes.",
    )
    parser.add_argument(
        "--force-restart",
        action="store_true",
        help="Restart the agent even if no updates are detected.",
    )
    return parser.parse_args()

def configure_logging(log_level=logging.INFO):
    log_format = "%(asctime)sZ %(levelname)s %(message)s"
    log_path = SCRIPT_DIR / "bootstrapper.log"
    handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")]
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
    )

def get_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "unknown"

def write_status(status: str, detail: str = "", extra: dict | None = None):
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "detail": detail,
        "version": get_version(),
        "hostname": socket.gethostname(),
    }
    if extra:
        payload.update(extra)
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def ensure_single_instance():
    if LOCK_FILE.exists():
        try:
            existing = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = existing.get("pid")
            if pid and is_pid_running(pid):
                logging.error("Another bootstrapper instance is running (pid=%s).", pid)
                write_status("blocked", "Another bootstrapper instance is running.", {"pid": pid})
                sys.exit(2)
        except Exception:
            logging.warning("Failed to read existing lock file; continuing with new lock.")
    lock_data = {
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    LOCK_FILE.write_text(json.dumps(lock_data, indent=2), encoding="utf-8")

def release_lock():
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception as exc:
            logging.warning("Failed to remove lock file: %s", exc)

# === CREDENTIAL MANAGEMENT ===
def get_credential(key, prompt):
    credential = keyring.get_password(SERVICE_NAME, key)
    if not credential:
        print(f"\n{prompt}")
        credential = getpass.getpass("Your input will be hidden for security: ")
        if not credential:
            print(f"ERROR: {key} is required!")
            sys.exit(1)
        keyring.set_password(SERVICE_NAME, key, credential)
        print(f"{key} saved securely in Windows Credential Manager.")
    return credential

# === SSH KEY GENERATION AND UPLOAD ===
def generate_ssh_key(email):
    if not SSH_DIR.exists():
        SSH_DIR.mkdir()
    if not SSH_KEY.exists():
        print("Generating a new SSH key for GitHub...")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-C", email, "-f", str(SSH_KEY), "-N", ""],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print(f"SSH key generated at {SSH_KEY}")
        return True  # Indicate a new key was generated
    return False  # No new key generated

def add_ssh_key_to_github(token, public_key_path, session: requests.Session, timeout: float):
    with open(public_key_path, "r") as f:
        public_key = f.read().strip()
    api_url = "https://api.github.com/user/keys"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    data = {
        "title": f"Rapidbotz-{time.strftime('%Y%m%d-%H%M%S')}",
        "key": public_key
    }
    response = session.post(api_url, headers=headers, json=data, timeout=timeout)
    if response.status_code == 201:
        print("SSH key added to GitHub successfully!")
        return True  # New key added
    elif response.status_code == 422 and "key is already in use" in response.text:
        print("SSH key already exists on GitHub.")
        return False  # Key already exists
    else:
        print(f"ERROR: Failed to add SSH key to GitHub: {response.status_code} - {response.text}")
        sys.exit(1)

def wait_for_sso_authorization():
    print("\nACTION REQUIRED: Authorize the SSH key for SSO in GitHub:")
    print("1. Go to: Settings > SSH and GPG keys (https://github.com/settings/keys)")
    print("2. Find the key titled 'Rapidbotz-YYYYMMDD-HHMMSS'")
    print("3. Click 'Configure SSO' and authorize it for 'aaa-ncnu-ie' via your SSO provider.")
    print("4. Once authorized, press Enter to continue...")
    input()  # Pauses script until Enter is pressed

def log_environment(options: Options):
    logging.info("Bootstrapper version: %s", get_version())
    logging.info("OS: %s", platform.platform())
    logging.info("Python: %s", sys.version)
    logging.info("Hostname: %s", socket.gethostname())
    logging.info("Branch: %s", BRANCH)
    logging.info("Repo path: %s", LOCAL_REPO_DIR)
    logging.info("CA bundle: %s", options.ca_bundle or os.getenv("RAPIDBOTZ_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or "certifi")
    logging.info("Proxy: %s", options.proxies)

# === FUNCTIONS ===
def get_latest_remote_commit(session: requests.Session, token: str, timeout: float):
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{BRANCH}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    try:
        response = session.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()["sha"]
    except requests.exceptions.SSLError:
        raise
    except requests.RequestException as e:
        print(f"WARNING: Could not check for updates (network error: {e}). Proceeding anyway...")
        return None

def get_latest_local_commit(repo_path):
    try:
        result = subprocess.run(["git", "-C", repo_path, "rev-parse", "HEAD"], check=True, stdout=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("WARNING: Could not verify local repository state. Proceeding with update...")
        return None

def pull_latest_changes():
    try:
        before = get_latest_local_commit(LOCAL_REPO_DIR)
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "checkout", BRANCH], check=True)
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "pull", "origin", BRANCH], check=True)
        after = get_latest_local_commit(LOCAL_REPO_DIR)
        print("Repository successfully updated to the latest version.")
        return before != after
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to update repository: {e}")
        sys.exit(1)

def setup_git_credentials(github_email: str):
    try:
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "config", "user.email", github_email], check=True)
        print("Git credentials configured.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Could not configure Git credentials: {e}")

def run_powershell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )

def find_agent_pids(agent_jar: Path) -> list[int]:
    command = (
        "Get-CimInstance Win32_Process "
        "-Filter \"Name='java.exe'\" | "
        "Where-Object { $_.CommandLine -like '*botzautomation-agent*' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    result = run_powershell(command)
    pids = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids

def is_pid_running(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in result.stdout

def terminate_existing_agent(agent_jar: Path):
    pids = find_agent_pids(agent_jar)
    if not pids:
        logging.info("No existing agent process found.")
        return False
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        logging.info("Terminated existing agent process (PID: %s).", pid)
    time.sleep(1)
    return True

def launch_agent(agent_jar: Path, secret: str):
    print("Launching agent with provided secret...")
    process = subprocess.Popen(["java", "-jar", str(agent_jar)], stdin=subprocess.PIPE, text=True)
    if process.stdin:
        process.stdin.write(secret + "\n")
        process.stdin.flush()
        process.stdin.close()
    print("Agent launched successfully! It’s now running in the background.")
    print("You can close this window or press Ctrl+C in another terminal to stop it.")

def run_bootstrapper():
    args = parse_args()
    _proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
    http_options = Options(ca_bundle=args.ca_bundle, proxies=_proxies, insecure=args.insecure)
    session = build_session(http_options)

    configure_logging()
    ensure_single_instance()
    write_status("starting", "bootstrapper started")
    log_environment(http_options)

    if args.diagnose:
        logging.info("Diagnostics mode: no changes will be made.")
        repo_path = Path(LOCAL_REPO_DIR)
        agent_jar = repo_path / "agent" / "botzautomation-agent-mobilitas-all-1.0.1.jar"
        logging.info("Repo exists: %s", repo_path.exists())
        logging.info("Agent jar exists: %s", agent_jar.exists())
        logging.info("Agent PIDs: %s", find_agent_pids(agent_jar))
        write_status("diagnose", "diagnostics complete")
        release_lock()
        return 0

    # === LOAD CREDENTIALS ===
    github_token = get_credential(
        "GITHUB_PAT",
        "Please enter your GitHub Personal Access Token (needs 'repo' and 'write:public_key' scopes).",
    )
    github_email = get_credential("GITHUB_EMAIL", "Please enter your GitHub Email.")
    rapidbotz_secret = get_credential("RAPIDBOTZ_SECRET", "Please enter your Rapidbotz Secret.")

    # Generate and upload SSH key if needed
    new_key_generated = generate_ssh_key(github_email)
    new_key_added = add_ssh_key_to_github(github_token, SSH_KEY.with_suffix(".pub"), session, http_options.timeout)
    if new_key_generated or new_key_added:
        wait_for_sso_authorization()

    # === CLONE OR PULL ===
    repo_path = Path(LOCAL_REPO_DIR)
    repo_updated = False

    if not repo_path.exists():
        print(f"First-time setup: Cloning {GITHUB_REPO} into {LOCAL_REPO_DIR}...")
        try:
            subprocess.run(["git", "clone", "--branch", BRANCH, CLONE_URL, LOCAL_REPO_DIR], check=True)
            setup_git_credentials(github_email)
            print("Repository cloned successfully.")
            repo_updated = True
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to clone repository: {e}")
            print("Ensure your SSH key is authorized for SSO with 'aaa-ncnu-ie' in GitHub settings.")
            write_status("error", "clone failed", {"error": str(e)})
            release_lock()
            sys.exit(1)
    else:
        print(f"Found existing repository at {LOCAL_REPO_DIR}. Checking for updates...")
        remote_commit = get_latest_remote_commit(session, github_token, http_options.timeout)
        local_commit = get_latest_local_commit(LOCAL_REPO_DIR)
        if remote_commit and local_commit and remote_commit == local_commit:
            print("Repository is already up to date.")
        else:
            print("Fetching the latest updates...")
            repo_updated = pull_latest_changes()

    # === LAUNCH THE AGENT ===
    print("Starting Rapidbotz agent...")
    agent_jar = repo_path / "agent" / "botzautomation-agent-mobilitas-all-1.0.1.jar"

    if agent_jar.exists():
        agent_running = bool(find_agent_pids(agent_jar))
        should_restart = args.force_restart or repo_updated or not agent_running
        if should_restart:
            terminate_existing_agent(agent_jar)
            lock_file = Path("C:/cfg-mobilitas/BotzAgent/db/BotzAgent.lock.db")
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    print("Removed stale database lock file.")
                except Exception as e:
                    print(f"WARNING: Could not remove lock file: {e}")
            try:
                launch_agent(agent_jar, rapidbotz_secret)
            except Exception as e:
                print(f"ERROR: Failed to launch agent: {e}")
                write_status("error", "launch failed", {"error": str(e)})
                release_lock()
                sys.exit(1)
        else:
            logging.info("Agent already running and no updates detected; skipping restart.")
    else:
        print(f"ERROR: Agent file not found at {agent_jar}. Please contact IT support.")
        write_status("error", "agent jar missing", {"agent_jar": str(agent_jar)})
        release_lock()
        sys.exit(1)

    time.sleep(2)
    write_status("success", "bootstrap complete", {"repo_updated": repo_updated})
    release_lock()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(run_bootstrapper())
    finally:
        release_lock()
