# ytpod

This is a trivial _(at the moment)_ youtube channel downloader that produces a 
directory, containing two useful things: A bunch of video _(or audio, if desired)_ files, and an
xml file that presents them as an RSS feed suitable for downloading by podcast listening applications. Just
grab your OPML file from Youtube subscription management page, find the feed URL for the channel you want from there,
and give it to ytpod. Make the directory you download the channel into accessible from your web server
_(you do need a web server)_ and give the URL of the xml file to your podcatcher, and you're done.
Run at regular intervals as appropriate for each youtube channel that you wish to download in this manner.

I made this for my own use, because, while Android has some excellent podcatching applications, few, if any, of them
can download Youtube channels for later viewing offline. This downloader permits them to do it, at the cost of keeping a
cache on your own web server.

## Installation

Something to the tune of 

    pip install -e git+https://github.com/mihara/ytpod@master#egg=ytpod

While it should be perfectly possible to produce Windows binaries, I hardly see the need when there are better
alternatives available for that use case. I'll see about a PyPi release once I figure out how to get channel metadata
without actually requiring a YouTube API key.

## Command line arguments

    ytpod <youtube feed url> <your website root for the podcast>
    
The feed URL is what you get from the OPML file. You must give the website root URL with a trailing slash. The feed URL
that you should give to your podcatcher is `<website root>/rss.xml`
    
Options:

* **--destination** | **-d** -- Output directory for the files and the XML file of the feed. Defaults to current directory.
* **--format** | **-f** -- Output format as per youtube-dl options. Use `bestaudio/best` to produce audio only files.
* **--limit** | **-l** -- Maximum number of files to keep on disk. Defaults to 10. Every previously downloaded file
  *(youtube IDs are logged into `download_log` in the target directory)* that no longer fits into the feed is
  automatically deleted.

## Troubleshooting

At the moment, the script includes almost no error checking of any kind. The most likely spot to break, however, will
always be the YouTube download itself, to rectify which you will need to make sure a fresh version of youtube-dl is
installed with `pip install --upgrade youtube-dl`.
  
## License

This program is licensed under the terms of GNU GPL version 3 license.

Pull requests and improvements are quite welcome, I know it's far from foolproof, it's just something cooked up quickly
to scratch an itch one monday morning.

