#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import urlparse
import mimetypes
import glob

import os
import click
import feedparser
from feedgen.feed import FeedGenerator
import youtube_dl
from bs4 import BeautifulSoup
import requests

CDATA = "<![CDATA[{}]]>"


def fail(*objs):
    print("ERROR: ", *objs, file=sys.stderr)
    sys.exit(1)


def get_feed_icon(channel_page):
    # There is apparently no other way to get at it without a youtube API key, and I'd rather not mess with that.
    r = requests.get(channel_page)
    if not r.status_code == 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    icons = soup.find_all('img', class_='channel-header-profile-image')
    if icons:
        return icons[0]['src']
    return None


def get_channel_description(channel_page):
    r = requests.get(channel_page + '/about')
    if not r.status_code == 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    descriptions = soup.find_all('div', class_='about-description')
    if descriptions:
        return descriptions[0].encode_contents()
    return None


@click.command()
@click.argument('url')
@click.argument('root')
@click.option('--destination', '-d', default='.', help="Where to put output files")
@click.option('--limit', '-l', default=10, help="Number of recent videos to keep in the feed")
@click.option('--format', '-f', default='best',
              help="Preferred format option as per youtube-dl documentation. Use 'bestaudio/best' to download only audio.")
@click.option('--noblock', '-n', is_flag=True, default=False,
              help="Do not prevent the feed from being listed in iTunes podcast directory")
def run(url, root, destination, limit, format, noblock):
    feed = feedparser.parse(url)
    if feed['bozo']:
        fail("Could not parse feed from {}".format(url))

    if len(feed['entries']) < 1:
        fail("Channel appears to contain no videos.")

    if not feed.get('feed'):
        fail("Channel appears to contain no feed metadata")

    channel_page = feed['feed'].get('author_detail', {}).get('href', None)
    feed_icon = get_feed_icon(channel_page)
    channel_description = get_channel_description(channel_page)

    output = FeedGenerator()
    output.load_extension('podcast')

    output.id(feed['feed']['yt_channelid'])
    output.title(feed['feed']['title'])
    output.author({
        'name': feed['feed']['author'],
        'uri': feed['feed']['link']
    })

    if not noblock:
        output.podcast.itunes_block(True)

    if channel_description:
        output.description(CDATA.format(channel_description))
    else:
        output.description(u'{} Youtube Channel-as-Podcast. See {}'.format(feed['feed']['title'], channel_page))

    output.link(href=urlparse.urljoin(root, 'rss.xml'), rel='self')

    ydl_options = {
        'outtmpl': os.path.join(destination, '%(id)s.%(ext)s'),
        'download_archive': os.path.join(destination, 'download_log'),
        'format': format,
    }

    youtube_identifiers = []

    for entry in feed['entries'][0:limit]:
        youtube_id = entry['id'].split(':')[2]
        youtube_identifiers.append(youtube_id)
        video_url = "https://www.youtube.com/watch?v={}".format(youtube_id)

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(video_url, download=True)
            extension = info['formats'][
                next(index for (index, x) in enumerate(info['formats']) if x['format_id'] == info['format_id'])
            ]['ext']

        downloaded_filename = os.path.join(destination, "{}.{}".format(youtube_id, extension))
        output_entry = output.add_entry()
        file_url = urlparse.urljoin(root, youtube_id + '.' + extension)
        output_entry.id(file_url)
        output_entry.link(entry['links'])
        output_entry.title(entry['title'])
        output_entry.summary(CDATA.format(entry['summary'].replace('\n', '<br>')))
        output_entry.enclosure(file_url, str(os.path.getsize(downloaded_filename)), mimetypes.guess_type(file_url)[0])
        thumbnail = entry['media_thumbnail'][0]['url']
        if not feed_icon:
            feed_icon = thumbnail
        output_entry.podcast.itunes_image(thumbnail)
        output_entry.published(entry['published'])

    # The only way of getting the channel icon I could think of was scraping the youtube channel page.
    # This is fragile.
    output.podcast.itunes_image(feed_icon)
    output.rss_file(os.path.join(destination, 'rss.xml'))

    # Now clean the output directory of files previously downloaded but not in the feed.
    with open(os.path.join(destination, 'download_log'), 'r') as f:
        for line in f.readlines():
            if line.strip():
                id = line.split()[1]
                if id not in youtube_identifiers:
                    for name in glob.glob(os.path.join(destination, '{}.*'.format(id))):
                        os.remove(name)


if __name__ == '__main__':
    run()
