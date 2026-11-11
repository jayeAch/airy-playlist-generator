import json
import time
import requests
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape, quoteattr

API_URL = 'https://api.airy.tv/api/v2.1.7/channels'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

M3U_FILENAME = "airy_channels.m3u"
EPG_FILENAME = "airy_channels.xml"

GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "airy-playlist-generator"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/{EPG_FILENAME}"

headers = {'user-agent': USER_AGENT}


def parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def xmltv_time(dt):
    return dt.strftime('%Y%m%d%H%M%S +0000')


def fetch_data(retries=3, delay=5):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(API_URL, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay * attempt)
    return None


def generate_files(data):
    if not data or data.get('status') != 'success':
        print("Invalid data received from API")
        return

    m3u_lines = [f'#EXTM3U x-tvg-url="{GITHUB_RAW_URL}"']
    xml_channels = []
    xml_programmes = []
    processed_channels = set()
    prog_count = 0
    chans_with_epg = 0

    categories = data.get('response', {}).get('categories', [])

    for category in categories:
        cat_name = category.get('name', 'General').replace('_', ' ')

        for chan in category.get('stream_channels', []):
            chan_id = str(chan.get('id', ''))
            if not chan_id or chan_id in processed_channels:
                continue

            chan_name = chan.get('name', 'Unknown').replace('_', ' ')
            stream_url = chan.get('source_url', '')
            if not stream_url:
                continue

            logo = chan.get('image_url', '') or ''
            xid = f"airy-{chan_id}"

            m3u_lines.append(
                f'#EXTINF:-1 tvg-id="{xid}" tvg-name="{chan_name}" '
                f'tvg-logo="{logo}" group-title="{cat_name}",{chan_name}'
            )
            m3u_lines.append(stream_url)

            xml_channels.append(
                f'  <channel id={quoteattr(xid)}>\n'
                f'    <display-name>{escape(chan_name)}</display-name>\n'
                f'    <icon src={quoteattr(logo)} />\n'
                f'  </channel>'
            )

            progs = 0
            for prog in chan.get('broadcasts', []) or []:
                start_dt = parse_iso(prog.get('view_start_at_iso'))
                if not start_dt:
                    continue
                try:
                    duration = float(prog.get('view_duration', 0) or 0)
                except (TypeError, ValueError):
                    duration = 0
                if duration <= 0:
                    continue
                end_dt = start_dt + timedelta(seconds=duration)

                title = escape(prog.get('title') or chan_name)
                desc = escape(prog.get('description') or "No description available.")

                xml_programmes.append(
                    f'  <programme start="{xmltv_time(start_dt)}" stop="{xmltv_time(end_dt)}" channel={quoteattr(xid)}>\n'
                    f'    <title>{title}</title>\n'
                    f'    <desc>{desc}</desc>\n'
                    f'  </programme>'
                )
                progs += 1

            prog_count += progs
            if progs:
                chans_with_epg += 1
            processed_channels.add(chan_id)

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    xml_lines += xml_channels + xml_programmes
    xml_lines.append('</tv>')

    with open(M3U_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    with open(EPG_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

    print(f"Channels: {len(processed_channels)} | with EPG: {chans_with_epg} | programmes: {prog_count}")


if __name__ == "__main__":
    generate_files(fetch_data())
