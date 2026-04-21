
# RedNotebook API — FastAPI backend for the RedNotebook mobile app companion client for Android.

## What this is

- This is the the RedNotebook API systemd service for the RedNotebook mobile app companion client for Android, available at [
rednotebook-mobile-android](https://github.com/intranets-talk/rednotebook-mobile-android).
- Based on FastAPI/Python, it reads and writes RedNotebook yyyy-mm.txt files, providing the API endpoints for the Android app.
- It adds the ability to embed [Immich](https://github.com/immich-app/immich) photos in both the [RedNotebook](https://github.com/jendrikseipp/rednotebook) desktop app as well as in the [
rednotebook-mobile-android](https://github.com/intranets-talk/rednotebook-mobile-android) app.
- Your RedNotebook text journal entries can reside on a shared mount, pointing to your desktop where the RedNotebook desktop app is installed.
- I am running this FastAPI backend as a systemd service on a Orange Pi + a shared mount with my desktop, pointing to the RedNotebook `data` folder.
- You can also set up the systemd service directly on your Linux desktop; in that case, no shared mount is needed.

## Features

- *API*: provides a CRUD FastAPI backend for the companion [
rednotebook-mobile-android](https://github.com/intranets-talk/rednotebook-mobile-android) app. API endpoints listed below.
- *Embed Immich photos*: ability to embed Immich photos via the FastAPI service, acting as proxy — embed images in RedNotebook desktop and Android app, using a URL link format like: `[""http://YOUR_FASTAPI_IP:8000/immich/ASSET_ID"".jpg]`. Note that the file extension in URL is a dummy for RedNotebook compatibility — actual format is detected from Immich response headers.

* Note: *Images only*: this will only work for images, videos will not work. Images are resized to 300px wide and EXIF orientation is preserved using Pillow.

## What the script does:

- It creates a setup dir for Python venv at: `/opt/rednotebook-api`
- It installs Python: `sudo apt-get install -y python3 python3-venv python3-pip`
- It adds Python dependencies: `fastapi, uvicorn,pyyaml, pydantic, httpx, Pillow`
- It sets up a systemd service running on port 8000: `rednotebook-api@${USER}`
- Shows the local FastAPI service IP so you can use it with the Android app: `systemctl status rednotebook-api@${USER}`

## How to install

- Take a backup of your RedNotebook journal entries, just in case.
- Clone the repo on your Linux host. I am using Debian 13.
- Edit the file `rednotebook-api@.service` to point to your RedNotebook text journal entries (shared mount or local) - and add the Immich URL and API key if you want to embed Immich photos in your journal entries - change the following lines:

```
Environment=REDNOTEBOOK_DIR=/my/path/rednotebook/data # required - path to rednotebook text files
IMMICH_URL=https://your-immich-host # optional - if you are using Immich
IMMICH_API_KEY=your-immich-api-key" # optional - if you are using Immich
```

- Optionally, change the port number;
- Make `setup.sh` executable and run it as your normal user (not root); sudo is called where needed:

```
chmod +x setup.sh
./setup.sh
```

- After installation, check the service it's running:

```
sudo systemctl status rednotebook-api@YOUR_USERNAME
```

- Try it in your browser:

```
curl http://fastapi-ip-address:8000/months
```

- *For both RedNotebook desktop and Android app*: if you are using Immich, you can use the following format to embed images in your journal entries ():

`[""http://YOUR_FASTAPI_IP:8000/immich/ASSET_ID"".jpg]`

* This will not work for videos. You can get the ASSET_ID for an Immich photo by opening the photo in the browser, the last part of the URL will be the ASSET_ID, example:

`https://IMMICH-IP/photos/ec96511e-957a-4954-93r9-ae4543e0fcb8`

* I know this is not "elegant" or "ideal", but personally I'll take this rather than nothing, improvements welcomed.

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

- Can the RedNotebook FastAPI backend service be improved? Of course, in many ways:

  - Add API endpoints for improved search;
  - Add authentication;
  - Add option to automatically insert the outside temperature;
  - Change the service into a Docker image.

- Feel free to submit a pull request for any improvements.
- MIT Licensed.
