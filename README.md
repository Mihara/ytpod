# ytpod

This is a trivial _(at the moment)_ youtube channel downloader that produces a
directory, containing two useful things: A bunch of video _(or audio, if
desired)_ files, and an xml file that presents them as an RSS feed suitable
for downloading by podcast listening applications. Just grab your OPML file
from Youtube subscription management page, find the feed URL for the channel
you want from there, and give it to ytpod. Make the directory you download the
channel into accessible from your web server _(you do need a web server)_ and
give the URL of the xml file to your podcatcher, and you're done. Run at
regular intervals as appropriate for each youtube channel that you wish to
download in this manner.

An alternative use is to save the files and feed them to
[Navidrome](https://navidrome.org) as if they were music -- when using audio
files mode, the appropriate tags are applied to media files to make it easy to
sort them.

I made this for my own use, because, while Android has some excellent
podcatching applications, few, if any, of them can download Youtube channels
for later viewing offline. This downloader permits them to do it, at the cost
of keeping a cache on your own web server.

## Installation

Something to the tune of 

    pip install git+https://github.com/mihara/ytpod@master#egg=ytpod

While it should be perfectly possible to produce Windows binaries, I hardly
see the need when there are better alternatives available for that use case.

You also require an installation of youtube-dl or yt-dlp -- whichever works
best for you -- accessible as `youtube-dl` in PATH.

The project is set up to use [shiv](https://shiv.readthedocs.io/en/latest/index.html)
and produce quasi-standalone executables. To produce one yourself, check out `build.sh`.

## Command line arguments

    ytpod <youtube feed url> <your website root for the podcast>
    
Getting the feed URL has become harder over the years. Previously, YouTube
allowed you to export an OPML file. Now you have to [do a complicated
dance](https://greasyfork.org/en/scripts/418574-export-youtube-subscriptions-to-rss-opml)
to get it. Straight channel URLs instead of the feed URL are also supported
for convenience, but may abruptly stop working when YouTube changes something
again.

You must give the website root URL with a trailing slash. The feed URL that
you should give to your podcatcher is `<website root>/rss.xml`
    
Options:

* **--destination** | **-d** -- Output directory for the files and the XML file
  of the feed. Defaults to current directory.
* **--format** | **-f** -- Output format as per youtube-dl options. Use
  `bestaudio/best` to produce audio only files.
* **--keep-video** -- By default, ytpod will attempt to produce audio, rather
  than video files. This may not be what you want, hence this option.
* **--limit** | **-l** -- Maximum number of files to keep on disk. Defaults
  to 10. Every previously downloaded file *(youtube IDs are logged into
  `download_log` in the target directory)* that no longer fits into the feed
  is automatically deleted.
* **--noblock** | **-n** -- Do not add a marker that prevents the podcast from
  showing up in iTunes podcast directory _(It is assumed by default that this
  is your private feed and you do not wish it to be publicized.)_
* **--proxy** -- Use a proxy, presumably a socks proxy. `socks5://localhost:port`
  or something like that. Getting around censorship in the first place is left
  as an exercise for the user.

## Troubleshooting

This is not a very robust program, not by my standards. The most likely spot
to break is the fact that as of this moment I don't have an idea on how to
acquire channel description and icon from YouTube without an API key, _(This
script hardly merits an API key)_ so I'm scraping the relevant pages for data
instead. While the data is extracted from meta tags used for embedding YouTube
in other sites, which are liable to stick around, in *some* cases this may be
impeded by a webpage asking the user to consent for cookies, and I'm not sure
the way to bypass that will keep working forever.

## License

This program is licensed under the terms of GNU GPL version 3 license.

Pull requests and improvements are quite welcome, I know it's far from
foolproof, it's just something cooked up quickly to scratch an itch one Monday
morning.

