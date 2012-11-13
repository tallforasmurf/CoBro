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
of Comictastic with easier configuration,
maybe with the ability also to display the navigation buttons
or the SMBC red button, etc. But finally I concluded
that the only equitable way to read web comics is to use a browser
to render the whole page. That's also the simplest way to do it
from both a coding standpoint (assuming one has access to a
web page renderer as a canned widget) and the
best from a usability standpoint:
no need to "configure" each comic, no need to worry about the
quirks of each comic's html code. Just get the URL and render the page.

A Specialty Browser
-------------------

However, a general-purpose browser like Firefox or Chrome is not
a good way to read comics either. I load 32 comics in Comictastic
now. It is very convenient that it:

* Presents these in a scrolling list of names;

* Starts pre-loading comics as soon as the program launches;

* Displays comic names in bold when there is an unread episode;

* Displays a comic quickly, with a single click on the name
or while scrolling the list of names with the arrow keys.

These conveniences are not available if I were to read the same list in
Chrome or Firefox. I'd have to use the browser's
bookmark manager, and reading through a list of comics would entail
many more clicks and some delay for each (because they aren't preloaded).

What I want is a small, simple web browser specially designed for
reading web comics with full HTML support but all the convenience 
of Comictastic. Qt/PyQt gives me the materials to build this.

THE SPEC
========

CoBro (Comics Browser -- bro!) is a simple app written in Python,
PyQt4, and Qt4, especially the QWebView widget.

CoBro has a simple window with a scrolling list of names on the left
and a large webview on the right. The window geometry is recorded in the
preferences (using the QSettings facility that lets the app store
settings values in platform-independent way).

All controls are in the File menu:

* New Comic opens a comic-creation dialog to name a comic URL and add
it to the list.

* Refresh All (re)loads the source of all comics

* Refresh Selected (re)loads the source of the comic(s) selected in the list

* Delete Selected deletes the selected comic(s) after querying the user.

* Quit stores the list of comics and the window geometry in settings and terminates

The List
--------

The list is a list of comic names, e.g. "SMBC", "Jesus and Mo", "Questionable Content" etc.

Each name is associated with these data:

* a URL of a web comic, e.g. "http://www.gocomics.com/stonesoup"

* an SHA-1 hash of the last-read page of this comic

* the status of the comic: no new comic, yes new comic, or error

* the text contents last read from the comic web page

The font style of each item indicates its status:

* Normal: no new comic

* Bold: a new comic is available

* Italic: CoBro is trying to read this comic's page now

* Strikethrough: an error occurred reading this comic.


Refresh Operation
-----------------

When the app starts up it performs File > Refresh All automatically.
This and Refresh Selected operate the same:

* The app goes through the (selected) items in the list one at a time from the top and on each it:

* Sets italic font on the name and attempts to read the source of the one page at the associated URL.

* If this times out or yields an error, set error status and strikethrough font

* Else compute the hash of the just-read page and compare to the stored hash.

* If the hash is different, set new comic status and bold font.

* Else set normal font (no new comic)

* Save the text of the web page in memory.

Display Operation
-----------------

When the user clicks on a comic name, pass the text of its page to the QWebView for rendering. (QWebView uses Webkit and is quite speedy.) This may take a moment if the page links numerous ads and images, but it will be quicker than the initial click on a browser bookmark.

QWebview will be configured to disable java and javascript, so no scripting, which will speed display. If some ads don't run as a result, that's too bad but no skin of my nose.

After displaying a new comic, set the status of that comic to not-new (and normal name font).

Shutdown Operation
------------------

On shutdown, store the each comic: name, URL, and last hash value -- in the app settings. Also the window geometry.

