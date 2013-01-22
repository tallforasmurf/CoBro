COBRO: A Comics Browser
=======================

The Inspiration: Comictastic
----------------------------

For years I've used the little app Comictastic 
(see http://spiny.com/comictastic/) to read
a couple dozen web comics daily. However, it has
several drawbacks:

* It is no longer supported and isn't open-source so it can't be forked;

* It is difficult to configure new comics;

* Sometimes it is impossible to make a comic work;

* It is a web scraper, it fetches only the image of the comic and nothing else.

The last point is the most important. It creates drawbacks for
both the user and for the authors of the comics.

The user loses out on features 
provided by the full HTML page of the typical comic,
for example:

* the Red Button on every SMBC comic;

* the title that pops up when hovering the XKCD image;

* the previous/next/first/random navigation buttons on most comics;

* easy linking to the comic's back-story or character lists.

The comic authors lose out because a source download
by Comictastic isn't a "visit" in web terms, so they
lose out on visitor counts and on ad revenue.

I thought a long time about making a better version
of Comictastic, but finally concluded
that the right way to read web comics is to use a browser
to render the whole page. All the user has to configure
is the comic's URL. Then just get the html and render the page.

A Specialty Browser
-------------------

However, a general-purpose browser is not
a good way to read comics. It is very convenient that Comictastic:

* Presents a scrolling list of names;

* Starts pre-loading comics as soon as the program launches;

* Displays comic's names in bold when there is an unread episode;

These conveniences are not available reading the same comics in
Chrome or Firefox. I'd have to use the browser's
bookmark manager, and reading through a list of comics would entail
many more clicks and some delay because they aren't preloaded.

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

Shutdown Operation
------------------

On shutdown,
store the each comic: name, URL, and last hash value -- in the app settings.
Also the window geometry.

