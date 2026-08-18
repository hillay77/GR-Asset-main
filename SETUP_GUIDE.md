# GR Asset Management System — Setup Guide

## What You Need
- A computer running **Windows**, **macOS**, or **Linux**
- **Python 3.10 or newer** (free download)
- That's it — no internet required after installation

---

## Step 1 — Install Python

### Windows
1. Go to https://www.python.org/downloads/
2. Click **Download Python 3.x.x**
3. Run the installer — **tick "Add Python to PATH"** before clicking Install
4. Open **Command Prompt** (search "cmd" in Start menu) and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.0`

### macOS
1. Go to https://www.python.org/downloads/
2. Download and install the `.pkg` file
3. Open **Terminal** and type:
   ```
   python3 --version
   ```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

---

## Step 2 — Copy the Project Files

Copy the `gr_ams` folder to wherever you want it, for example:
- Windows: `C:\gr_ams\`
- macOS/Linux: `/home/yourname/gr_ams/`

---

## Step 3 — Open a Terminal in the Project Folder

### Windows
1. Open **Command Prompt** or **PowerShell**
2. Navigate to the folder:
   ```
   cd C:\gr_ams
   ```

### macOS / Linux
```bash
cd /home/yourname/gr_ams
```

---

## Step 4 — Create a Virtual Environment

A virtual environment keeps the project's packages separate from your system Python.

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Your terminal prompt will change to show `(venv)` — this means it's active.

---

## Step 5 — Install Required Packages

```bash
pip install -r requirements.txt
```

This installs Flask, SQLAlchemy, Flask-Login, and other dependencies.
It only needs internet access this one time.

---

## Step 6 — Run the Application

```bash
python run.py
```

You will see:
```
  GR Asset Management System
  ─────────────────────────────
  Running at: http://127.0.0.1:5000
  Network:    http://0.0.0.0:5000
  Accounts:   admin/admin123  finance/finance123  john/user123
```

---

## Step 7 — Open in Browser

On the **same computer**, open any web browser and go to:
```
http://127.0.0.1:5000
```

### Access from Other Computers on the Same Network (LAN)
1. Find the server computer's IP address:
   - **Windows**: open Command Prompt → type `ipconfig` → look for **IPv4 Address** (e.g. `192.168.1.5`)
   - **macOS/Linux**: open Terminal → type `ifconfig` or `ip addr`
2. On any other computer/phone on the same WiFi or LAN, open a browser and go to:
   ```
   http://192.168.1.5:5000
   ```
   *(replace with your actual IP address)*

---

## Demo Login Accounts

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator — full access |
| finance | finance123 | Finance Officer — view + reports |
| john | user123 | Staff User — own assets only |
| mary | user123 | Staff User — own assets only |

**Change all passwords after first login** via Admin → Register Users → Edit.

---

## Database

The database file is created automatically at:
```
gr_ams/instance/gr_ams.db
```

This is a single **SQLite file**. To back it up, simply copy that file.

### Database Schema Summary
| Table | Description |
|-------|-------------|
| `users` | All system users (admin, finance, staff) |
| `asset_categories` | Asset types with short codes (LP, DISC, etc.) |
| `projects` | Projects that fund asset purchases |
| `vendors` | Suppliers/vendors |
| `assets` | All assets with tags, assignment, condition |
| `return_records` | Log of every asset return |

---

## Starting the App Each Time

```bash
# Windows
cd C:\gr_ams
venv\Scripts\activate
python run.py

# macOS / Linux
cd /home/yourname/gr_ams
source venv/bin/activate
python run.py
```

Press **Ctrl + C** to stop the server.

---

## Resetting the Database (Start Fresh)

```bash
# Delete the database file and restart — it will reseed automatically
# Windows
del instance\gr_ams.db
python run.py

# macOS / Linux
rm instance/gr_ams.db
python run.py
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `python: command not found` | Use `python3` instead, or reinstall Python with PATH option ticked |
| `pip: command not found` | Use `pip3` instead |
| `Address already in use` | Another program is using port 5000. Change `port=5000` to `port=5001` in `run.py` |
| Page not loading from other computers | Check Windows Firewall — allow Python through the firewall, or temporarily disable it for testing |
| `ModuleNotFoundError` | Make sure the virtual environment is activated (you see `(venv)` in your prompt) and run `pip install -r requirements.txt` again |

---

## Folder Structure

```
gr_ams/
├── run.py                  ← START HERE — runs the app
├── app.py                  ← App factory and database seed
├── models.py               ← Database table definitions
├── extensions.py           ← Flask extensions
├── requirements.txt        ← Package list
├── SETUP_GUIDE.md          ← This file
├── instance/
│   └── gr_ams.db         ← SQLite database (auto-created)
├── routes/
│   ├── auth.py             ← Login / logout
│   ├── main.py             ← Dashboard
│   ├── assets.py           ← Assets, assign, return, print
│   ├── users.py            ← User management
│   ├── admin.py            ← Categories, projects, vendors
│   └── reports.py          ← Reports and print-by-user
└── templates/
    ├── base.html           ← Sidebar, layout
    ├── dashboard_admin.html
    ├── dashboard_user.html
    ├── auth/login.html
    ├── assets/             ← index, form, assign, return, print
    ├── users/              ← index, form
    ├── admin/              ← categories, projects, vendors
    └── reports/            ← index, print_by_user
```
