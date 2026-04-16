
# RedNotebook API — FastAPI backend for the RedNotebook mobile app companion client for Android.

## What this is

- This is the the RedNotebook API systemd service for the RedNotebook mobile app companion client for Android, available at [
rednotebook-mobile-android](https://github.com/intranets-talk/rednotebook-mobile-android).
- Based on FastAPI/Python, it reads and writes RedNotebook yyyy-mm.txt files, providing the API endpoints for the Android app.
- Your RedNotebook text journal entries can reside on a shared mount, pointing to your desktop where the RedNotebook desktop app is installed.
- I am running the systemd service on a Orange Pi + a shared mount with my desktop, pointing to the RedNotebook `data` folder.
- You can also set up the systemd service directly on your Linux desktop; in that case, no shared mount is needed.

## What the script does:

- It creates a setup dir for Python venv at: `/opt/rednotebook-api`
- It installs Python: `sudo apt-get install -y python3 python3-venv python3-pip`
- It adds Python dependencies: `fastapi, uvicorn,pyyaml, pydantic`
- It sets up a systemd service running on port 8000: `rednotebook-api@${USER}`
- Shows the local IP so you can use it with the Android app: `systemctl status rednotebook-api@${USER}`

## How to install

- Take a backup of your RedNotebook journal entries, just in case.
- Clone the repo on your Linux host. I am using Debian 13.
- Edit the file rednotebook-api@.service to point to your RedNotebook text journal entries, change the following line in the file:

```
Environment=REDNOTEBOOK_DIR=/my/path/rednotebook/data
```

- Make setup.sh executable:

```
chmod +x setup.sh
./setup.sh
```

- Run as your normal user (not root); sudo is called where needed.


- After installation, check the service it's running:

```
sudo systemctl status rednotebook-api@YOUR_USERNAME
```

- Try it in your browser:

```
curl http://localhost:8000/months
```

## API endpoints examples:

```
GET /months                All months with entry counts

GET /entries/2025/04       All entries for April 2025

GET /entries/2025/04/16    Single day entry

PUT /entries/2025/04/16    Create or update an entry

DELETE /entries/2025/04/16 Delete an entry

GET /search?q=day          Full-text search across all entries
```

FastAPI also auto-generates interactive docs at http://localhost:8000/docs

- Note: The API endpoints do not feature authentication. Exposing the API publicly to the Internet will make your journal entries available to anyone. Not a good idea.

## Thanks to

- [Jendrik Seipp](https://github.com/jendrikseipp) - creator of RedNotebook and contributors.

## Contributing

- Can the RedNotebook FastAPI backend service be improved? Of course, in many ways!
- Ex: handle image attachments, add API endpoints for improved search, add authentication.
- Feel free to submit a pull request for any improvements.
