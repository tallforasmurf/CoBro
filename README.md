COBRO: Abandoned Project
=======================

CoBro was a simple web browser designed to store and display a list of web comics. Its aim was to make it quick and simple to enjoy one's daily comics without needing to open the comics in a browser. It shows the user which comics have been updated since they were last viewed.

Project Abandonment
-------------------

After working on Cobro, and using it myself, for several years, I have decided to give up on it. The combination of PyQt5 and QtWebEngine are just unmanageable and untrustworthy. I have never succeeded in getting Cobro packaged using any of the Python packagers, CxFreeze, Py2app, or PyInstaller -- even after devoting many volunteer hours to assisting the development of PyInstaller.

There are other intractable issues, for example the frequent failures of fake-useragent to initialize; the frequent problems with mismatched levels of ssl security causing comics to not load; the many crazy ways comic sites have of coding that causes uncatchable false-positive; unannounced changes in the way PyQt5 is distributed; and on and on.

Most recently when I attempted to upgrade to the latest level of PyQt5 and QtWebEngine, the new browser module just doesn't display correctly. Something has changed, perhaps there is a setting I could tweak, but you know what? Fuck it.

I have switched my personal web-comic reading to the use of an RSS reader (Reeder). That meant dropping a couple of comics of which I was fond because they don't provide RSS or Atom feeds. Tough. I'm moving on.

The remainder of this README is kept to provide orientation in case anyone else is fool enough to try to pick this project up. My best wishes go with you.

The Inspiration: Comictastic
----------------------------

