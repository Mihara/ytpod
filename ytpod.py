#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import mimetypes
import os
import subprocess
import json
import re
from urllib.parse import urljoin

import click
import feedparser
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

FILE_LEGAL = re.compile(r"[^\w_. -]")


def fail(*objs):
    """Shorthand for failure."""
    click.get_current_context().fail("ERROR: ", *objs)


def warn(s):
    """Shorthand for warning."""
    click.echo(message="WARNING: " + s, err=True)


def get_feed_icon(channel_page, channel_id, root, destination, s):
    """
    Previously, this function just tried to refer to the icon file on
    youtube itself, but now it just downloads the thing, and parses
    channel information from page <meta> for good measure.
    """
    r = s.get(channel_page)
    if not r.status_code == 200:
        warn("Failed to acquire feed icon from youtube.")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    icon = soup.find("meta", attrs={"property": "og:image"})
    if icon is not None:
        try:
            r = s.get(icon["content"])
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
    warn("Failed to parse out icon from youtube, which could be perfectly normal.")
    return None


def get_channel_description(channel_page, s):
    r = s.get(channel_page + "/about")
    if not r.status_code == 200:
        warn("Failed to acquire channel description from youtube.")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    description = soup.find("meta", attrs={"name": "description"})
    if description is not None:
        return description["content"]
    warn(
        "Failed to parse out channel description from youtube, "
        "which could be perfectly normal."
    )
    return None


def download_log(destination):
    return os.path.join(destination, "download_log")


def get_download_log(destination):
    try:
        with open(download_log(destination), "r") as f:
            return [x.split(" ")[1].strip() for x in f.read().split("\n") if x]
    except FileNotFoundError:
        return []


@click.command()
@click.argument("url")
@click.argument("root")
@click.option("--destination", "-d", default=".", help="Where to put output files")
@click.option(
    "--limit", "-l", default=10, help="Number of recent files to keep in the feed"
)
@click.option(
    "--file_format",
    "-f",
    default="bestaudio",
    help="Preferred format option as per youtube-dl/yt-dlp documentation.",
)
@click.option(
    "--keep-video",
    is_flag=True,
    default=False,
    help="By default, ytpod will attempt to download an audio-only file. "
    "This option will make it keep the video and avoid conversion.",
)
@click.option(
    "--keep-unlisted",
    is_flag=True,
    default=False,
    help="By default, files no longer present in the RSS feed of the channel "
    "will be deleted. If you want to keep them, use this option.",
)
@click.option(
    "--noblock",
    "-n",
    is_flag=True,
    default=False,
    help="Do not prevent the feed from being listed in iTunes " "podcast directory",
)
@click.option(
    "--proxy", help="A proxy url (like 'socks5://localhost:port') if required."
)
def run(
    url, root, destination, limit, file_format, noblock, proxy, keep_video, keep_unlisted
):
    """
    Download a YouTube channel as files to make a podcast RSS feed.
    """

    s = requests.Session()
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})

    r = s.get(url)

    feed = feedparser.parse(r.text)
    if feed["bozo"]:
        fail("Could not parse feed from {}".format(url))

    if len(feed["entries"]) < 1:
        fail("Channel appears to contain no videos.")

    if not feed.get("feed"):
        fail("Channel appears to contain no feed metadata")

    # For a while now youtube wasn't supplying a channel id field in feed header,
    # bur rather only in the entries.
    feed_id = feed["feed"]["yt_channelid"] or FILE_LEGAL.sub("_", feed["feed"]["href"])

    channel_page = feed["feed"].get("author_detail", {}).get("href", None)
    feed_icon = get_feed_icon(channel_page, feed_id, root, destination, s)
    channel_description = get_channel_description(channel_page, s)

    output = FeedGenerator()
    output.load_extension("podcast")

    output.id(feed_id)
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
        download_log(destination),
        "--format",
        file_format,
    ]

    if not keep_video:
        ydl_options += ["-x"]

    if proxy:
        ydl_options += ["--proxy", proxy]

    youtube_identifiers = []

    for entry in feed["entries"][0:limit]:
        youtube_id = entry["id"].split(":")[2]
        youtube_identifiers.append(youtube_id)
        video_url = entry["link"]

        # Don't even invoke youtube-dl if the file is in the download log.
        downloaded_ids = get_download_log(destination)

        if youtube_id not in downloaded_ids:
            # So here we have to invoke youtube-dl (or yt-dlp) as a subprocess instead of
            # trying to call it directly.

            info = subprocess.check_output(["youtube-dl"] + ydl_options + [video_url])
            info = json.loads(info)
            if not info:
                # That means the file is in the log but was deleted from disk.
                # In which case we don't want it in the feed either, so bail before
                # we create the corresponding entry.
                warn(
                    "{} was downloaded before, but was since deleted, ignoring.".format(
                        youtube_id
                    )
                )
                continue

            downloaded_filename = info["requested_downloads"][0]["filepath"]
            
            # Deal with the thumbnail. We're going to be embedding it into the file
            # once we can add media tags to the file itself.
            r = s.get(entry["media_thumbnail"][0]["url"])
            if r.status_code == 200:
                ext = entry["media_thumbnail"][0]["url"].rsplit('.',1)[-1]
                icon_filename = os.path.join(destination, 'icon.{}.{}'.format(youtube_id,ext))
                with open(icon_filename, "wb") as f:
                    f.write(r.content)
                
        else:
            # Else find it on disk.
            fitting_filenames = glob.glob(
                os.path.join(destination, "{}.*".format(youtube_id))
            )
            # If the file was deleted, skip creating output feed entry.
            if not len(fitting_filenames):
                warn(
                    "{} was downloaded before, but was since deleted, ignoring.".format(
                        youtube_id
                    )
                )
                continue
            downloaded_filename = fitting_filenames[0]
            icon_filename = glob.glob(os.path.join(destination, "icon.{}.*".format(youtube_id)))[0]
            click.echo("{} already downloaded.".format(youtube_id))

        output_entry = output.add_entry()
        file_url = urljoin(root, os.path.basename(downloaded_filename))
        output_entry.id(file_url)
        output_entry.link(entry["links"])
        output_entry.title(entry["title"])
        output_entry.summary(entry["summary"])
        output_entry.enclosure(
            file_url,
            str(os.path.getsize(downloaded_filename)),
            mimetypes.guess_type(file_url)[0],
        )
        output_entry.podcast.itunes_image(icon_filename or feed_icon)
        output_entry.published(entry["published"])

    # If the feed icon was not available, use a video thumbnail instead.
    if not feed_icon and icon_filename:
        feed_icon = urljoin(root, os.path.basename(icon_filename))
    # Just don't add a feed icon if we still don't have one.
    if feed_icon:
        output.podcast.itunes_image(feed_icon)

    output.rss_file(os.path.join(destination, "rss.xml"))

    # Now clean the output directory of files previously downloaded but not in the feed.
    # Re-read the download log for this.
    if not keep_unlisted:
        downloads = get_download_log(destination)
        for youtube_id in downloads:
            if youtube_id not in youtube_identifiers:
                for name in glob.glob(
                    os.path.join(destination, "{}.*".format(youtube_id))
                ) + glob.glob(
                    os.path.join(destination, "icon.{}.*".format(youtube_id))
                ):
                    os.remove(name)


if __name__ == "__main__":
    run()
