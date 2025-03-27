import os
import subprocess
import sys
import json
from pathlib import Path
import requests

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
                return {**DEFAULT_CONFIG, **user_config}
        except json.JSONDecodeError:
            print("ERROR: Invalid JSON in config.json. Using default config.")
    else:
        print("No config.json found. Using default config.")
    return DEFAULT_CONFIG

config = load_config()
BRANCH = config["repo_branch"]
LOCAL_REPO_DIR = config["local_repo_path"]

# === CONSTANTS ===
GITHUB_REPO = "aaa-ncnu-ie/mobilitas-rapidbotz-local-agent"
CLONE_URL = "git@github.com:aaa-ncnu-ie/mobilitas-rapidbotz-local-agent.git"

# === ENV VARS ===
GITHUB_TOKEN = os.getenv("GITHUB_PAT")
GITHUB_EMAIL = os.getenv("GITHUB_EMAIL")

if not GITHUB_TOKEN or not GITHUB_EMAIL:
    print("ERROR: Missing required environment variables GITHUB_PAT and/or GITHUB_EMAIL.")
    sys.exit(1)

# === FUNCTIONS ===
def get_latest_remote_commit():
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{BRANCH}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}"
    }
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()["sha"]
    except Exception as e:
        print("ERROR: Unable to fetch remote commit hash:", e)
        return None


def get_latest_local_commit(repo_path):
    try:
        result = subprocess.run(["git", "-C", repo_path, "rev-parse", "HEAD"], check=True, stdout=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("ERROR: Could not get local commit hash.")
        return None

def pull_latest_changes():
    try:
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "checkout", BRANCH], check=True)
        subprocess.run(["git", "-C", LOCAL_REPO_DIR, "pull", "origin", BRANCH], check=True)
        print("Repository updated successfully.")
    except subprocess.CalledProcessError as e:
        print("Error pulling repository:", e)
        sys.exit(1)

# === CLONE OR PULL ===
repo_path = Path(LOCAL_REPO_DIR)

if not repo_path.exists():
    print(f"Cloning {GITHUB_REPO} into {LOCAL_REPO_DIR} (branch: {BRANCH})...")
    try:
        subprocess.run(
            ["git", "clone", "--branch", BRANCH, CLONE_URL, LOCAL_REPO_DIR],
            check=True
        )
        print("Clone completed successfully.")
    except subprocess.CalledProcessError as e:
        print("Error cloning repository:", e)
        sys.exit(1)
else:
    print(f"Repository already exists at {LOCAL_REPO_DIR}. Checking for updates...")

    remote_commit = get_latest_remote_commit()
    local_commit = get_latest_local_commit(LOCAL_REPO_DIR)

    if remote_commit and local_commit:
        if remote_commit == local_commit:
            print("Repository is already up to date. No pull necessary.")
        else:
            print("New updates found. Pulling latest changes...")
            pull_latest_changes()
    else:
        print("Unable to verify update status — proceeding with pull just in case.")
        pull_latest_changes()
        
 # === LAUNCH THE AGENT ===
print("Launching Rapidbotz agent...")

agent_jar = Path(LOCAL_REPO_DIR) / "agent" / "botzautomation-agent-mobilitas-all-1.0.1.jar"

if agent_jar.exists():
    try:
        subprocess.Popen(["java", "-jar", str(agent_jar)], shell=True)
        print("Agent JAR launched successfully.")
    except Exception as e:
        print("Failed to launch agent JAR:", e)
else:
    print(f"ERROR: agent.jar not found at expected location: {agent_jar}")

