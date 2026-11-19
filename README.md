# Vesper Keep Player

A Windows helper that connects your own Jellyfin library to the Vesper Keep VRChat theatre. Browse a poster catalogue, pick a title, and play it on the theatre screen.

**Preview, not a finished public release.** The installer has been tested locally, including uninstall. Local two-client tests passed for late-joining catalogues, shared selection, manual disconnect, and provider departure. Lock permissions and remote-device playback remain to be verified. Remote movie delivery to other homes and standalone Quest is not finished. Do not interpret a public catalogue relay as a working remote video service.

## What to open first

1. Start **Jellyfin Server**, the program that manages your movies and shows. It must already have a library configured.
2. Open **Vesper Keep Player** and click **Open player** when it says Ready.
3. Click **Connect Jellyfin**. Vesper shows an approval code and tries to copy it.
4. Click **Open Jellyfin**. Sign in to your own Jellyfin server if asked. Open your profile menu at the top-right, choose **Quick Connect**, paste the code, and approve it.
5. Return to Vesper. Your catalogue appears automatically.
6. Choose **Pair my in-world menu**, then **Copy full link**. In the Keep theatre, open the small round logo below the screen, choose the **Jellyfin** tab, paste the link, and choose **Connect library**.
7. Choose a movie, or a series, season and episode, then press **Play**.

Keep **Jellyfin Server and Vesper Keep Player** running while watching. The separate Jellyfin desktop media-player app is not required. After approving the code, you can close the Jellyfin browser tab.

## Install and uninstall

The Windows installer lets you choose the installation folder. It installs for your Windows user and adds desktop and Start menu shortcuts. It does not install Jellyfin, include movies, move your media, or change your Jellyfin library folders.

Vesper stores its app files and a temporary `Data` folder inside the chosen installation folder. Choose a location your Windows account can write to. No Windows startup task or background Windows service is installed. Launch the app when needed and use **Stop and exit** when finished.

To uninstall: stop Vesper, then open **Windows Settings → Apps → Installed apps → Vesper Keep Player → Uninstall**. The uninstaller removes Vesper's files, shortcuts, registration and temporary data. Jellyfin and your movie folders are not uninstall targets.

## Privacy & local access

### Jellyfin approval

Vesper never asks for your Jellyfin password, an administrator API key, or VRChat login credentials. Sign-in and approval happen in Jellyfin. Quick Connect grants a normal Jellyfin user session token; this is **not** a special read-only API key. Vesper holds that token and the connected account/server information in process memory, not in a saved credentials file. Jellyfin determines the account permissions and the lifetime of its session.

The app uses the approved account to read permitted library metadata and artwork and to request/start/stop its own playback/transcoding sessions. It does not implement media deletion, uploading, or server administration. Approve an account with only the library and playback permissions you want to grant; do not use an administrator account just for convenience.

**Disconnect Jellyfin** requests logout and clears the browser session. Closing Vesper clears its in-memory credentials. These do not justify a claim that Jellyfin has automatically expired every server-side device token. The Jellyfin server owner can manage/revoke devices in the server dashboard. Stopping a movie only stops playback; it is not account revocation.

### Local Windows and VRChat checks

Vesper reads Steam installation locations, Windows process identities/start times and the owner of local TCP connections to verify requests from the expected VRChat client. It reads that client's existing VRChat output log to identify the current Keep visit and detect leaving the world or closing the game. This lets it end catalogue pairing when the visit ends.

Vesper does not inject code into VRChat or read VRChat process memory. It does not copy or upload the output log, extract a social graph, or ask for a VRChat login. VRChat creates its own logs independently; Vesper does not delete or control those files. The app also reads its own installation assets and writes temporary stream segments and poster-building files in its own Data directory.

### Network and sharing

The local player listens only on `127.0.0.1:8097`, not every network interface. `127.0.0.1` means the computer running it; each user needs their own helper. Other users do not connect to the developer's PC by using that address.

The app contacts the Jellyfin server selected by the user. When the user pairs the catalogue with the Keep, the app sends a limited catalogue projection (titles, descriptions, categories, ordering and poster artwork) to the public HTTPS catalogue relay. People in that paired instance can browse and select from the catalogue, subject to player controls. **Catalogue data and artwork are therefore shared deliberately when pairing.** Jellyfin tokens, passwords, internal movie URLs and local media paths are not part of the relay payload.

The relay uses short-lived in-memory grants. Stop pairing, leaving the verified Keep visit, or losing the provider heartbeat ends catalogue access. The hosting provider still handles ordinary network traffic; this documentation does not promise that no third party ever handles IP addresses or server access metadata.

## Build and verify

The source and build inputs are being prepared for public review. No public Actions build or signed attestation has been produced yet. The current local test installer is unsigned. Do not disable Windows protection or dismiss a detection merely because it may be a false positive.

The release workflow will build from a visible source commit, publish SHA-256 checksums and generate GitHub artifact attestations. Attestations establish build provenance; they are not a security audit and do not prove the program has no bugs. An installer code-signing certificate is separate from GitHub provenance.

A raw Python source option is included for technical users. This is a multi-module program with native Windows checks, not a 100-line script. Runtime dependencies and exact build instructions will be supplied with the release.

No VirusTotal upload has been made. Any future scan will identify the exact release hash, link the actual report, and treat detections individually rather than telling users to ignore them.

## Licensing

Code license: MIT. Third-party notices are included separately. The Vesper Keep logo and other brand artwork are not covered by the MIT code license. Jellyfin and VRChat are independent projects; Vesper Keep Player is not an official Jellyfin or VRChat client.
### Build from source (Windows x64)

Use Python 3.13.13 and WiX 3.14.1. From a checkout in a writable folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-build.lock
.\Build.ps1 -WixPath "D:\Tools\wix314" -Python ".\.venv\Scripts\python.exe"
```

Replace the WiX example path with your extracted WiX folder. All build intermediates go into this checkout's `build` and `dist` directories. The build script checks the bundled app before packaging. `dist/release` contains the preview MSI and `SHA256SUMS.txt`.

For source-only use, install `requirements-runtime.txt`, run `python src/service_entry.py`, then open `http://127.0.0.1:8097/`. Stop the source process when finished. The compiled desktop launcher is optional for source users.

The prepared GitHub workflow is manual-only. It pins Actions by commit, verifies the WiX ZIP hash, installs hash-locked Python dependencies, runs unit checks, builds the MSI, generates an installer provenance attestation, and uploads the MSI/checksum as workflow artifacts. It does **not** publish a GitHub Release automatically. A successful hosted run still needs to be performed before a release can claim provenance.

Installer validation: ICE91 is intentionally excluded because this package supports per-user installation only. Two font-language metadata warnings are currently reviewed and documented; they do not disable the remaining installer validation. Local install/uninstall testing covers a custom installation folder, shortcut registration, temporary cache cleanup, and preservation of a file outside the installation folder.
