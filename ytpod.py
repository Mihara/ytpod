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


def fail(*objs):
    print("ERROR: ", *objs, file=sys.stderr)
    sys.exit(1)


@click.command()
@click.argument('url')
@click.argument('root')
@click.option('--destination', '-d', default='.', help="Where to put output files")
@click.option('--limit', '-l', default=10, help="Number of recent videos to keep in the feed")
@click.option('--format', '-f', default='best',
              help="Preferred format option as per youtube-dl documentation. Use 'bestaudio/best' to download only audio.")
def run(url, root, destination, limit, format):
    feed = feedparser.parse(url)
    if feed['bozo']:
        fail("Could not parse feed from {}".format(url))

    if len(feed['entries']) < 1:
        fail("Channel appears to contain no videos.")

    if not feed.get('feed'):
        fail("Channel appears to contain no feed metadata")

    output = FeedGenerator()
    output.load_extension('podcast')

    output.id(feed['feed']['yt_channelid'])
    output.title(feed['feed']['title'])
    output.author({
        'name': feed['feed']['author'],
        'uri': feed['feed']['link']
    })
    output.link(href=urlparse.urljoin(root, 'rss.xml'), rel='self')
    output.description(u'{} Youtube-as-Podcast'.format(feed['feed']['title']))
    # TODO: More meta.

    ydl_options = {
        'outtmpl': os.path.join(destination, '%(id)s.%(ext)s'),
        'download_archive': os.path.join(destination, 'download_log'),
        'format': format,
    }

    youtube_identifiers = []
    feed_icon = None

    for entry in feed['entries'][0:limit]:
        youtube_id = entry['id'].split(':')[2]
        youtube_identifiers.append(youtube_id)
        video_url = "https://www.youtube.com/watch?v={}".format(youtube_id)

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(video_url, download=True)
            extension = info['formats'][
                next(index for (index, x) in enumerate(info['formats']) if x['format_id'] == info['format_id'])
            ]['ext']

        output_entry = output.add_entry()
        file_url = urlparse.urljoin(root, youtube_id + '.' + extension)
        output_entry.id(file_url)
        output_entry.link(entry['links'])
        output_entry.title(entry['title'])
        output_entry.summary(entry['summary'])
        output_entry.enclosure(file_url, 0, mimetypes.guess_type(file_url)[0])
        thumbnail = entry['media_thumbnail'][0]['url']
        if not feed_icon:
            feed_icon = thumbnail
        output_entry.podcast.itunes_image(thumbnail)
        output_entry.published(entry['published'])

    # It is unfortunately impractical to acquire a channel banner without getting an api id.
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
