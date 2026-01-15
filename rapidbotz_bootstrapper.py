import argparse
import getpass
import json
import logging
import logging.handlers
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import keyring
import requests

sys.path.insert(0, os.path.dirname(__file__))  # <-- add this line

from rbz.http import Options, build_session

RUN_ID = "unknown"

# === LOAD CONFIG ===
DEFAULT_CONFIG = {
    "repo_branch": "main",
    "local_repo_path": "C:/Rapidbotz/mobilitas-rapidbotz-local-agent",
    "circuit_breaker_enabled": True,
    "circuit_breaker_window_minutes": 15,
    "circuit_breaker_failure_threshold": 5,
    "log_max_bytes": 5_000_000,
    "log_backup_count": 5,
    "log_dir": "%ProgramData%/RapidBotz/logs",
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
    parser.add_argument(
        "--reset-circuit-breaker",
        action="store_true",
        help="Reset circuit breaker state and continue.",
    )
    parser.add_argument(
        "--bundle-logs",
        action="store_true",
        help="Create a support bundle zip with logs and status artifacts.",
    )
    return parser.parse_args()


def resolve_log_dir(config: dict) -> Path:
    raw = config.get("log_dir") or ""
    expanded = os.path.expandvars(raw) if raw else ""
    candidate = Path(expanded) if expanded else SCRIPT_DIR / "logs"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        test_path = candidate / ".write_test"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink()
        return candidate
    except Exception:
        fallback = SCRIPT_DIR / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def configure_logging(log_level=logging.INFO):
    log_format = "%(asctime)sZ %(levelname)s [run_id=%(run_id)s] %(message)s"
    log_dir = resolve_log_dir(CONFIG)
    log_path = log_dir / "bootstrapper.log"
    rotating = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=CONFIG["log_max_bytes"],
        backupCount=CONFIG["log_backup_count"],
        encoding="utf-8",
    )

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.run_id = RUN_ID
        return record

    logging.setLogRecordFactory(record_factory)
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), rotating],
    )
    return log_dir, log_path


def build_logger(run_id: str):
    base_logger = logging.getLogger("bootstrapper")
    return logging.LoggerAdapter(base_logger, {"run_id": run_id})


