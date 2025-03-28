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

#### 🔐 Prerequisite: Rapidbotz Access

Before you can use the Rapidbotz Bootstrapper, you must have access to the Rapidbotz platform.
1. Log in to:
https://botzautomation.rapidbotz.com/login

2. If you don’t have access, contact your team lead or system admin to request it.

#### 🧩 Getting Your Rapidbotz Agent Secret Code

After the script runs, the agent will launch and prompt you with:
```
Please enter secret code:
```

Follow these steps to get your code:

1. Log in to: https://botzautomation.rapidbotz.com/login

2. Go to:
    Settings > Automation Tab > BotzAgent

3. Select "Local" 

4. On your local agent row, click the plug icon 🔌 (Connect to Agent)

5. Copy the secret code that appears — it should look like this:
```
   BZ::firstname.lastnameinitial::4kqr3mcvqrc4oxehpb7gbnlv7l
```

6. Paste that code into the terminal when prompted by the agent

✅ After entering the secret, the agent will register with Rapidbotz and be ready for automation tasks.

---

### 2. 🔐 Set Up Your GitHub Credentials

You need to generate a Personal Access Token (PAT) to allow the script to check for updates in GitHub.
How to Generate a PAT:

1. Go to: https://github.com/settings/tokens
2. Select “Personal access tokens” > Tokens (classic):
  - Generate new token (classic)

3. Fill out the form:
  - Note: Rapidbotz Bootstrapper
  - Expiration: 90 days or whatever fits your company policy

4. Under Scopes, check:
  - ✅ repo (full control of private repositories)
  - ✅ read:org (to access org metadata)
5. Click Generate token and copy your token
💡 Important: Copy the token right away. You won’t see it again!
6. Select "Enable SSO" dropdown
  - Select aaa-ncnu-ie and authorize

#### Option A: Set Your Environment Variables (Windows)

Open Command Prompt and run:
```cmd
setx GITHUB_PAT your_token_here
setx GITHUB_EMAIL your_email@example.com
```
💡 You may need admin rights for this depending on system policy.

#### Option B: Define Variables Inside the .bat File

If you'd rather not set system-wide environment variables, you can define them directly inside run_bootstrapper.bat.

Open the batch file and uncomment the lines below:

```
:: set GITHUB_PAT=your_token_here
:: set GITHUB_EMAIL=your_email@example.com
```

Just remove the :: at the beginning of each line and add your actual token and email.

This approach is useful if:

- You want to avoid permanent changes

- You're sharing this with users who will run it from a flash drive or temporary folder

---
### 3. 🔑 Set Up SSH Key (for GitHub Access)
You need an SSH key so the script can securely pull from GitHub.

Generate Your SSH Key:
1. Open Command Prompt and run:
```
ssh-keygen -t ed25519 -C "your_email@example.com"
```
2. When prompted for a location, press Enter to accept the default (this saves it to C:\Users\YourName\.ssh\id_ed25519).
3. You'll then be prompted for a passphrase:
```
Enter passphrase (empty for no passphrase):
```
➤ Just press Enter to skip — no password is required for this setup.

5. You’ll see something like:
```
Your identification has been saved in C:\Users\YourName\.ssh\id_ed25519
Your public key has been saved in C:\Users\YourName\.ssh\id_ed25519.pub
```

Add Your Key to GitHub:

1. Open the file:
- Go to: C:\Users\YourName\.ssh\id_ed25519.pub
- Open it with Notepad or Notepad++
- It will look like:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM... your_email@example.com
```
2. Go to: https://github.com/settings/keys
3. Click "New SSH key"
- Title: something like Rapidbotz Agent
- Key: paste the entire contents of id_ed25519.pub
4. Click Add SSH Key
5. Select "Enable SSO" dropdown
  - Select aaa-ncnu-ie and authorize

✅ Now your machine is authorized to pull from your GitHub org via SSH.

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
