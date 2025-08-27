Rapidbotz Bootstrapper Launcher  
Version 1.0 - For QA Team  
Updated: April 3, 2025


Overview
--------
This tool automatically sets up and runs the Rapidbotz agent on your Windows machine.
It uses a self-contained Python environment, so you don’t need to install Python or worry about system settings.
It installs dependencies, updates the local agent repo, and launches the agent with one click.

Requirements
------------
Before running, ensure you have:
1. **Git** – [Download from git-scm.com](https://git-scm.com)
2. **Java (JDK or JRE)** – [Download from java.com](https://www.java.com)

You do *not* need to install Python — it comes bundled and self-extracts.

Also have these credentials ready:
- ✅ Your GitHub Personal Access Token (PAT)
- ✅ Your GitHub Email
- ✅ Your Rapidbotz Secret (found in Rapidbotz under: Settings > Automation > Connect to Agent)

Installation
------------
1. Unzip the `rapidbotz-bootstrapper` package to a local folder (e.g., `C:\Rapidbotz`).
2. Double-click `run_bootstrapper.bat`.

The launcher mirrors all output to the console and saves a timestamped log (`bootstrapper-YYYYMMDD-HHMMSS.log`) in the same folder for troubleshooting.

The first time you run it, it will:
- Extract embedded Python
- Install pip (automatically)
- Install required dependencies (`requests`, `keyring`, etc.)
- Clone the Rapidbotz agent repo
- Launch the RapidBotz agent and uses your stored secret code

First-Time Setup
----------------
The first time you run `run_bootstrapper.bat`, it will:
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
- Double-click `run_bootstrapper.bat` anytime to update the repository and restart the agent.
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

### Corporate TLS / Netskope: trusting the inspected chain
If your corporate network performs TLS inspection (e.g., Netskope), Python’s default CA bundle (from `certifi`) will not trust
the injected corporate root. You have three secure ways to supply the correct CA to the tool:

**Option A: Use the standard Requests env var (recommended, per-user)**

1. Obtain the approved corporate CA bundle (PEM) from IT/SecOps. **Do not commit it to this repo.**
2. Save it locally, e.g.:
   ```
   C:\certs\csaa_netskope_combined.pem
   ```
3. Set the environment variable:
   - **PowerShell (current session):**
     ```powershell
     $Env:REQUESTS_CA_BUNDLE = 'C:\certs\csaa_netskope_combined.pem'
     ```
   - **CMD (persist for future sessions):**
     ```cmd
     setx REQUESTS_CA_BUNDLE "C:\certs\csaa_netskope_combined.pem"
     ```
4. Run the bootstrapper normally. `requests` will automatically use this bundle.

**Option B: Tool-specific flag/env**

- CLI flag:
  ```cmd
  python rapidbotz_bootstrapper.py --ca-bundle C:\certs\csaa_netskope_combined.pem
  ```
- Or env var:
  ```cmd
  setx RAPIDBOTZ_CA_BUNDLE "C:\certs\csaa_netskope_combined.pem"
  ```
This takes precedence over `REQUESTS_CA_BUNDLE`.

**Option C: Temporary escape hatch**

```cmd
python rapidbotz_bootstrapper.py --insecure
```
This disables certificate verification. Use **only** to confirm root cause locally. Do **not** use in CI/CD or production.

#### Verifying your setup
Run:
```cmd
python diagnose_ssl.py
```
This prints:
- Effective CA bundle (which of: `--ca-bundle`, `RAPIDBOTZ_CA_BUNDLE`, `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`, or `certifi`)
- Proxies (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`)
- Python/OpenSSL/requests versions
- A certificate chain summary for `https://api.github.com` and whether TLS inspection is likely

#### Team rollout guidance
- **Do not share** the PEM externally or commit it. Store locally per user.
- Prefer an **internal distribution page** (Confluence/SharePoint) or IT portal where teammates can download the approved `csaa_netskope_combined.pem` and follow the steps above.
- If the corporate CA rotates, update the internal distribution and notify users to refresh their local file.

### Proxies
The tool respects `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY`. You can also pass `--proxy`.

### Ignore files
Add these patterns to keep local certs out of source control:
```
certs/
*.pem
*.crt
```

## Common Errors

- `SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate in certificate chain`
  - Usually indicates the corporate root CA isn’t trusted. Follow the steps above.
  - If you must unblock quickly for local testing, use `--insecure` (temporary only).

Decision tree:
1) Run python diagnose_ssl.py
2) If it reports “LIKELY TLS inspection”, configure Option A or B above.
3) Re-run your command.
4) Only if still blocked: verify proxy settings, then open an internal ticket with the diagnose output attached.

-- **"Python/Git/Java not found"**: Install the missing tool (see Requirements) and rerun.
-- **"Failed to clone repository"**:
   - Check your internet connection.
   - Ensure the SSH key is authorized (Settings > SSH and GPG keys > Configure SSO).
   - Contact IT if the error persists.
-- **"Agent file not found"**: The repository might not have cloned correctly—see above.
-- **"Database in use"**: The script should fix this automatically; if not, delete `C:/cfg-mobilitas/BotzAgent/db/BotzAgent.lock.db` and retry.
-- **Still stuck?**: Take a screenshot of the error and email IT.
