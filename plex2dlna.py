#!/usr/bin/python3
"""
Fetch the currently active Plex stream from Tautulli and play it on this LG TV via luna-send. Designed to run on a webOS TV.
"""
import json
import os
import re
import subprocess
import sys

# --- Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "plex2dlna.json")
with open(CONFIG_PATH) as _f:
    _config = json.load(_f)

TAUTULLI_URL = _config["tautulli_url"]
TAUTULLI_API_KEY = _config["tautulli_api_key"]
PLEX_URL = _config["plex_url"]
ALLOWED_USERS = set(_config["allowed_users"])

# Map container/extension to DLNA MIME type
MIME_TYPES = {
    "mkv": "video/x-matroska",
    "mp4": "video/mp4",
    "avi": "video/x-msvideo",
    "mov": "video/quicktime",
    "wmv": "video/x-ms-wmv",
    "ts": "video/mp2t",
    "m4v": "video/mp4",
}


def show_message(message):
    """Show a toast notification on the TV."""
    endpoint = "luna://com.webos.notification/createToast"
    payload = {"message": message}
    luna_send(endpoint, payload)


def error_exit(message):
    """Print error, show it on the TV, and exit."""
    print("ERROR: %s" % message)
    show_message("Plex Play: %s" % message)
    sys.exit(1)


def curl_json(url):
    """Fetch URL with system curl, return parsed JSON."""
    try:
        output = subprocess.check_output(["curl", "-sf", url])
    except subprocess.CalledProcessError:
        error_exit("Failed to reach Tautulli")
    return json.loads(output)


def resolve_to_ip(url):
    """Replace hostname in URL with its resolved IP address."""
    match = re.match(r'(https?://)([^:/]+)(.*)', url)
    if not match:
        return url
    scheme, host, rest = match.groups()
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
        return url
    try:
        import socket
        ip = socket.gethostbyname(host)
        print("Resolved %s -> %s" % (host, ip))
        return scheme + ip + rest
    except Exception:
        print("WARNING: could not resolve %s, using as-is" % host)
        return url


def luna_send(endpoint, payload):
    """Execute luna-send-pub and return output."""
    cmd = ["/usr/bin/luna-send-pub", "-n", "1", "-f", endpoint, json.dumps(payload)]
    print("luna-send-pub: %s %s" % (endpoint, json.dumps(payload)))
    try:
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        print("ERROR: luna-send-pub failed: %s" % e)
        return None


def get_activity():
    """Get current streaming activity from Tautulli."""
    url = "%s?apikey=%s&cmd=get_activity" % (TAUTULLI_URL, TAUTULLI_API_KEY)
    data = curl_json(url)
    return data.get("response", {}).get("data", {})


def terminate_session(session):
    """Stop the original Plex session via Tautulli."""
    session_key = session.get("session_key")
    if not session_key:
        print("WARNING: no session_key, cannot terminate")
        return
    url = "%s?apikey=%s&cmd=terminate_session&session_key=%s&message=Moved+to+TV" % (
        TAUTULLI_URL, TAUTULLI_API_KEY, session_key)
    print("Terminating session %s" % session_key)
    try:
        subprocess.check_output(["curl", "-sf", url])
    except subprocess.CalledProcessError:
        print("WARNING: failed to terminate session")


def get_user_token(session):
    """Fetch the user's Plex token from Tautulli."""
    user_id = session.get("user_id")
    if not user_id:
        print("WARNING: no user_id in session")
        return None
    url = "%s?apikey=%s&cmd=get_user&user_id=%s" % (TAUTULLI_URL, TAUTULLI_API_KEY, user_id)
    data = curl_json(url)
    token = data.get("response", {}).get("data", {}).get("user_token")
    if not token:
        print("WARNING: no user_token returned for user_id %s" % user_id)
    return token


def mark_watched(session):
    """Mark the item as watched on Plex on behalf of the streaming user."""
    rating_key = session.get("rating_key")
    if not rating_key:
        print("WARNING: no rating_key, cannot scrobble")
        return
    token = get_user_token(session)
    url = "%s/:/scrobble?key=%s&identifier=com.plexapp.plugins.library" % (PLEX_URL, rating_key)
    if token:
        url += "&X-Plex-Token=%s" % token
    else:
        print("WARNING: scrobbling without user token (will mark on server owner's account)")
    print("Marking rating_key %s as watched" % rating_key)
    try:
        subprocess.check_output(["curl", "-sf", url])
    except subprocess.CalledProcessError:
        print("WARNING: failed to mark as watched")


def extract_part_id(session):
    """Extract the Plex part ID from bif_thumb field."""
    bif_thumb = session.get("bif_thumb", "")
    # Format: /library/parts/<part_id>/indexes/sd/<offset>
    match = re.match(r'/library/parts/(\d+)/', bif_thumb)
    if match:
        return match.group(1)
    return None


def get_mime_type(file_path):
    """Get DLNA MIME type from file extension."""
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    return MIME_TYPES.get(ext, "video/mp4")


def play_on_tv(url, title="Plex", mime_type="video/mp4"):
    """Launch video playback via com.webos.app.mediadiscovery."""
    endpoint = "luna://com.webos.applicationManager/launch"
    protocol_info = "http-get:*:%s:DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000" % mime_type
    payload = {
        "id": "com.webos.app.mediadiscovery",
        "params": {
            "payload": [{
                "fullPath": url,
                "fileName": title,
                "mediaType": "VIDEO",
                "deviceType": "DMR",
                "dlnaInfo": {
                    "flagVal": 4096,
                    "cleartextSize": "-1",
                    "contentLength": "-1",
                    "opVal": 1,
                    "protocolInfo": protocol_info,
                    "duration": 0,
                },
                "thumbnail": "",
                "artist": "",
                "subtitle": "",
                "album": "",
                "lastPlayPosition": -1,
            }]
        }
    }
    result = luna_send(endpoint, payload)
    if result:
        print("Playback launched.")
    else:
        error_exit("Failed to launch playback")
    return result


def main():
    debug = "--debug" in sys.argv

    show_message("Moving Plex content to DLNA app...")

    activity = get_activity()
    sessions = activity.get("sessions", [])

    if not sessions:
        error_exit("No active Plex streams")

    sessions = [s for s in sessions if s.get("username") in ALLOWED_USERS]
    if not sessions:
        error_exit("No streams for allowed users")

    session = sessions[0]
    title = session.get("full_title", session.get("title", "Unknown"))
    print("Active stream: %s" % title)

    if debug:
        print(json.dumps(session, indent=2))
        return

    part_id = extract_part_id(session)
    file_path = session.get("file", "")
    if not part_id:
        error_exit("Could not extract part ID from bif_thumb")
    if not file_path:
        error_exit("No file path in session data")

    ext = os.path.splitext(file_path)[1].lstrip(".")
    stream_url = "%s/library/parts/%s/file.%s" % (PLEX_URL, part_id, ext)
    stream_url = resolve_to_ip(stream_url)
    mime_type = get_mime_type(file_path)

    print("Stream URL: %s" % stream_url)
    print("MIME type: %s" % mime_type)
    terminate_session(session)
    mark_watched(session)
    play_on_tv(stream_url, title=title, mime_type=mime_type)


if __name__ == "__main__":
    main()