def get_version():
    try:
        result = subprocess.run(
            ["git", "-C", str(SCRIPT_DIR), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def load_status() -> dict:
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_status(payload: dict):
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def update_status(status: dict, updates: dict):
    status.update(updates)
    write_status(status)
    return status


def ensure_single_instance(logger, status: dict):
    if LOCK_FILE.exists():
        try:
            existing = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = existing.get("pid")
            if pid and is_pid_running(pid):
                logger.error("Another bootstrapper instance is running (pid=%s).", pid)
                status.update(
                    {
                        "status": "blocked",
                        "last_error_summary": "Another bootstrapper instance is running",
                        "last_error_detail": f"pid={pid}",
                    }
                )
                write_status(status)
                sys.exit(2)
        except Exception as exc:
            logger.warning("Failed to read existing lock file; continuing with new lock. %s", exc)
    lock_data = {
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    LOCK_FILE.write_text(json.dumps(lock_data, indent=2), encoding="utf-8")


def release_lock(logger):
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception as exc:
            logger.warning("Failed to remove lock file: %s", exc)


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
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"SSH key generated at {SSH_KEY}")
        return True  # Indicate a new key was generated
    return False  # No new key generated


def add_ssh_key_to_github(token, public_key_path, session: requests.Session, timeout: float):
    with open(public_key_path, "r") as f:
        public_key = f.read().strip()
    api_url = "https://api.github.com/user/keys"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    data = {"title": f"Rapidbotz-{time.strftime('%Y%m%d-%H%M%S')}", "key": public_key}
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


def sanitize_text(text: str, secrets: list[str]) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "***")
    return sanitized


def run_command(command: list[str], logger, secrets: list[str], check: bool = False):
    sanitized_command = [sanitize_text(part, secrets) for part in command]
    logger.info("Command: %s", " ".join(sanitized_command))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = sanitize_text(result.stdout[-2000:], secrets)
    stderr = sanitize_text(result.stderr[-2000:], secrets)
    if stdout:
        logger.info("Command stdout (tail): %s", stdout)
    if stderr:
        logger.warning("Command stderr (tail): %s", stderr)
    if check and result.returncode != 0:
        logger.error("Command failed with exit code %s", result.returncode)
    return result


def get_username():
    try:
        return os.getlogin()
    except Exception:
        return getpass.getuser()


def log_environment(logger, options: Options, run_id: str, log_dir: Path, args: list[str]):
    logger.info("Run ID: %s", run_id)
    logger.info("Bootstrapper version: %s", get_version())
    logger.info("Script path: %s", SCRIPT_DIR)
    logger.info("Working directory: %s", os.getcwd())
    logger.info("Command line: %s", " ".join(args))
    logger.info("Hostname: %s", socket.gethostname())
    logger.info("Username: %s", get_username())
    logger.info("OS: %s", platform.platform())
    logger.info("Python: %s", sys.version)
    try:
        java_result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
        java_output = (java_result.stderr or java_result.stdout).strip()
        if java_output:
            logger.info("Java version: %s", java_output.splitlines()[0])
    except Exception as exc:
        logger.warning("Java version check failed: %s", exc)
    logger.info("Repo path: %s", LOCAL_REPO_DIR)
    logger.info("Branch: %s", BRANCH)
    logger.info("Config path: %s", Path("config.json").resolve())
    logger.info(
        "Config values: %s",
        json.dumps(
            {
                "repo_branch": BRANCH,
                "local_repo_path": LOCAL_REPO_DIR,
                "circuit_breaker_enabled": CONFIG["circuit_breaker_enabled"],
                "circuit_breaker_window_minutes": CONFIG["circuit_breaker_window_minutes"],
                "circuit_breaker_failure_threshold": CONFIG["circuit_breaker_failure_threshold"],
                "log_dir": CONFIG["log_dir"],
                "log_max_bytes": CONFIG["log_max_bytes"],
                "log_backup_count": CONFIG["log_backup_count"],
            }
        ),
    )
    logger.info("Log dir: %s", log_dir)
    logger.info(
        "CA bundle: %s",
        options.ca_bundle
        or os.getenv("RAPIDBOTZ_CA_BUNDLE")
        or os.getenv("REQUESTS_CA_BUNDLE")
        or os.getenv("SSL_CERT_FILE")
        or "certifi",
    )
    logger.info("Proxy: %s", options.proxies)


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
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("WARNING: Could not verify local repository state. Proceeding with update...")
        return None


def pull_latest_changes(logger, secrets: list[str]):
    before = get_latest_local_commit(LOCAL_REPO_DIR)
    result = run_command(["git", "-C", LOCAL_REPO_DIR, "checkout", BRANCH], logger, secrets)
    if result.returncode != 0:
        return False, "checkout_failed", result
    result = run_command(["git", "-C", LOCAL_REPO_DIR, "pull", "origin", BRANCH], logger, secrets)
    if result.returncode != 0:
        return False, "pull_failed", result
    after = get_latest_local_commit(LOCAL_REPO_DIR)
    logger.info("Repository successfully updated to the latest version.")
    return before != after, "pull_complete", result


def setup_git_credentials(github_email: str):
    try:
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "config", "user.email", github_email], check=True)
        print("Git credentials configured.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Could not configure Git credentials: {e}")


