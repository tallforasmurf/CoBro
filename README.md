COBRO: A Comics Browser
=======================

CoBro is a simple web browser designed to store and display
a list of web comics. It shows the user which comics have been
updated since they were last viewed. In general its aim is to make
it quick and simple to enjoy one's daily comics.

CoBro source can be viewed here: https://github.com/tallforasmurf/CoBro
That location also has a couple of lists of comics that CoBro can import.

At the moment CoBro is Python source only. Hopefully soon
it will be available for at least MacOS as a binary app.

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
That's a drawback;
the comic artist loses out on visitor counts and ad revenue,
and the user loses out on features
like the Red Button at SMBC,
or the title text that pops up when hovering the XKCD image,
or the nav. links previous/next/first, About or Cast.

Comics Need a Specialty Browser
-------------------

I thought a long time about writing a better comic scraper,
but concluded that the right way to read web comics is to use a browser
to render the whole page.

However, a general-purpose browser is not
a good way to read comics because it lacks the three
best features of Comictastic:

* A list of names that can be clicked to show a comic instantly;

* Pre-loading comics as soon as the program launches;

* Comic names in bold to show an unread episode.

Also I don't want to mix 20+ comic bookmarks with all my
other browser bookmarks. An RSS reader works, but not all comics
have RSS feeds, and it is possible to read with even fewer
clicks in a special-purpose app.

So: A very simple web browser designed just for
reading web comics. Qt via PyQt has the materials to build this.

THE SPEC
========

CoBro (Comics Browser) is a simple app written in Python 3.3,
PyQt5 and Qt5.2.

CoBro provides a single window containing
a scrolling list of comic names on the left
and a QWebView (browser) pane on the right.

The List
--------

The list of names supports multi-selection (shift-click, ctl-click)
and can be
reordered by dragging.
The font style of each name indicates that comic's status:

* Normal: comic available but its contents are unchanged from
the last time it was read.

* Bold: comic is available with contents that appear to be updated
since the last time.

* Italic: working: CoBro is trying to read this comic's page now.

* Strikethrough: an error occurred reading this comic.

Double-clicking a name opens a dialog to edit the name and URL.

The Browser
-----------

When the user clicks on a comic name in the list,
the contents read from its URL are passed
to the browser panel for rendering.
If there was an error reading the comic, an
explanatory error message is displayed instead.

Rendering may take time if the comic links to numerous ads and images,
so a progress bar is displayed.

The browser panel is a QWebEngineView widget, a fully-functional
browser first available in Qt5.4. This is used because the QWebKit
browser used in the first version displayed many annoying bugs that
were not possible to work around.

However because QWebEngine is in an early state, all of the following
features that were possible with QWebKit are no longer offered.
There is no support for any keystrokes nor for a custom context menu.
There is no restriction on Java, and browsing
is not "private" i.e. the residue of one's comic reading in the form
of cookies and other detritus may remain in one's Chrome browser history.

<del>The browser pane is a QWebView widget, a fully functional
browser based on WebKit. When the app starts up, a welcome
message with how-to-use text is displayed.</del>

<del>The QWebview is configured to disable java
but to permit javascript and plug-ins, because
some comics require scripts and Flash.</del>

<del>The following keystrokes are implemented:</del>

<del>* Browser "back" on ctl/cmd-left, ctl/cmd-b, ctl/cmd-[</del>

<del>* Browser "forward" on ctl/cmd-right, ctl/cmd-]</del>

<del>* Font size zoom on ctl/cmd-plus, ctl/cmd-minus</del>

<del>* Copy selected text to clipboard on ctl/cmd-c</del>

<del>Using a "back" key from the first page of a comic brings back
the display of the welcome message.</del>

<del>The user can ctl/cmd-click on any link to bring up a context menu
with the options "Copy link to clipboard" and "Open link in
default browser". This allows an easy escape for
example to bring up the Archives or About link of a comic
in a "real" browser.</del>

File Menu
---------

The only other controls are in the File menu:

* New Comic opens a dialog to define a comic by name and URL,
adding it to the end of the list.

* Refresh (re)loads the source of the comic(s) currently
selected in the list.

* Delete deletes the selected comic(s)
after getting an ok from the user.

* Export writes the selected comic(s) to a UTF-8 text file in CSV format,
including boilerplate text documenting the file format.

* Import reads a UTF-8 file of CSV data in the Export format and adds or
replaces the comics in the list.

* Quit (in Windows, clicking the dismiss button)
saves the list of comics and terminates.

Stored Data
-----------

With each name is associated these data:
* the comic's URL, e.g. "http://www.gocomics.com/stonesoup"

* an SHA-1 hash based on the last-read page of this comic

* the status of the comic: New, Old,
Bad (error reading URL) or Working (read in progress)

* after a refresh, the HTML contents read from the URL

* after a failed refresh, a character string describing the error


Refresh Operation
-----------------

When the app starts up it refreshes all comics automatically.
This and File>Refresh are the same:
The app queues the (selected) comics for processing by
a separate QThread.
The thread processes comics one at a time as follows:

* Set Working status (italic font on the name)

* Attempt to read the
source of the one page at the associated URL.

* If this times out or yields an error,
set error status (strikout font), store an error string,
and return.

* Save the text of the web page in memory for display
if the user clicks the comic.

* If update days are known for this comic,
_and_ if this is not an update day,
_and_ an update day has not elapsed since the comic was last read:
set Old status and return.

* Compute a hash based on selected elements of 
the page and compare to the prior hash.

* If the hash is different, set New status (bold font),
else Old status (normal font).

Because refresh is in a separate thread, the user
can display and read comics while others are being refreshed.
The user can begin reading comics as soon as the first comic 
in the list has changed from Working (italic) font to normal
or bold font.

Shutdown Operation
------------------

On shutdown, Cobro stores the current window geometry, and
for each comic its name, URL, and last hash value.
These data go into the app settings.
The location of settings depends on the OS:

* Windows: Registry under Tassosoft/Cobro

* Mac OSX: ~/Library/Preferences/tassos-oak.com/Cobro.plist

* Linux: $HOME/.config/Tassosoft/Cobro.conf

