# Rapidbotz Bootstrapper

A lightweight Python-based tool that pulls the latest version of the `mobilitas-rapidbotz-local-agent` repository and launches the Rapidbotz agent automatically.

Designed to help non-technical users run the Rapidbotz agent with a simple double-click, while ensuring the agent is always up to date.

---

## 🔧 Features

- ✅ Pulls from the `main` branch of the GitHub repo
- ✅ Skips re-downloading if no new updates are found
- ✅ Automatically launches the Rapidbotz agent (`agent.jar`)
- ✅ Configurable download location and branch via `config.json`
- ✅ Includes a `.bat` file for easy execution on Windows

---

## 📁 Folder Structure
/rapidbotz-bootstrapper 
- config.json # Local settings (branch and repo path) 
- rapidbotz_bootstrapper.py # Python script that manages pull + launch 
- run_bootstrapper.bat # Easy-to-use batch file for non-technical users


---

## ⚙️ Setup Instructions

### 1. ✅ Install Python (if needed)

- Recommended: Python 3.10+
- [Download Python](https://www.python.org/downloads/) or install via command line:

```cmd
curl -o python-installer.exe https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
```

---
### 2. 🔐 Set Up Your GitHub Credentials
a. Generate a Personal Access Token (PAT)

Go to GitHub PATs → Generate new token (classic)
Scopes to enable:

    repo

    read:org

After generating, authorize the token for your org (SAML SSO).

b. Set Environment Variables (Windows)
```
setx GITHUB_PAT your_token_here
setx GITHUB_EMAIL your_email@example.com
```

---
### 3. 🔑 Set Up SSH Key (if not done already)
```
ssh-keygen -t ed25519 -C "your_email@example.com"
```
- Add the .pub key to GitHub: SSH Key Settings

- Enable SSO if prompted
  
---
### 4. 🛠️ Customize the Config (Optional)

Edit config.json if you want to change the default branch or clone location:
```json
{
  "repo_branch": "main",
  "local_repo_path": "C:/Rapidbotz/mobilitas-rapidbotz-local-agent"
}
```

---
## 🚀 Running the Bootstrapper

Just double-click:
```cmd
run_bootstrapper.bat
```
This will:

1. Check for updates to the Rapidbotz agent repo
2. Pull latest changes (if any)
3. Launch the agent (agent.jar)
   
---

💡 Notes

- The script uses SSH for Git operations and HTTPS (with token) for update detection via GitHub API.
- Your SSH key and PAT must be authorized for your organization.
- Make sure Java is installed and available in your system PATH.
