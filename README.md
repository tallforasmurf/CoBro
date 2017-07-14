COBRO: A Comics Browser
=======================

CoBro is a simple web browser designed to store and display a list of web comics. Its aim is to make it quick and simple to enjoy one's daily comics without needing to open the comics in a browser. It shows the user which comics have been updated since they were last viewed.

CoBro source can be viewed here: https://github.com/tallforasmurf/CoBro

That location also has a couple of lists of comics that you can import into CoBro to get started.

At the moment CoBro is Python source only. Hopefully soon it will be available for at least MacOS as a binary app.

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

The "hashing" lines show you the data that are being extracted and used to make the hash value that CoBro uses to tell when a comic is different from the last time it is read.

At present there is nothing much you can do with this information.