def find_agent_pids(logger, secrets: list[str]) -> tuple[list[int], str | None]:
    command = (
        "Get-CimInstance Win32_Process "
        "-Filter \"Name='java.exe'\" | "
        "Where-Object { $_.CommandLine -like '*botzautomation-agent*' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    result = run_command(["powershell", "-NoProfile", "-Command", command], logger, secrets)
    pids = []
    if result.returncode != 0:
        return [], f"CIM query failed: {result.stderr.strip()}"
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids, None


def is_pid_running(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in result.stdout


def terminate_existing_agent(logger, secrets: list[str]):
    pids, detection_error = find_agent_pids(logger, secrets)
    if detection_error:
        logger.warning("Agent detection failed; not terminating. Error: %s", detection_error)
        return False, detection_error
    if not pids:
        logger.info("No existing agent process found.")
        return False, None
    for pid in pids:
        run_command(["taskkill", "/PID", str(pid), "/F"], logger, secrets)
        logger.info("Terminated existing agent process (PID: %s).", pid)
    time.sleep(1)
    return True, None


def launch_agent(agent_jar: Path, secret: str):
    print("Launching agent with provided secret...")
    process = subprocess.Popen(["java", "-jar", str(agent_jar)], stdin=subprocess.PIPE, text=True)
    if process.stdin:
        process.stdin.write(secret + "\n")
        process.stdin.flush()
        process.stdin.close()
    print("Agent launched successfully! It’s now running in the background.")
    print("You can close this window or press Ctrl+C in another terminal to stop it.")


def phase(logger, status: dict, name: str, action):
    start = time.time()
    logger.info("Phase start: %s", name)
    try:
        result = action()
        duration = int((time.time() - start) * 1000)
        if result is False:
            logger.error("Phase failed: %s (%sms)", name, duration)
            return result, False, duration
        logger.info("Phase complete: %s (%sms)", name, duration)
        update_status(status, {"last_phase_completed": name})
        return result, True, duration
    except Exception as exc:
        duration = int((time.time() - start) * 1000)
        logger.error("Phase failed: %s (%sms) error=%s", name, duration, exc)
        return exc, False, duration


def evaluate_circuit_breaker(status: dict, logger, reset: bool):
    now = datetime.now(timezone.utc)
    window_minutes = CONFIG["circuit_breaker_window_minutes"]
    threshold = CONFIG["circuit_breaker_failure_threshold"]
    if not CONFIG.get("circuit_breaker_enabled", True):
        status["circuit_breaker_tripped"] = False
        return status
    if reset:
        status.update(
            {
                "failure_window_start": None,
                "failure_window_count": 0,
                "consecutive_failures": 0,
                "circuit_breaker_tripped": False,
            }
        )
        logger.info("Circuit breaker reset requested.")
        return status
    failure_window_start = status.get("failure_window_start")
    failure_window_count = status.get("failure_window_count", 0)
    if failure_window_start:
        try:
            start_dt = datetime.fromisoformat(failure_window_start)
            if now - start_dt > timedelta(minutes=window_minutes):
                failure_window_start = None
                failure_window_count = 0
        except ValueError:
            failure_window_start = None
            failure_window_count = 0
    status["failure_window_start"] = failure_window_start
    status["failure_window_count"] = failure_window_count
    status["circuit_breaker_tripped"] = bool(status.get("circuit_breaker_tripped", False))
    if failure_window_start and failure_window_count >= threshold:
        status["circuit_breaker_tripped"] = True
        logger.error(
            "Circuit breaker tripped: %s failures within %s minutes.",
            failure_window_count,
            window_minutes,
        )
    return status


def record_failure(status: dict, logger):
    now = datetime.now(timezone.utc)
    window_minutes = CONFIG["circuit_breaker_window_minutes"]
    threshold = CONFIG["circuit_breaker_failure_threshold"]
    failure_window_start = status.get("failure_window_start")
    if failure_window_start:
        start_dt = datetime.fromisoformat(failure_window_start)
        if now - start_dt > timedelta(minutes=window_minutes):
            failure_window_start = None
            status["failure_window_count"] = 0
    if not failure_window_start:
        status["failure_window_start"] = now.isoformat()
        status["failure_window_count"] = 1
    else:
        status["failure_window_count"] = status.get("failure_window_count", 0) + 1
    status["consecutive_failures"] = status.get("consecutive_failures", 0) + 1
    if status["failure_window_count"] >= threshold:
        status["circuit_breaker_tripped"] = True
        logger.error("Circuit breaker tripped after failure count threshold.")
    status["last_failure_time"] = now.isoformat()
    return status


def record_success(status: dict):
    now = datetime.now(timezone.utc)
    status["last_success_time"] = now.isoformat()
    status["consecutive_failures"] = 0
    return status


def create_support_bundle(log_dir: Path, run_id: str, status_path: Path, logger):
    hostname = socket.gethostname()
    bundle_name = f"bootstrapper-support-bundle-{hostname}-{run_id}.zip"
    bundle_path = log_dir / bundle_name
    sanitized_config_path = log_dir / f"config-{run_id}.json"
    sanitized_config_path.write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in log_dir.glob("bootstrapper.log*"):
            bundle.write(path, arcname=path.name)
        if status_path.exists():
            bundle.write(status_path, arcname=status_path.name)
        if sanitized_config_path.exists():
            bundle.write(sanitized_config_path, arcname="config.json")
        if VERSION_FILE.exists():
            bundle.write(VERSION_FILE, arcname=VERSION_FILE.name)
        diagnose_path = log_dir / f"diagnose-{run_id}.txt"
        if diagnose_path.exists():
            bundle.write(diagnose_path, arcname=diagnose_path.name)
    logger.info("Support bundle created at %s", bundle_path)
    return bundle_path


def maybe_bundle_logs(args, log_dir: Path, run_id: str, logger):
    if args.bundle_logs:
        create_support_bundle(log_dir, run_id, STATUS_FILE, logger)


def summarize_run(status: dict, logger, log_path: Path):
    summary_lines = [
        "---- Bootstrapper Summary ----",
        f"run_id: {status.get('run_id')}",
        f"start: {status.get('last_start_time')}",
        f"end: {status.get('last_end_time')}",
        f"duration_ms: {status.get('duration_ms')}",
        f"exit_code: {status.get('exit_code')}",
        f"repo_updated: {status.get('repo_updated')} ({status.get('git_output_summary')})",
        f"agent_detected: {status.get('agent_detected')} pid={status.get('agent_pid')}",
        f"detection_error: {status.get('detection_error')}",
        f"decision: {status.get('decision')}",
        f"actions_taken: {status.get('actions_taken')}",
        f"last_error_summary: {status.get('last_error_summary')}",
        f"log_path: {log_path}",
        f"status_path: {STATUS_FILE}",
        "-------------------------------",
    ]
    summary_text = "\n".join(summary_lines)
    logger.info(summary_text)
    status["summary_text"] = summary_text
    return status


def set_duration(status: dict):
    try:
        start = datetime.fromisoformat(status["last_start_time"])
        end = datetime.fromisoformat(status["last_end_time"])
        status["duration_ms"] = int((end - start).total_seconds() * 1000)
    except Exception:
        status["duration_ms"] = None
    return status


def dependency_checks(logger, secrets: list[str]):
    checks = {}
    checks["python"] = run_command([sys.executable, "--version"], logger, secrets).returncode == 0
    checks["git"] = run_command(["git", "--version"], logger, secrets).returncode == 0
    checks["java"] = run_command(["java", "-version"], logger, secrets).returncode == 0
    return checks


def network_checks(logger):
    try:
        socket.gethostbyname("api.github.com")
        logger.info("Network check: DNS resolution ok for api.github.com")
        return True
    except Exception as exc:
        logger.warning("Network check failed: %s", exc)
        return False


def validate_config():
    errors = []
    if not BRANCH:
        errors.append("repo_branch is empty")
    if not LOCAL_REPO_DIR:
        errors.append("local_repo_path is empty")
    if CONFIG.get("circuit_breaker_enabled") not in (True, False):
        errors.append("circuit_breaker_enabled must be true or false")
    if CONFIG["circuit_breaker_window_minutes"] <= 0:
        errors.append("circuit_breaker_window_minutes must be > 0")
    if CONFIG["circuit_breaker_failure_threshold"] <= 0:
        errors.append("circuit_breaker_failure_threshold must be > 0")
    return errors


def run_bootstrapper():
    global RUN_ID
    args = parse_args()
    _proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
    http_options = Options(ca_bundle=args.ca_bundle, proxies=_proxies, insecure=args.insecure)
    session = build_session(http_options)

    RUN_ID = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    log_dir, log_path = configure_logging()
    logger = build_logger(RUN_ID)

    status = load_status()
    status.update(
        {
            "run_id": RUN_ID,
            "last_start_time": datetime.now(timezone.utc).isoformat(),
            "version": get_version(),
            "hostname": socket.gethostname(),
            "status": "starting",
            "actions_taken": [],
            "last_exit_code": status.get("last_exit_code", 0),
            "exit_code": None,
            "failure_window_start": status.get("failure_window_start"),
            "failure_window_count": status.get("failure_window_count", 0),
            "consecutive_failures": status.get("consecutive_failures", 0),
            "circuit_breaker_tripped": status.get("circuit_breaker_tripped", False),
        }
    )
    write_status(status)
    ensure_single_instance(logger, status)
    log_environment(logger, http_options, RUN_ID, log_dir, sys.argv)

    phase(logger, status, "load_config", lambda: CONFIG)
    config_errors = validate_config()
    if config_errors:
        status.update(
            {
                "status": "error",
                "last_error_summary": "Invalid configuration",
                "last_error_detail": "; ".join(config_errors),
                "last_end_time": datetime.now(timezone.utc).isoformat(),
                "exit_code": 1,
                "last_exit_code": 1,
            }
        )
        status = record_failure(status, logger)
        status = set_duration(status)
        status = summarize_run(status, logger, log_path)
        write_status(status)
        maybe_bundle_logs(args, log_dir, RUN_ID, logger)
        release_lock(logger)
        return 1
    phase(logger, status, "validate_config", lambda: True)

    status = evaluate_circuit_breaker(status, logger, args.reset_circuit_breaker)
    write_status(status)
    if args.reset_circuit_breaker:
        status["actions_taken"].append("circuit_breaker_reset")
        write_status(status)

    secrets = []

    if (
        CONFIG.get("circuit_breaker_enabled", True)
        and status.get("circuit_breaker_tripped")
        and not args.reset_circuit_breaker
        and not args.diagnose
    ):
        logger.error("Circuit breaker is tripped. Skipping all destructive actions.")
        status["actions_taken"].append("circuit_breaker_tripped")
        status["status"] = "blocked"
        status["decision"] = "CIRCUIT_BREAKER"
        status["last_end_time"] = datetime.now(timezone.utc).isoformat()
        status["exit_code"] = 2
        status["last_exit_code"] = 2
        status["last_error_summary"] = "Circuit breaker tripped"
        status["last_error_detail"] = "Failure threshold exceeded; skipping actions."
        status = set_duration(status)
        status = summarize_run(status, logger, log_path)
        write_status(status)
        maybe_bundle_logs(args, log_dir, RUN_ID, logger)
        release_lock(logger)
        return 2

    if args.diagnose:
        logger.info("Diagnostics mode: no changes will be made.")
        repo_path = Path(LOCAL_REPO_DIR)
        agent_jar = repo_path / "agent" / "botzautomation-agent-mobilitas-all-1.0.1.jar"
        pids, detection_error = find_agent_pids(logger, secrets)
        logger.info("Repo exists: %s", repo_path.exists())
        logger.info("Agent jar exists: %s", agent_jar.exists())
        logger.info("Agent PIDs: %s", pids)
        if detection_error:
            logger.warning("Agent detection error: %s", detection_error)
        diagnose_path = log_dir / f"diagnose-{RUN_ID}.txt"
        diagnose_path.write_text(
            "\n".join(
                [
                    f"run_id={RUN_ID}",
                    f"repo_exists={repo_path.exists()}",
                    f"agent_jar_exists={agent_jar.exists()}",
                    f"agent_pids={pids}",
                    f"detection_error={detection_error}",
                ]
            ),
            encoding="utf-8",
        )
        status.update(
            {
                "status": "diagnose",
                "agent_detected": bool(pids) if detection_error is None else None,
                "agent_pid": pids[0] if pids else None,
                "detection_error": detection_error,
                "last_phase_completed": "diagnose",
                "last_end_time": datetime.now(timezone.utc).isoformat(),
                "exit_code": 0,
                "last_exit_code": 0,
            }
        )
        status["actions_taken"].append("diagnose")
        status = record_success(status)
        status = set_duration(status)
        status = summarize_run(status, logger, log_path)
        write_status(status)
        maybe_bundle_logs(args, log_dir, RUN_ID, logger)
        release_lock(logger)
        return 0

    # === LOAD CREDENTIALS ===
    github_token = get_credential(
        "GITHUB_PAT",
        "Please enter your GitHub Personal Access Token (needs 'repo' and 'write:public_key' scopes).",
    )
    github_email = get_credential("GITHUB_EMAIL", "Please enter your GitHub Email.")
    rapidbotz_secret = get_credential("RAPIDBOTZ_SECRET", "Please enter your Rapidbotz Secret.")

    secrets = [github_token, rapidbotz_secret]

    # Generate and upload SSH key if needed
    new_key_generated = generate_ssh_key(github_email)
    new_key_added = add_ssh_key_to_github(github_token, SSH_KEY.with_suffix(".pub"), session, http_options.timeout)
    if new_key_generated or new_key_added:
        wait_for_sso_authorization()

    repo_path = Path(LOCAL_REPO_DIR)
    repo_updated = False
    git_output_summary = None
    actions_taken = status["actions_taken"]

    def dependency_phase():
        return dependency_checks(logger, secrets)

    dep_result, _, _ = phase(logger, status, "dependency_checks", dependency_phase)
    status["dependency_checks"] = dep_result

    phase(logger, status, "network_checks", lambda: network_checks(logger))

    # === CLONE OR PULL ===
    if not repo_path.exists():
        logger.info("First-time setup: Cloning %s into %s...", GITHUB_REPO, LOCAL_REPO_DIR)
        phase_start = time.time()
        logger.info("Phase start: git_clone")
        result = run_command(["git", "clone", "--branch", BRANCH, CLONE_URL, LOCAL_REPO_DIR], logger, secrets)
        phase_duration = int((time.time() - phase_start) * 1000)
        if result.returncode == 0:
            logger.info("Phase complete: git_clone (%sms)", phase_duration)
            update_status(status, {"last_phase_completed": "git_clone"})
        else:
            logger.error("Phase failed: git_clone (%sms)", phase_duration)
        if result.returncode != 0:
            status.update(
                {
                    "status": "error",
                    "last_error_summary": "Failed to clone repository",
                    "last_error_detail": result.stderr[-2000:],
                    "git_output_summary": "clone_failed",
                }
            )
            status = record_failure(status, logger)
            status["last_exit_code"] = 1
            status["exit_code"] = 1
            status["last_end_time"] = datetime.now(timezone.utc).isoformat()
            status = set_duration(status)
            status = summarize_run(status, logger, log_path)
            write_status(status)
            maybe_bundle_logs(args, log_dir, RUN_ID, logger)
            release_lock(logger)
            return 1
        setup_git_credentials(github_email)
        logger.info("Repository cloned successfully.")
        repo_updated = True
        git_output_summary = "clone"
        actions_taken.append("git_clone")
    else:
        logger.info("Found existing repository at %s. Checking for updates...", LOCAL_REPO_DIR)
        remote_commit = get_latest_remote_commit(session, github_token, http_options.timeout)
        local_commit = get_latest_local_commit(LOCAL_REPO_DIR)
        if remote_commit and local_commit and remote_commit == local_commit:
            logger.info("Repository is already up to date.")
            git_output_summary = "no_change"
        else:
            logger.info("Fetching the latest updates...")
            phase_start = time.time()
            logger.info("Phase start: git_pull")
            updated, summary, result = pull_latest_changes(logger, secrets)
            phase_duration = int((time.time() - phase_start) * 1000)
            if summary not in {"checkout_failed", "pull_failed"}:
                logger.info("Phase complete: git_pull (%sms)", phase_duration)
                update_status(status, {"last_phase_completed": "git_pull"})
            else:
                logger.error("Phase failed: git_pull (%sms)", phase_duration)
            if summary in {"checkout_failed", "pull_failed"}:
                status.update(
                    {
                        "status": "error",
                        "last_error_summary": f"Git {summary}",
                        "last_error_detail": result.stderr[-2000:],
                        "git_output_summary": summary,
                    }
                )
                status = record_failure(status, logger)
                status["last_exit_code"] = 1
                status["exit_code"] = 1
                status["last_end_time"] = datetime.now(timezone.utc).isoformat()
                status = set_duration(status)
                status = summarize_run(status, logger, log_path)
                write_status(status)
                maybe_bundle_logs(args, log_dir, RUN_ID, logger)
                release_lock(logger)
                return 1
            repo_updated = updated
            git_output_summary = "updated" if repo_updated else "no_change"
            actions_taken.append("git_pull")

    # === LAUNCH THE AGENT ===
    phase_start = time.time()
    logger.info("Phase start: compute_repo_updated")
    phase_duration = int((time.time() - phase_start) * 1000)
    logger.info("Phase complete: compute_repo_updated (%sms)", phase_duration)
    update_status(status, {"last_phase_completed": "compute_repo_updated"})

    logger.info("Starting Rapidbotz agent...")
    agent_jar = repo_path / "agent" / "botzautomation-agent-mobilitas-all-1.0.1.jar"

    if agent_jar.exists():
        phase_start = time.time()
        logger.info("Phase start: agent_detection")
        pids, detection_error = find_agent_pids(logger, secrets)
        phase_duration = int((time.time() - phase_start) * 1000)
        if detection_error:
            logger.error("Phase failed: agent_detection (%sms)", phase_duration)
        else:
            logger.info("Phase complete: agent_detection (%sms)", phase_duration)
            update_status(status, {"last_phase_completed": "agent_detection"})
        agent_detected = None if detection_error else bool(pids)
        status["agent_detected"] = agent_detected
        status["agent_pid"] = pids[0] if pids else None
        status["detection_error"] = detection_error
        status["detection_method"] = "wmi"
        if detection_error:
            logger.warning("Agent detection failed: %s", detection_error)
        should_restart = False
        if args.force_restart:
            should_restart = True
        elif repo_updated:
            should_restart = True
        elif agent_detected is False:
            should_restart = True

        if detection_error and not args.force_restart:
            logger.warning("Agent detection error; skipping restart without --force-restart.")
            actions_taken.append("agent_restart_skipped_detection_error")
            status["decision"] = "SKIPPED"
        elif should_restart:
            actions_taken.append("agent_restart")
            phase_start = time.time()
            logger.info("Phase start: agent_stop")
            terminate_existing_agent(logger, secrets)
            phase_duration = int((time.time() - phase_start) * 1000)
            logger.info("Phase complete: agent_stop (%sms)", phase_duration)
            update_status(status, {"last_phase_completed": "agent_stop"})
            lock_file = Path("C:/cfg-mobilitas/BotzAgent/db/BotzAgent.lock.db")
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    logger.info("Removed stale database lock file.")
                except Exception as e:
                    logger.warning("Could not remove lock file: %s", e)
            try:
                phase_start = time.time()
                logger.info("Phase start: agent_start")
                logger.info("Command: java -jar %s", agent_jar)
                launch_agent(agent_jar, rapidbotz_secret)
                phase_duration = int((time.time() - phase_start) * 1000)
                logger.info("Phase complete: agent_start (%sms)", phase_duration)
                update_status(status, {"last_phase_completed": "agent_start"})
                phase_start = time.time()
                logger.info("Phase start: post_start_verification")
                verify_pids, verify_error = find_agent_pids(logger, secrets)
                phase_duration = int((time.time() - phase_start) * 1000)
                if verify_error:
                    logger.error("Phase failed: post_start_verification (%sms)", phase_duration)
                    status["post_start_verification_error"] = verify_error
                else:
                    logger.info("Phase complete: post_start_verification (%sms)", phase_duration)
                    status["post_start_agent_pids"] = verify_pids
                    update_status(status, {"last_phase_completed": "post_start_verification"})
                status["decision"] = "RESTARTED" if pids else "STARTED"
            except Exception as e:
                logger.error("Failed to launch agent: %s", e)
                status.update(
                    {
                        "status": "error",
                        "last_error_summary": "Failed to launch agent",
                        "last_error_detail": str(e)[:2000],
                    }
                )
                status = record_failure(status, logger)
                status["exit_code"] = 1
                status["last_exit_code"] = 1
                status["last_end_time"] = datetime.now(timezone.utc).isoformat()
                status = set_duration(status)
                status = summarize_run(status, logger, log_path)
                write_status(status)
                maybe_bundle_logs(args, log_dir, RUN_ID, logger)
                release_lock(logger)
                return 1
        else:
            logger.info("Agent already running and no updates detected; skipping restart.")
            actions_taken.append("agent_restart_skipped_no_change")
            status["decision"] = "SKIPPED"
    else:
        logger.error("Agent file not found at %s. Please contact IT support.", agent_jar)
        status.update(
            {
                "status": "error",
                "last_error_summary": "Agent jar missing",
                "last_error_detail": str(agent_jar),
            }
        )
        status = record_failure(status, logger)
        status["exit_code"] = 1
        status["last_exit_code"] = 1
        status["last_end_time"] = datetime.now(timezone.utc).isoformat()
        status = set_duration(status)
        status = summarize_run(status, logger, log_path)
        write_status(status)
        maybe_bundle_logs(args, log_dir, RUN_ID, logger)
        release_lock(logger)
        return 1

    time.sleep(2)
    status.update(
        {
            "status": "success",
            "repo_updated": repo_updated,
            "git_output_summary": git_output_summary,
            "last_end_time": datetime.now(timezone.utc).isoformat(),
            "exit_code": 0,
            "last_exit_code": 0,
            "last_error_summary": None,
            "last_error_detail": None,
        }
    )
    status = record_success(status)
    status = set_duration(status)
    status = summarize_run(status, logger, log_path)
    write_status(status)
    maybe_bundle_logs(args, log_dir, RUN_ID, logger)

    release_lock(logger)
    return 0


if __name__ == "__main__":
    sys.exit(run_bootstrapper())
