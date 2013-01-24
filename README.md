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
The md5 signatures are shown in that folder.

The Inspiration: Comictastic
----------------------------

For years I've used the little app Comictastic 
(see http://spiny.com/comictastic/) to read
a couple dozen web comics daily. However, it has
drawbacks: it is difficult and sometimes
impossible to configure new comics, and
it is no longer supported and isn't open-source
so it can't be forked and tinkered-with.

But mainly, Comictastic is a web scraper:
it fetches only the image of the comic and nothing else.
That creates drawbacks for
both the user and for the artists.
The comic author loses out on visitor counts and on ad revenue.
The user loses out on features 
provided by the full HTML page,
like the Red Button at SMBC, the
title text that pops up when hovering the XKCD image,
the previous/next/first/random nav buttons on most comics,
or links to a comic's About or Cast page.

I thought a long time about writing a better Comictastic,
but concluded that the right way to read web comics is to use a browser
to render the whole page.

A Specialty Browser
-------------------

However, a general-purpose browser is not
a good way to read comics. It is very convenient that Comictastic
(1) presents a scrolling list of names;
(2) Starts pre-loading comics as soon as the program launches;
and (c) Displays comic names in bold to show an unread episode.

In Chrome or Firefox, I'd have to use the browser's
bookmark manager, and reading through a list of comics would entail
many more clicks, and I'd have to look at many previously-read
ones because new ones aren't flagged. Or, I could use an RSS reader
like Google Reader (which I do use for blogs), but not all comics
have RSS feeds, and there are more clicks involved in getting at the 
content.

So: I want a small, simple web browser specially designed for
reading web comics, with full HTML support but with the convenience 
of Comictastic. Qt/PyQt gives me the materials to build this.

THE SPEC
========

CoBro (Comics Browser -- bro!) is a simple app written in Python (2.7,
but as soon as pyinstaller supports it I'll make it Python 3.3), using
PyQt4 and Qt4 (Qt5 TBS).

CoBro has a simple window with a scrolling list of names on the left
and a large QWebView widget on the right.
The window geometry is recorded at shutdown
using the QSettings facility, and restored at start-up.

All controls are in the File menu:

* New Comic opens a dialog to name a comic URL and add it to the list.

* Refresh (re)loads the source of the comic(s) selected in the list.

* Delete deletes the selected comic(s) after querying the user.

* Quit stores the list of comics and the window geometry in settings and terminates

The List
--------

The list is a list of comic names, e.g.
"SMBC", "Jesus and Mo", "Questionable Content" etc.

With each name is associated these data:

* a URL of a web comic, e.g. "http://www.gocomics.com/stonesoup"

* an SHA-1 hash based on the last-read page of this comic

* the status of the comic: New, Old (previously-read),
Bad (error reading URL) or Working (read in progress)

* the text contents last read from the comic web page

The font style of each item indicates its status:

* Normal: comic available but unchanged from last look

* Bold: a new comic is available

* Italic: working: CoBro is trying to read this comic's page now

* Strikethrough: an error occurred reading this comic

Display Operation
-----------------

When the user clicks on a comic name,
the text of its page is passed
to the QWebView for rendering.
This may take time if the page links numerous ads and images.
A progress bar keeps the user informed.

QWebview is configured to disable java
but to permit javascript and plug-ins, because
some comics require Flash.

After displaying a new comic, its status is set to not-new
and normal font.

Refresh Operation
-----------------

When the app starts up it refreshes all comics automatically.
This and File>Refresh operate the same:
The app goes through the (selected) items one at a time and for each it:

* Sets italic font on the name and attempts to read the source of the one page at the associated URL.

* If this times out or yields an error, sets error status and strikethrough font

* Else computes the hash of the just-read page and compares to the stored hash.

* If the hash is different, sets new comic status and bold font.

* Else sets normal font (no new comic)

* Stores the text of the web page in memory.

The refresh operation is done in a separate QThread so the user
can display and read comics while others are being updated.

Shutdown Operation
------------------

On shutdown,
store the name, URL, and last hash value or each comic in the app settings.
(Location of settings depends on the OS.)
