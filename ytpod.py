#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Why is that a default anywhere?...
# pylint: disable=invalid-name

"""
Youtube-to-podcast shim.
"""

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
import mediafile
import arrow
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator


def fail(msg):
    """Shorthand for failure."""
    click.get_current_context().fail(msg)


def warn(msg):
    """Shorthand for warning."""
    click.echo(message=f"Warning: {msg}", err=True)


def get_feed_icon(channel_page, channel_id, s):
    """
    Previously, this function just tried to refer to the icon file on
    youtube itself, but now it just downloads the thing, and parses
    channel information from page <meta> for good measure.
    """
    root = click.get_current_context().params["root"]
    destination = click.get_current_context().params["destination"]
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
                "Could not download icon, which can happen if certain "
                "parts of youtube are blocked in your country."
            )
            return None
        if not r.status_code == 200:
            warn("Failed to download feed icon from youtube.")
            return None
        mime = r.headers.get("Content-Type")
        if mime is None:
            warn("Youtube has an icon with a mysterious file type.")
        extension = {
            "image/jpeg": "jpg",
        }.get(mime, mimetypes.guess_extension(mime))
        icon_filename = os.path.join(destination, f"{channel_id}.{extension}")
        with open(icon_filename, "wb") as f:
            f.write(r.content)
        return urljoin(root, icon_filename)
    warn("Failed to parse out icon from youtube, which could be perfectly normal.")
    return None


def get_channel_description(channel_page, s):
    """
    You would think this would be easy or present in the rss feed.
    No it's not.
    """
    r = s.get(channel_page + "/about")
    if not r.status_code == 200:
        warn("Failed to acquire channel description from youtube.")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    description = soup.find("meta", attrs={"name": "twitter:description"})
    if description is not None:
        return description["content"]
    warn(
        "Failed to parse out channel description from youtube, "
        "which could be perfectly normal."
    )
    return None


def download_log():
    """Filename of the download log for this feed."""
    return os.path.join(
        click.get_current_context().params["destination"], "download_log"
    )