For years I used the little app Comictastic (see http://spiny.com/comictastic/) to read a couple dozen web comics daily. However, it has drawbacks: it is difficult to configure new comics, and it is no longer supported and isn't open-source so it can't be forked and tinkered-with.

Most important, Comictastic is a web scraper: it fetches only the image of the comic and doesn't render any more of the comic's web page. That means the comic artist loses out on visitor counts and ad revenue, and the user loses out on features like the Red Button at SMBC, or the title text that pops up when hovering the XKCD image, or the typical buttons to read the previous/next comic, or the artist's About page.

These problems are avoided if we use a browser to render the whole page. However, a general-purpose browser lacks the three best features of Comictastic:

* A list of names that can be clicked to show a comic instantly;

* Pre-loading comics as soon as the program launches;

* Comic names in bold to show an unread episode.

Also I don't want to mix 20+ comic bookmarks with all my other browser bookmarks. An RSS reader might be an option but not all comics have RSS feeds, and it is possible to read with even fewer clicks in a special-purpose app.

So: CoBro (Comics Browser) to provide a single window containing a scrolling list of comic names on the left and a web browser pane on the right.

Cobro is written in Python 3.x and PyQt/Qt (currently at release 5.9).

The List
--------

At the left of the CoBro window is the list of comic names. It supports multi-selection (shift-click, ctl-click) and can be reordered by dragging. The font style of each name indicates that comic's status:

* Normal: comic available but its contents are unchanged from the last time it was read.

* Bold: comic is available with contents that appear to be updated since the last time.

* Italic: working: CoBro is trying to read this comic's page now.

* Strikethrough: an error occurred reading this comic.

Double-clicking a name opens a dialog to edit the name and URL.

The Browser
-----------

On the right of the window is the display of the currently selected comic. When the user clicks on a comic name in the list, the contents read from its URL are passed to the browser panel for rendering. If there was an error reading the comic, an explanatory error message is displayed instead.

Rendering may take time if the comic links to numerous ads and images, so a progress bar is displayed.

The browser panel is a QWebEngineView widget, a fully-functional browser. Clicking a link in the comic page will usually cause that link to be loaded. You can control-click on a link to copy the link to the clipboard. (Do this to open some linked page in a regular browser.) There is no restriction on Javascript, and browsing is not "private" i.e. the residue of one's comic reading in the form of cookies and other detritus may remain on one's computer.

File Menu
---------

The only other controls are in the File menu:

* New Comic opens a dialog to define a comic by name and URL, adding it to the end of the list. If there is a URL on the system clipboard, it is filled in to the dialog for you.

* Refresh (re)loads the source of the comic(s) currently selected in the list. If no comic is selected, all comics are refreshed.

* Delete deletes the selected comic(s) after getting an ok from the user.

* Export writes the selected comic(s), or all comics, to a UTF-8 text file. The name and URL of each comic are written in CSV format, plus some boilerplate text documenting the file format.

* Import reads a UTF-8 file of CSV data in the Export format and adds or replaces the comics in the list.

* Quit (in Windows, clicking the dismiss button) saves the list of comics and terminates.

In-memory Data
-----------

With each comic's name is associated these data:

* the comic's URL, e.g. "http://www.gocomics.com/stonesoup"

* an SHA-1 hash based on the last-read page of this comic

* the status of the comic: New, Old, Bad (error reading URL) or Working (read in progress)

* after a refresh, the HTML contents read from the URL

* after a failed refresh, a character string describing the error


Refresh Operation
-----------------

When the app starts up it refreshes all comics automatically. This and File>Refresh are the same: The app queues the (selected) comics for processing by a separate QThread. The thread processes comics one at a time as follows:

* Set Working status (italic font on the name in the list).

* Attempt to read the source of the one page at the associated URL.

* If this times out or yields an error, set error status (strikout font), store an error string, and return.

* Save the text of the web page in memory for display if the user clicks the comic.

* Compute a hash based on selected elements of the page and compare to the prior hash.

* If the hash is different, set New status (bold font), else Old status (normal font).

Because refresh is in a separate thread, the user can display and read one comic while others are being refreshed. The user can begin reading comics as soon as the first comic in the list has changed from Working status (italic font).

Shutdown Operation
------------------

On shutdown, Cobro stores the current window geometry, and for each comic its name, URL, and last hash value. These data go into the app settings. The location of settings depends on the OS:

* Windows: Registry under Tassosoft/Cobro

* Mac OSX: ~/Library/Preferences/tassos-oak.com/Cobro.plist

* Linux: $HOME/.config/Tassosoft/Cobro.conf

About "Unread" Status
---------------------

CoBro decides that a comic is probably unread, and makes it bold in the list, when the contents of the comic appear to be different from the last time it was refreshed. This is done by forming a hash based on elements of the web page as read from the comic URL.

The only elements that go into the hash are the `src=` attributes of its `<img` statements. In most comic web pages, the only image that changes from time to time is the image of the comic itself. So when the actual comic image changes, the hash will vary from the prior time, and CoBro will mark the comic bold meaning unread.

Almost all comic pages include image elements other than the comic itself, and these can change. In particular, images related to advertisements are often different every time a URL is fetched, without regard for whether the comic itself is different. This causes "false positive" tests: comics that are marked Unread and when you click them, it's the same comic as last time.

CoBro deals with many of these by having a "stop list" for certain strings that appear in  advertisements. Images whose sources contain one of these strings are not included in the hash. (See the code for `self.blacklist` around line 570 of the file.) This list prevents many false positives. Please open an issue if you know of another string that should be added to the blacklist.

Sadly, a few comics do things in a way that a blacklist can't help. In particular, Jesus and Mo and Savage Chickens both have the awkward habit of occasionally **not** loading an image that they loaded a prior time. There's no obvious reason they would load it one time and not the next -- it is not an ad -- but they do that, and it causes the hash to differ when the comic image is not changed.


Command-line arguments
-----------------------

If you start CoBro by double-clicking an app, there is no opportunity to enter command line arguments, and it runs with the defaults. However if you can launch it from the command line you can supply these arguments:

* `--level [ERROR | INFO | DEBUG]` Level of detail to write to the log file, default is ERROR.

* `--logfile filepath` A writeable text file to receive log data, default stderr (which is discarded when launched as a GUI).

* `--logitem name [,name]...` Name or name fragment of one or more comics to be documented to the log file. Forces `--level INFO`.

When you log a comic by name, for example `--logitem xk` to log the XKCD comic, CoBro writes several lines to the log file whenever it refreshes that comic. For example you might see,

    INFO:root:Reading comic XKCD
    INFO:root:  hashing: b'/s/0b7742.png'
    INFO:root:  hashing: b'//imgs.xkcd.com/comics/particle_properties.png'
    INFO:root:  hashing: b'//imgs.xkcd.com/s/a899e84.jpg'
    INFO:root:XKCD appears to be unread

The "hashing" lines show you the data that are being extracted and used to make the hash value that CoBro uses to tell when a comic is different from the last time it is read. You can use this to diagnose false positive "unread" status.


