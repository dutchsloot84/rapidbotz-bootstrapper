import os
import subprocess
import sys
import json
import argparse
from pathlib import Path
import requests
import time
import keyring
import getpass
sys.path.insert(0, os.path.dirname(__file__))  # <-- add this line

from rbz.http import Options, build_session


from rbz.http import Options, build_session

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

config = load_config()
BRANCH = config["repo_branch"]
LOCAL_REPO_DIR = config["local_repo_path"]

# === CONSTANTS ===
GITHUB_REPO = "aaa-ncnu-ie/mobilitas-rapidbotz-local-agent"
CLONE_URL = "git@github.com:aaa-ncnu-ie/mobilitas-rapidbotz-local-agent.git"
SERVICE_NAME = "Rapidbotz"
SSH_DIR = Path.home() / ".ssh"
SSH_KEY = SSH_DIR / "id_ed25519"

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
    return parser.parse_args()


args = parse_args()
_proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
HTTP_OPTIONS = Options(ca_bundle=args.ca_bundle, proxies=_proxies, insecure=args.insecure)
SESSION = build_session(HTTP_OPTIONS)

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

def add_ssh_key_to_github(token, public_key_path, session: requests.Session):
    with open(public_key_path, "r") as f:
        public_key = f.read().strip()
    api_url = "https://api.github.com/user/keys"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    data = {
        "title": f"Rapidbotz-{time.strftime('%Y%m%d-%H%M%S')}",
        "key": public_key
    }
    response = session.post(api_url, headers=headers, json=data, timeout=HTTP_OPTIONS.timeout)
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

# === LOAD CREDENTIALS ===
GITHUB_TOKEN = get_credential("GITHUB_PAT", "Please enter your GitHub Personal Access Token (needs 'repo' and 'write:public_key' scopes).")
GITHUB_EMAIL = get_credential("GITHUB_EMAIL", "Please enter your GitHub Email.")
RAPIDBOTZ_SECRET = get_credential("RAPIDBOTZ_SECRET", "Please enter your Rapidbotz Secret.")

# Generate and upload SSH key if needed
new_key_generated = generate_ssh_key(GITHUB_EMAIL)
new_key_added = add_ssh_key_to_github(GITHUB_TOKEN, SSH_KEY.with_suffix(".pub"), SESSION)
if new_key_generated or new_key_added:
    wait_for_sso_authorization()

# === FUNCTIONS ===
def get_latest_remote_commit(session: requests.Session):
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{BRANCH}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    try:
        response = session.get(api_url, headers=headers, timeout=HTTP_OPTIONS.timeout)
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
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "checkout", BRANCH], check=True)
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "pull", "origin", BRANCH], check=True)
        print("Repository successfully updated to the latest version.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to update repository: {e}")
        sys.exit(1)

def setup_git_credentials():
    try:
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "config", "user.email", GITHUB_EMAIL], check=True)
        print("Git credentials configured.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Could not configure Git credentials: {e}")

# === CLONE OR PULL ===
repo_path = Path(LOCAL_REPO_DIR)

if not repo_path.exists():
    print(f"First-time setup: Cloning {GITHUB_REPO} into {LOCAL_REPO_DIR}...")
    try:
        subprocess.run(["git", "clone", "--branch", BRANCH, CLONE_URL, LOCAL_REPO_DIR], check=True)
        setup_git_credentials()
        print("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to clone repository: {e}")
        print("Ensure your SSH key is authorized for SSO with 'aaa-ncnu-ie' in GitHub settings.")
        sys.exit(1)
else:
    print(f"Found existing repository at {LOCAL_REPO_DIR}. Checking for updates...")
    remote_commit = get_latest_remote_commit(SESSION)
    local_commit = get_latest_local_commit(LOCAL_REPO_DIR)
    if remote_commit and local_commit and remote_commit == local_commit:
        print("Repository is already up to date.")
    else:
        print("Fetching the latest updates...")
        pull_latest_changes()

# === LAUNCH THE AGENT ===
print("Starting Rapidbotz agent...")
agent_jar = repo_path / "agent" / "botzautomation-agent-mobilitas-all-1.0.1.jar"

def terminate_existing_agent():
    try:
        result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "CSV"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if str(agent_jar) in line:
                pid = line.split(",")[1].strip('"')
                subprocess.run(["taskkill", "/PID", pid, "/F"], check=True)
                print(f"Terminated existing agent process (PID: {pid}).")
                time.sleep(1)
                return True
        return False
    except subprocess.CalledProcessError:
        print("No existing agent process found.")
        return False

if agent_jar.exists():
    terminate_existing_agent()
    lock_file = Path("C:/cfg-mobilitas/BotzAgent/db/BotzAgent.lock.db")
    if lock_file.exists():
        try:
            lock_file.unlink()
            print("Removed stale database lock file.")
        except Exception as e:
            print(f"WARNING: Could not remove lock file: {e}")
    try:
        print("Launching agent with provided secret...")
        process = subprocess.Popen(["java", "-jar", str(agent_jar)], stdin=subprocess.PIPE, text=True)
        process.communicate(RAPIDBOTZ_SECRET + "\n")
        print("Agent launched successfully! It’s now running in the background.")
        print("You can close this window or press Ctrl+C in another terminal to stop it.")
    except Exception as e:
        print(f"ERROR: Failed to launch agent: {e}")
        sys.exit(1)
else:
    print(f"ERROR: Agent file not found at {agent_jar}. Please contact IT support.")
    sys.exit(1)

time.sleep(2)