#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import mimetypes
import os
import subprocess
import json
from urllib.parse import urljoin

import click
import feedparser
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator


def fail(*objs):
    """Shorthand for failure."""
    click.get_current_context().fail("ERROR: ", *objs)


def warn(s):
    """Shorthand for warning."""
    click.echo(message="WARNING: " + s, err=True)


def get_feed_icon(channel_page, channel_id, root, destination):
    """
    Previously, this function just tried to refer to the icon file on
    youtube itself, but now it just downloads the thing, and parses
    channel information from page <meta> for good measure.
    """
    r = requests.get(channel_page)
    if not r.status_code == 200:
        warn("Failed to acquire feed icon from youtube.")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    icon = soup.find("meta", attrs={"property": "og:image"})
    if icon is not None:
        try:
            r = requests.get(icon["content"])
        except requests.exceptions.ConnectionError:
            warn(
                "Could not download icon, which can happen if certain parts of youtube are blocked in your country."
            )
            return None
        if not r.status_code == 200:
            warn("Failed to download feed icon from youtube.")
            return None
        mime = r.headers.get("Content-Type")
        if mime is None:
            warn("Youtube has an icon with a mysterious file type.")
        extension = {"image/jpeg": ".jpg"}.get(mime, mimetypes.guess_extension(mime))
        icon_filename = os.path.join(destination, "{}{}".format(channel_id, extension))
        with open(icon_filename, "wb") as f:
            f.write(r.content)
        return urljoin(root, icon_filename)
    warn("Failed to parse out icon from youtube, ytpod needs an update.")
    return None


def get_channel_description(channel_page):
    r = requests.get(channel_page + "/about")
    if not r.status_code == 200:
        warn("Failed to acquire channel description from youtube.")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    description = soup.find("meta", attrs={"name": "description"})
    if description is not None:
        return description["content"]
    warn(
        "Failed to parse out channel description from youtube, "
        "ytpod needs to be updated"
    )
    return None


@click.command()
@click.argument("url")
@click.argument("root")
@click.option("--destination", "-d", default=".", help="Where to put output files")
@click.option(
    "--limit", "-l", default=10, help="Number of recent videos to keep in the feed"
)
@click.option(
    "--format",
    "-f",
    default="best",
    help="Preferred format option as per youtube-dl documentation. "
    "Use 'bestaudio/best' to download only audio.",
)
@click.option(
    "--noblock",
    "-n",
    is_flag=True,
    default=False,
    help="Do not prevent the feed from being listed in iTunes " "podcast directory",
)
def run(url, root, destination, limit, format, noblock):
    feed = feedparser.parse(url)
    if feed["bozo"]:
        fail("Could not parse feed from {}".format(url))

    if len(feed["entries"]) < 1:
        fail("Channel appears to contain no videos.")

    if not feed.get("feed"):
        fail("Channel appears to contain no feed metadata")

    channel_page = feed["feed"].get("author_detail", {}).get("href", None)
    feed_icon = get_feed_icon(
        channel_page, feed["feed"]["yt_channelid"], root, destination
    )
    channel_description = get_channel_description(channel_page)

    output = FeedGenerator()
    output.load_extension("podcast")

    output.id(feed["feed"]["yt_channelid"])
    output.title(feed["feed"]["title"])
    output.author({"name": feed["feed"]["author"], "uri": feed["feed"]["link"]})

    if not noblock:
        output.podcast.itunes_block(True)

    if channel_description:
        output.description(channel_description)
    else:
        output.description("{} Youtube Channel-as-Podcast. See {}").format(
            feed["feed"]["title"], channel_page
        )

    output.link(href=urljoin(root, "rss.xml"), rel="self")

    ydl_options = [
        "--ignore-config",
        "-J",
        "--no-simulate",
        "--no-progress",
        "-o",
        os.path.join(destination, "%(id)s.%(ext)s"),
        "--download-archive",
        os.path.join(destination, "download_log"),
        "--format",
        format,
    ]

    youtube_identifiers = []

    for entry in feed["entries"][0:limit]:
        youtube_id = entry["id"].split(":")[2]
        youtube_identifiers.append(youtube_id)
        video_url = "https://www.youtube.com/watch?v={}".format(youtube_id)

        # Skip the whole downloading process if the file already exists
        existing_files = glob.glob(os.path.join(destination, "{}.*".format(youtube_id)))
        if not existing_files:
            # So here we have to invoke youtube-dl (or yt-dlp) as a subprocess instead of
            # trying to call it directly.
            info = subprocess.check_output(["youtube-dl"] + ydl_options + [video_url])
            info = json.loads(info)
            extension = info["formats"][
                next(
                    index
                    for (index, x) in enumerate(info["formats"])
                    if x["format_id"] == info["format_id"]
                )
            ]["ext"]
            downloaded_filename = os.path.join(
                destination, "{}.{}".format(youtube_id, extension)
            )
        else:
            print("{} already downloaded, skipping".format(youtube_id))
            downloaded_filename = existing_files[0]
            extension = downloaded_filename.split(".")[-1]

        output_entry = output.add_entry()
        file_url = urljoin(root, youtube_id + "." + extension)
        output_entry.id(file_url)
        output_entry.link(entry["links"])
        output_entry.title(entry["title"])
        output_entry.summary(entry["summary"])
        output_entry.enclosure(
            file_url,
            str(os.path.getsize(downloaded_filename)),
            mimetypes.guess_type(file_url)[0],
        )
        thumbnail = entry["media_thumbnail"][0]["url"]
        if not feed_icon:
            feed_icon = thumbnail
        output_entry.podcast.itunes_image(feed_icon)
        output_entry.published(entry["published"])

    output.podcast.itunes_image(feed_icon)
    output.rss_file(os.path.join(destination, "rss.xml"))

    # Now clean the output directory of files previously downloaded but not in the feed.
    with open(os.path.join(destination, "download_log"), "r") as f:
        for line in f.readlines():
            if line.strip():
                id = line.split()[1]
                if id not in youtube_identifiers:
                    for name in glob.glob(os.path.join(destination, "{}.*".format(id))):
                        os.remove(name)


if __name__ == "__main__":
    run()
