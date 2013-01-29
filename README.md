COBRO: A Comics Browser
=======================

CoBro is a very simple web browser designed to store and display
a list of web comics. It shows the user which comics have been
updated since they were last viewed. In general its aim is to make
it quick and simple to enjoy one's daily comics.

CoBro source can be viewed here: https://github.com/tallforasmurf/CoBro
That location also has a couple of lists of comics that CoBro can import.

Binary executables for Windows and Mac OS can be downloaded at
https://www.dropbox.com/sh/ovgn8muzrn5nsku/0x0KUtOPxo/CoBro
In case you got these from some other source, the md5 signatures are:

    cobro-mac.zip = 32381b38b58074a8d85f0d843990fe9f
    cobro-win.zip = 409dc800545ee194c149b6e06192fefd

The Inspiration: Comictastic
----------------------------

For years I've used the little app Comictastic 
(see http://spiny.com/comictastic/) to read
a couple dozen web comics daily. However, it has
drawbacks: it is difficult to configure new comics, and
it is no longer supported and isn't open-source
so it can't be forked and tinkered-with.

Most important, Comictastic is a web scraper:
it fetches only the image of the comic and doesn't render
any more of the comic's web page.
That's a drawback for the user and for the artists.
The comic artist loses out on visitor counts and on ad revenue.
The user loses out on HTML features
like the Red Button at SMBC,
or the title text that pops up when hovering the XKCD image,
or the previous/next/first nav links,
or links to a comic's About or Cast page.

A Specialty Browser
-------------------

I thought a long time about writing a better comic scraper,
but concluded that the right way to read web comics is to use a browser
to render the whole page.

However, a general-purpose browser is not
a good way to read comics because it lacks the three
best features of Comictastic:

* A scrolling list of names that can be clicked to show a comic instantly;

* It starts pre-loading comics as soon as the program launches;

* It displays comic names in bold to show an unread episode.

Also I don't want to mix 20+ comic bookmarks with all my
other browser bookmarks. An RSS reader
like Google Reader comes closer, but not all comics
have RSS feeds, and it is possible to read with even fewer
clicks in a special-purpose app.

So: A very simple web browser designed just for
reading web comics. Qt via PyQt gives me the materials to build this.

THE SPEC
========

CoBro (Comics Browser) is a simple app written in Python (2.6 or 2.7;
will move to 3.3 as soon as pyinstaller supports it), using
PyQt4 and Qt4 (Qt5 TBS).

CoBro provides a single window containing
a scrolling list of comic names on the left
and a large QWebView (browser) pane on the right.

The List
--------

The list of names supports multi-selection (shift-click, ctl-click)
and can be
reordered by dragging.
The font style of each name indicates that comic's status:

* Normal: comic available but it contents are unchanged from
the last time it was read.

* Bold: comic is available with contents that appear to be updated
since the last time.

* Italic: working: CoBro is trying to read this comic's page now.

* Strikethrough: an error occurred reading this comic.

Double-clicking a name opens a dialog to edit the name, URL,
and update schedule.

The Browser
-----------

The browser pane is a QWebView widget, a fully functional
browser based on WebKit.
The QWebview is configured to disable java
but to permit javascript and plug-ins, because
some comics require Flash.
The following keystrokes are implemented:

* Browser "back" on ctl/cmd-left, ctl/cmd-b, ctl/cmd-[

* Browser "forward" on ctl/cmd-right, ctl/cmd-]

* Font size zoom on ctl/cmd-plus, ctl/cmd-minus

* Copy selected text to clipboard on ctl/cmd-c


File Menu
---------

The only other controls are in the File menu:

* New Comic opens a dialog to define a comic by name, URL, and
update schedule, adding it to the list.

* Refresh (re)loads the source of the comic(s) currently
selected in the list.

* Delete deletes the selected comic(s) after getting an ok from the user.

* Export writes the selected comic(s) to a CSV text file,
including boilerplate text documenting the file format.

* Import reads a CSV file in the Export format and adds or
replaces the comics in the list.

* Quit (in Windows, clicking the dismiss button)
saves the list of comics and terminates.

Stored Data
-----------

With each name is associated these data:
* the comic's URL, e.g. "http://www.gocomics.com/stonesoup"

* the days of the week when it is scheduled to update (if known)

* an SHA-1 hash based on the last-read page of this comic

* the status of the comic: New, Old,
Bad (error reading URL) or Working (read in progress)

* after a refresh, the HTML contents read from the URL

When the user clicks on a comic name in the list,
the contents read from its URL are passed
to the QWebView for rendering.
This may take time if the page links numerous ads and images,
so a progress bar is displayed.


Refresh Operation
-----------------

When the app starts up it refreshes all comics automatically.
This and File>Refresh are the same:
The app passes the (selected) items to a separate QThread.
The thread processes comics one at a time:

* Set Working status (italic font on the name)

* Attempt to read the
source of the one page at the associated URL.

* If this times out or yields an error,
set error status (strikout font) and return.

* Save the text of the web page in memory for display
if the user clicks the comic.

* If update days are known for this comic, and if
this is not an update day, and an update day has not
elapsed since the comic was last read: set Old status and return.

* Compute a hash based on selected elements of 
the page and compare to the prior hash.

* If the hash is different, set New status (bold font),
else Old status (normal font).

Because refresh is in a separate thread, the user
can display and read comics while others are being refreshed.
The user can begin reading comics as soon as the first comic 
in the list has changed from Working (italic) font.

Shutdown Operation
------------------

On shutdown, Cobro stores the current window geometry, and
the name, URL, update days, and last hash value of each comic,
in the app settings.
Location of settings depends on the OS:

* Windows: Registry under Tassosoft/Cobro

* Mac OSX: ~/Library/Preferences/tassos-oak.com/Cobro.plist

* Linux: $HOME/.config/Tassosoft/Cobro.conf

