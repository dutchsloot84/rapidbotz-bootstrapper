Rapidbotz Bootstrapper Launcher
Version 1.0 - For QA Team
Updated: March 31, 2025

Overview
--------
This tool sets up and runs the Rapidbotz agent on your Windows machine. It handles everything automatically—installing dependencies, cloning the Rapidbotz repository, and launching the agent. The first time you run it, you’ll need to authorize a security key in GitHub, but after that, it’s smooth sailing!

Requirements
------------
Before running, ensure you have:
1. Python (3.9 or later) - Download from python.org (check "Add Python to PATH" during install).
2. Git - Download from git-scm.com.
3. Java (JDK or JRE) - Download from java.com.
4. Your GitHub Personal Access Token (PAT), GitHub Email, and Rapidbotz Secret - Contact IT if you don’t have these.

Installation
------------
1. Unzip the Rapidbotz Bootstrapper package to a folder (e.g., C:\Rapidbotz).
2. Double-click `bootstrapper.bat` to start.

First-Time Setup
----------------
The first time you run `bootstrapper.bat`, it will:
1. Check for Python, Git, and Java (install them if missing—see Requirements).
2. Ask for your credentials:
   - GitHub PAT (needs 'repo' and 'write:public_key' scopes).
   - GitHub Email.
   - Rapidbotz Secret.
   Enter each when prompted (your input won’t show for security).
3. Generate and add an SSH key to GitHub, then pause with:

SSH key added to GitHub successfully!
ACTION REQUIRED: Authorize the SSH key for SSO in GitHub:

1. Go to: Settings > SSH and GPG keys (https://github.com/settings/keys)
2. Find the key titled 'Rapidbotz-YYYYMMDD-HHMMSS'
3. Click 'Configure SSO' and authorize it for 'aaa-ncnu-ie' via your SSO provider.
4. Once authorized, press Enter to continue...

- Open the link in a browser.
- Log in to GitHub, find the key, click "Configure SSO," and follow your SSO login (e.g., Okta).
- After authorizing, return to the script and press Enter.
4. Clone the Rapidbotz repository and launch the agent.

Running the Agent
-----------------
After the first setup:
- Double-click `bootstrapper.bat` anytime to update the repository and restart the agent.
- It uses your saved credentials and SSH key—no need to re-enter anything unless IT changes your details.

What It Does
------------
- Checks for updates to the Rapidbotz repository.
- Kills any old agent process to avoid conflicts.
- Starts the agent in the background (you’ll see logs like `[EL Info]` if it’s working).

Stopping the Agent
------------------
- Open Task Manager (Ctrl+Shift+Esc), find `java.exe`, and end it.
- Or, open a Command Prompt in the script folder, press Ctrl+C, and close the window.

Troubleshooting
---------------
- **"Python/Git/Java not found"**: Install the missing tool (see Requirements) and rerun.
- **"Failed to clone repository"**: 
   - Check your internet connection.
   - Ensure the SSH key is authorized (Settings > SSH and GPG keys > Configure SSO).
   - Contact IT if the error persists.
- **"Agent file not found"**: The repository might not have cloned correctly—see above.
- **"Database in use"**: The script should fix this automatically; if not, delete `C:/cfg-mobilitas/BotzAgent/db/BotzAgent.lock.db` and retry.
- **Still stuck?**: Take a screenshot of the error and email IT.