def get_download_log():
    """Read the download log and parse out the youtube ids."""
    try:
        with open(download_log(), "r", encoding="utf-8") as f:
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
    url,
    root,
    destination,
    limit,
    file_format,
    noblock,
    proxy,
    keep_video,
    keep_unlisted,
):
    """
    Download a YouTube channel as files to make a podcast RSS feed.
    """

    s = requests.Session()
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})

    # This is likely to be broken in short order,
    # but it bypasses the consent form,
    # which prevents the issues with fetching the icon and channel description.
    # Courtesy of https://stackoverflow.com/questions/74127649/
    s.cookies.set("SOCS", "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg")

    r = s.get(url)

    if r.status_code != 200:
        fail("Could not get the channel feed.")

    # See if we got a channel url rather than its RSS feed url.
    # If so, handle it - the easy way to get the channel id and
    # make an RSS url is to get the channel username out of the meta tags.

    if r.headers.get("Content-Type", "").startswith("text/html;"):
        # Rather than xml, which implies we need to extract the channel id.
        soup = BeautifulSoup(r.text, "html.parser")
        channel_url = soup.find("meta", attrs={"name": "twitter:url"})
        if not channel_url:
            fail("Wait, is that even a youtube URL?...")
        channel_url = channel_url["content"]
        m = re.match(r"^https://www.youtube.com/channel/(?P<user>.+)$", channel_url)
        if m:
            actual_url = (
                f"https://www.youtube.com/feeds/videos.xml?channel_id={m['user']}"
            )
            r = s.get(actual_url)
            if r.status_code == 200:
                click.echo(f"The actual RSS feed URL is {actual_url}")
            else:
                fail(
                    f"I figured out the actual channel feed URL, ({actual_url}) but couldn't fetch it."
                )
        else:
            fail(
                "I don't recognize the channel URL, so it's up to you to get an RSS feed out of it."
            )

    feed = feedparser.parse(r.text)

    if feed["bozo"]:
        fail(f"Could not parse feed from {url}")

    if len(feed["entries"]) < 1:
        fail("Channel appears to contain no videos.")

    if not feed.get("feed"):
        fail("Channel appears to contain no feed metadata")

    # For a while now youtube wasn't supplying a channel id field in feed header,
    # bur rather only in the entries.
    # We're already checking if there's at least one entry by the time we get here.
    feed_id = feed["feed"]["yt_channelid"] or feed["entries"][0]["yt_channelid"]

    channel_page = feed["feed"].get("author_detail", {}).get("href", None)
    feed_icon = get_feed_icon(channel_page, feed_id, s)
    channel_description = get_channel_description(channel_page, s)

    output = FeedGenerator()
    # Pylint can't get at the podcast extension.
    # pylint: disable=no-member
    output.load_extension("podcast")

    output.id(feed_id)
    output.title(feed["feed"]["title"])
    output.author({"name": feed["feed"]["author"], "uri": feed["feed"]["link"]})

    if not noblock:
        output.podcast.itunes_block(True)

    if channel_description:
        output.description(channel_description)
    else:
        output.description(
            f"{feed['feed']['title']} Youtube Channel-as-Podcast. See {channel_page}"
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
        download_log(),
        "--format",
        file_format,
        # We can't be waiting for live streams.
        # But apparently that's not enough cause the process still throws an error...
        "--break-match-filter",
        "live_status='was_live'",
        "--break-match-filter",
        "live_status='not_live'",
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
        downloaded_ids = get_download_log()

        if youtube_id not in downloaded_ids:
            # So here we have to invoke youtube-dl (or yt-dlp) as a subprocess instead of
            # trying to call it directly.

            try:
                info = subprocess.check_output(["youtube-dl"] + ydl_options + [video_url], 
                                               stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                # youtube-dl / yt-dlp return errors when attempting
                # to download live events, but don't produce
                # very detailed error messages.
                # Live events, however, will one day air, so 
                # it's an error safe to ignore.
                if "live event will begin" in e.output.decode():
                    continue
                raise e
            
            try:
                info = json.loads(info)
            except json.decoder.JSONDecodeError:
                warn(f"{youtube_id} could not be downloaded, skipping...")
                continue

            if not info:
                # That means the file is in the log but was deleted from disk.
                # In which case we don't want it in the feed either, so bail before
                # we create the corresponding entry.
                warn(
                    f"{youtube_id} was downloaded before, but was since deleted, ignoring."
                )
                continue

            if not info.get("requested_downloads"):
                warn(
                    f"Could not download {youtube_id}, probably because "
                    "it's an active livestream. Skipping."
                )
                continue

            downloaded_filename = info["requested_downloads"][0]["filepath"]

            # Deal with the thumbnail. We're going to be embedding it into the file if possible.
            r = s.get(entry["media_thumbnail"][0]["url"])
            if r.status_code == 200:
                ext = entry["media_thumbnail"][0]["url"].rsplit(".", 1)[-1]
                icon_filename = os.path.join(destination, f"icon.{youtube_id}.{ext}")
                with open(icon_filename, "wb") as f:
                    f.write(r.content)

            try:
                podcast_file = mediafile.MediaFile(downloaded_filename)
                # The idea is that every podcast file is attributed to an artist
                # (feed title, on youtube it is the same as the author),
                # and is part of an album (year-month)
                # while track numbers in it uniquely identify an issue of the podcast
                # within that album, in chronological order.

                # We have no way of knowing a podcast's actual "track number",
                # since youtube's feed does not include anything that would let us know
                # how many videos are there in total. We have to cook up our own,
                # and the only thing we can rely on is the publishing date.
                # Players have issues with very high track numbers, and some
                # youtube shows post more than one show per day.

                # So the current solution is to make the day a disc number,
                # in hopes that all players handle 30-disc collections well,
                # and make the hour a track number. Even that results in duplicates
                # for some particularly prolific channels.

                track_date = arrow.get(entry["published"])
                album = track_date.format("YYYY-MM")
                disc = track_date.format("DD")
                track = track_date.format("HH")
                podcast_file.update(
                    {
                        "artist": feed["feed"]["title"],
                        "album": album,
                        "title": entry["title"],
                        "genre": "Podcast",
                        "date": track_date,
                        "disc": disc,
                        "track": track,
                    }
                )
                if icon_filename:
                    with open(icon_filename, "rb") as icon_file:
                        cover = icon_file.read()
                        cover = mediafile.Image(
                            data=cover,
                            desc="album cover",
                            type=mediafile.ImageType.front,
                        )
                        podcast_file.images = [cover]
                podcast_file.save()
            except (
                mediafile.FileTypeError,
                mediafile.MutagenError,
                mediafile.UnreadableFileError,
            ):
                # If MediaFile doesn't handle this file type, pretend nothing untoward is going on.
                pass

        else:
            # Else find it on disk.
            fitting_filenames = glob.glob(os.path.join(destination, f"{youtube_id}.*"))
            # If the file was deleted, skip creating output feed entry.
            if not fitting_filenames:
                warn(
                    f"{youtube_id} was downloaded before, but was since deleted, ignoring."
                )
                continue
            downloaded_filename = fitting_filenames[0]
            icons = glob.glob(
                os.path.join(destination, f"icon.{youtube_id}.*")
            )
            if len(icons) > 0:
                icon_filename = icons[0]
            click.echo(f"{youtube_id} already downloaded.")

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
        downloads = get_download_log()
        for youtube_id in downloads:
            if youtube_id not in youtube_identifiers:
                for name in glob.glob(
                    os.path.join(destination, f"{youtube_id}.*")
                ) + glob.glob(os.path.join(destination, f"icon.{youtube_id}.*")):
                    os.remove(name)


if __name__ == "__main__":
    run()  # pylint: disable=no-value-for-parameter
