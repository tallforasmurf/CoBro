# le passe-partout (boilerplate)
__version__ = "2.0.0"
__author__  = "David Cortesi"
__copyright__ = "Copyright 2012, 2013, 2014 David Cortesi"
__maintainer__ = "who indeed"
__email__ = "tallforasmurf@yahoo.com"
__status__ = "first-draft"
# le permis
__license__ = '''
 License (GPL-3.0) :
    This file is part of CoBro.

    CoBro is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY and without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You can find a copy of the GNU General Public License at:
    <http://www.gnu.org/licenses/>.
'''
# le chaîne d'informations (doc-string)
'''
CoBro (Comic Browser) is a minimal web browser designed for convenient
reading of Web Comics. The main window has a list of comic names on the left
and a web page display on the right.

Associated with each comic in the list are these persistent items:

  * the user-selected name

  * the user-provided URL of the comic

  * an SHA-1 hash based on the contents of the page at the URL, as it
    was when the comic was last displayed to the user

These items are saved at shutdown and reloaded at startup.

Also associated with each comic but created dynamically as the program runs:

  * the contents of the page at the comic URL

  * an SHA-1 hash based on the contents of the page at the URL, as it
    was read now, since the program started up.

  * a status, one of:

     - comic has not been displayed since it was read (NEWCOMIC)
       i.e., the saved hash is not equal to the new hash.

     - comic has been read and displayed to the user (OLDCOMIC)
       i.e. the saved and latest hash values are the same

     - comic page is being read from its URL (WORKING)

     - error on http request or load, no data (BADCOMIC)

All these data are maintained in memory as a list of Comic objects. The list
is displayed to the user using the Qt model/view classes: The model is the
Python list of Comic objects; a QListView derivative displays the list.

The comic names in the list are shown in different fonts to reflect the
status: normal for been-displayed, bold for not-yet-displayed, italic for
being-read, and strikeout for error.

When the user clicks on a comic in the list, the text of that comic's URL
page is loaded into the web page display with QWebView::setHTML(), where it
is rendered. The displayed page can be used as in any browser, e.g. the user
can click on buttons and follow links in the page. Javascript is allowed
(some comics need it, e.g. the SMBC "red button" does), but java is not.
Browsing is "private," no cookies or caches are kept.

The list supports the following operations:

  * single-click an item to select and display that comic in the web display

  * drag and drop selected items to reorder the list

  * double-click an item to open an Edit Comic dialog which permits
        editing the name and URL.

There is a single menu, the File menu, with these commands:

  * New Comic
        opens a dialog to collect the name and URL of a new comic,
        which is added to the list at the bottom.

  * Refresh
        Apply refresh to the comics selected in the list if any, or to
        all if no selection. The refresh operation is described below.

  * Delete
        After querying for OK, delete the selected comics (if any).

  * Quit
        Save the persistent comic values in QSettings and terminate.

Refresh operation:

When the app loads, or when File>Refresh is chosen, or when the URL of a
comic is edited, the app pushes the model index of all, or selected, or the
edited Comic onto a queue and triggers a QSemaphore. A separate QThread waits
on the semaphore. While there is work on the queue it

* pops the next model index qmi from the queue and:

* signals statusChanged(qmi, WORKING),

* initiates a page-load from the item's URL, saving the text
  in the Comic object,

* if the load ends in error it signals statusChanged(qmi, BADCOMIC)

* else it computes the hash based on the loaded page and saves it
  in the Comic object as new_hash.

* if the new_hash is the same as the saved hash, it signals
  statusChanged(qmi, OLDCOMIC)

* else the new hash is different, the user hasn't seen this comic, so
  it signals statusChanged(qmi, NEWCOMIC)

The statusChanged signal goes to a slot in the list model which updates the
status of the item and calls dataChanged(), with the result that the list view
will call data() for new display data -- resulting in a change of font in
the displayed name of the comic.

In this way, shortly after launching, the user has a list of comics ready
to be read, with the ones yet-unseen in bold.
'''

'''
Acknowledgements and Credits

First thanks to the Van Tols of spiny.com who created Comictastic, of which
I was a long-time user and from which I've stolen all the ideas herein.

Second to Mark Summerfield for the book "Rapid GUI Development with PyQt"
which really could be called "be an instant Qt expert in 8 hours of reading."
'''

import collections # for deque
import hashlib # for sha-1
import urllib.request # for reading URLs, eh?
import urllib.error # for except statements
import webbrowser # for platform-independent access to system default browser
import re # regular expressions
import os # getcwd
import io # stringIO
from html.parser import HTMLParser # see MyParser below

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget
)
from PyQt5.QtCore import (
    pyqtSignal,
    QAbstractListModel,
    QModelIndex,
    QMutex,
    QPoint,
    QSettings,
    QSize,
    Qt,
    QThread,
    QUrl,
    QWaitCondition
)
from PyQt5.QtGui import (
    QFont, QFontInfo,
    QKeySequence
)
from PyQt5.QtWebKit import (
    QWebSettings
)
from PyQt5.QtWebKitWidgets import (
    QWebPage,
    QWebView
)
import PyQt5.QtNetwork
import PyQt5.QtPrintSupport

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# some global constants
#
URLTIMEOUT = 8 # timeout in seconds for urllib.urlopen
GLOBALTIMEOUT = 10.0 # socket.setdefaulttimeout value
# The status values of a comic.
OLDCOMIC = 0 # status of previously-seen comic
NEWCOMIC = 1 # status of an un-viewed comic (name in bold)
BADCOMIC = 2 # status when URL couldn't be read (name strikethrough)
WORKING = 3  # status while reading a url (name in italic)
# four QFonts ordered by the codes above
FONTLIST = [None, None, None, None]
# the user agent string returned from QWebPage::userAgentForUrl(),
# converted to a python string -- see main code far below.
USERAGENT = u''

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Find out the nearest font to Comic Sans and store four versions of it in
# FONTLIST for use in displaying the comic names in ConcreteListModel.data().
# Called only from the main code during startup.

def setup_jolly_fonts():
    global FONTLIST

    qf = QFont()
    qf.setStyleStrategy(QFont.PreferAntialias+QFont.PreferQuality)
    # we may or may not get Comic Sans, but something sans-serif
    qf.setStyleHint(QFont.SansSerif)
    # ask for the most appropriate font
    qf.setFamily(u'Comic Sans')
    qf.setPointSize(16)
    qf.setWeight(QFont.Normal)
    qf.setStyle(QFont.StyleNormal)
    # qf is a QFont based on (probably) Comic Sans:
    # copy it as the old/normal font
    FONTLIST[OLDCOMIC] = QFont(qf)
    # copy it as the new/bold font
    FONTLIST[NEWCOMIC] = QFont(qf)
    FONTLIST[NEWCOMIC].setWeight(QFont.Bold) # ..and make it so
    # copy as the working/italic font
    FONTLIST[WORKING] = QFont(qf)
    FONTLIST[WORKING].setItalic(True) # and make it so
    # copy as the error/strike font
    FONTLIST[BADCOMIC] = QFont(qf)
    FONTLIST[BADCOMIC].setStrikeOut(True) # and make that true

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Four boiler-plate messages that are pushed into the web page display
# from time to time.
#
# The html for the welcome screen shown on startup.
#
WELCOME_MSG = '''
<div style='text-align:center; height:6em; background-color:#444; color:#E0E; border:2px solid black;'>
<h2>Welcome to CoBro!</h2>
<p style='font-size:smaller;'>Version 2.0.0 30 Jan 2014</p>
</div>
<p>Single-click a comic name to display its page in this browser.</p>
<p>No comics in the list? Use File&gt;New Comic
to add a comic by name and URL.
Start by adding some of these nerd favorites!
Drag to select one the URLs;
then key ctl-c or right-click to copy (mac: cmd-c or ctl-click);
then select File&gt;New Comic, and fill in its name.</p>
<table style='border-collapse:collapse; width:80%;margin:auto;'>
<tr><td>Comic name</td><td>Comic URL</td></tr>
<tr><td>XKCD</td><td>http://xkcd.com/</td></tr>
<tr><td>Bug Comic</td><td>http://www.bugcomic.com</td></tr>
<tr><td>PhD Comics</td><td>http://www.phdcomics.com/comics.php</td></tr>
<tr><td>Megacynics</td><td>http://www.megacynics.com/</td></tr>
<tr><td>Penny Arcade</td><td>http://www.penny-arcade.com/comic</td></tr>
<tr><td>Foxtrot</td><td>http://www.foxtrot.com/</td></tr>
</table>
<p>That's enough! There are <i>thousands</i> of web comics out there!
The ones above are of the daily-joke variety, but there are also
richly-drawn graphic novels and everything in between.
For U.S. syndicated (newspaper) cartoons, try
<a href='http://comics.com/'>Comics.com</a> or check the website of your
regional newspaper under "Entertainment". For independent comics, try
<a href='http://thehiveworks.com/'>Hiveworks</a> or <a href='http://new.belfrycomics.net/'>The
Belfry</a> list.</p>
<p>To "refresh" a comic means to read its web page and see if it is
different from the last time. All comics are refreshed when the app starts!</p>
<ul><li>While we are reading its page, a comic's name is <i>italic</i>.</li>
<li>After reading, if the comic looks different from the last time you viewed it,
its name turns <b>bold</b>. (Sometimes this just means a change of
ad copy or user comments.)</li>
<li>If there was a problem reading it, its name is <strike>lined-out</strike>.
Click on it to see the error message.</li>
</ul>
<p>Use File&gt;Refresh to refresh a new or edited comic, or to retry one with an error.
When all refreshes are finished, you can rearrange the list order
by dragging and dropping. Double-click a comic
to edit its name and URL.</p>
<p>While browsing, use ctl-[ for "back" and ctl-] for "forward"
(cmd-[ and cmd-] on a mac). If you right-click on a link (mac: ctl-click),
you get a context menu that you can use to copy the link or open it in
your system default browser.</p>
<p>When you quit the app, it saves the
comic definitions in some magic settings place, depending your OS
(Registry, Library/Preferences, ~/.config).</p>
<p>Use File&gt;Export to write definitions of the selected comics to a UTF-8 text file.
Use File&gt;Import to read definitions from a UTF-8 text file and add them to the list
(or to replace them, when the name's the same). For the import file format,
export one comic and look at that output.</p>
<p>That's it! Enjoy! Oh wait -- read the license!</p>
<hr /><p>License (GPL-3.0):
CoBro is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version. This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You can find a copy of the GNU General Public License at:
<a href='http://www.gnu.org/licenses/'>www.gnu.org/licenses/</a>.</p>
'''
#
# Text displayed when a page could not be read. {0} is filled with the
# Comic.error string.
#
ERROR_MSG = '''
            <p style='text-align:center;margin-top:8em;'>
            Sorry, there was some problem reading the URL for that comic.<br />
            ({0})<br />
            Try refreshing it or test its URL in another browser.</p>'''
#
# Text displayed when the comic is has not yet been read
#
UNREAD_MSG = '''<p style='text-align:center;margin-top:8em;'>
Sorry, I have no data for this comic. Try refreshing it.</p>'''
#
# Text displayed when the comic is now being read
#
READING_MSG = '''
            <p style='text-align:center;margin-top:8em;'>
            I'm working on it, alright? Geez, gimme a sec...</p>'''
#
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Boilerplate text written to the top of any Exported text file.
#
EXPORTBUMF = '''
# A comic file is a latin-1 (ISO-8892-1) or ASCII file. In it, each
# comic is defined on a single line by two quoted strings.
# The first string is the comic name. The second string is its URL.
# Example: 'Bug Comic', 'http://www.bugcomic.com'
# The strings are delimited by 'single' or "double" quotes (sorry no guillemets)
# and separated by spaces and/or commas. All lines that don't match
# that format are ignored, and can be used as commentary, like these lines.
'''

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Some message routines.

# Create and run a QMessageBox (inner method)

def makeMsg ( text, icon, info = None):
    mb = QMessageBox( )
    mb.setText( text )
    mb.setIcon( icon )
    if info is not None:
        mb.setInformativeText( info )
    return mb

# Display a modal info message, blocking until the user clicks OK.
# No return value.

def infoMsg ( text, info = None ):
    mb = makeMsg(text, QMessageBox.Information, info)
    mb.exec_()

# Display a modal warning message, blocking until the user clicks OK.
# No return value

def warningMsg ( text, info = None ):
    mb = makeMsg(text, QMessageBox.Warning, info)
    mb.exec_()

# Display a modal query message, blocking until the user clicks OK/Cancel
# Return True for OK, False for Cancel.

def okCancelMsg ( text, info = None ):
    mb = makeMsg ( text, QMessageBox.Question, info)
    mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    return QMessageBox.Ok == mb.exec_()

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# The actual data behind the list model, a list of Comic objects each with
# these fields:
#
#   name:      the name of the comic as set by the user, the display data
#              of the list view.
#
#   url:       the URL of the comic as given by the user.
#
#   old_hash:  the SHA-1 hash of the page as read last time we ran AND the
#              user displayed the comic. Saved in the settings.
#
#   new_hash:  the SHA-1 hash of the page as read today, which will be
#              saved as old_hash if and when the user displays the comic.
#
#   status:    OLDCOMIC, NEWCOMIC, BADCOMIC or WORKING. Not saved.
#
#   page:      contents of the single page at the url. Not saved.
#
#   error:     error string to display when status==BADCOMIC
#

class Comic(object) :
    def __init__(self, name='', url=u'', hash=b'\x00', s=OLDCOMIC ) :
        self.name = name
        self.url = url
        self.old_hash = hash
        self.new_hash = b'\x00'
        self.status = s
        self.page = ''
        self.error = ''

#
# The list is initialized at startup, see ConcreteListModel.load()
#
COMICS = [] # list of Comic objects

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# This is how we make a hash signature of a comic web page. Instead of
# hashing the whole HTML text of the page, we only hash the src='' values
# of the <img statements in it, assuming that these should not change
# from day to day except for the one img that is the day's comic.
#
# This HTML parser subclass is applied to the text of a comic page.
# The handle_starttag method is called for each tag. Only <img start tags
# are looked at, and only the src= attribute, which is pushed into the
# hasher. Thus the hash is built on image urls, skipping certain images
# that are by experience false updates.
#
# To simply hash the whole page gets false positives since some comics have for
# example, random-comic links that change on every read, comments
# documenting the number of SQL queries to generate, user forums,
# constantly changing store displays, etc etc etc. So we parse the
# HTML and hash only the src= attributes of <img /> statements. This
# eliminated many but not all false positives>
#

class myParser(HTMLParser):
    def __init__(self, sha1) :
        HTMLParser.__init__(self)
        self.sha1 = sha1
        # A list of strings that are present in images that change without
        # any relation to new content in the actual comic. Eliminate these from
        # the hash to prevent false positive detection of new content.
        #  in A Multiverse, images/goat-xxxx changes randomly
        #  in comics that use yahoo for analytics, yahoo.com/visit.gif has a random argument
        #  some comics load different gravatars for no obvious reason
        #  Savage Chickens injects random ads from its images directory
        #  Ted Rall ends with a random number on cookies-for-comments
        #  sheldon inserts a random thumbnail of an old comic and so does
        #  comics.com, so any image with "thumb" is junk
        #  assets.amuniversal.com is a random ad image.
        self.blacklist = ['images/goat',
                            'webhosting.yahoo',
                            'gravatar',
                            'savagechickens.com/images',
                            'cookies-for-comments',
                            'thumb',
                            'assets.amuniversal.com'
                            ]
    def read_hash(self) :
        return bytes(self.sha1.digest())
    def handle_starttag(self, tag, attrs):
        if tag == 'img' :
            for (attr,val) in attrs :
                if attr == 'src' :
                    for nono in self.blacklist :
                        if nono in val :
                            return # bad image, do not include in hash
                    #print(val) #dbg: make a record of the hash input
                    val = val.encode('utf-8','ignore')
                    logging.info('  hash: %s', val)
                    self.sha1.update(val)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#   Synchronization between the main thread and the refresh thread.
#
# The main thread acquires the mutex work_queue_lock then pushes model
# indexes onto the work_queue. Then it releases the lock and posts the
# semaphore worker_waits.
#
# The refresh thread waits on worker_waits passing work_queue_lock, so when
# it wakes up it owns the work_queue_lock. It sets worker_working true. It
# removes an item from the queue and releases the lock. After refreshing that
# one comic, it comes back for more. If the work_queue turns out to be empty,
# the thread sets worker_working false and sleeps again on worker_waits.
#
# As long as worker_working is true, the list model will refuse to allow
# drag/drop to reorder the list and File > Delete and File > Import actions,
# because they could invalidate the index the worker is using.
#
work_queue = collections.deque() # queUE (misspelled) of items needing refresh

work_queue_lock = QMutex() # lock to allow updating the above queue

worker_working = False # flag to block drag/drop reordering

worker_waits = QWaitCondition() # where the worker thread awaits work

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
# This is the worker thread. Its code is in its run() method. It is
# started by a call to its start() method from the main code far below.
#

class WorkerBee ( QThread ) :

    statusChanged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        # !!! TEMPORARY until Wing 5.0.3
        import os
        if 'WINGDB_ACTIVE' in os.environ:
            super().__init__(self, parent)
        else:
            super().__init__(parent)
        # save a hasher which will be duplicated for each comic read
        self.hash = hashlib.sha1()
        # save an RE used to detect charset='encoding' or encoding='charset'
        # in HTML page headers.
        self.charset_re = re.compile(u'''(charset|encoding)\s*=\s*['"]?([\w\-\_\d]+)[;'">\s]''')

    def run(self) :
        global work_queue, work_queue_lock, worker_working, worker_waits
        work_queue_lock.lock() # start out owning the lock
        while True :
            # invariant: we own work_queue_lock at this point of the loop
            if 0 < len(work_queue) :
                # There is work, one or more model indexes in the queue.
                # Set the flag telling the main thread not to invalidate
                # any indexes, get the next item, release the lock.
                worker_working = True
                ix = work_queue.pop()
                work_queue_lock.unlock()
                # Process that one item, then re-acquire the lock for the
                # next iteration of this loop.
                self.process_one(ix)
                work_queue_lock.lock()
            else :
                # There is no work. At this point we own the lock. Set the
                # flag to allow the main thread to delete or reorder indexes.
                # Enter a wait on the QWaitCondition: that releases the lock
                # before it sleeps, and re-acquires the lock when it wakes.
                worker_working = False
                worker_waits.wait(work_queue_lock)

    # Process one Comic: Signal the main thread to update status to WORKING.
    # We will read the comic page no matter its status, because the user might
    # want to view even an old comic.
    #
    # If there is some error (usually, a timeout) reading the page, signal
    # the main thread to mark the comic BADCOMIC and exit. After reading the
    # page, compute its hash and compare to the last-displayed hash. If they
    # differ, tell the main thread to mark it NEWCOMIC -- else, OLDCOMIC.

    def process_one(self, ix) :
        global read_url, OLDCOMIC, NEWCOMIC, BADCOMIC, WORKING
        global COMICS
        row = ix.row()
        self.statusChanged.emit( row, WORKING )
        comic = COMICS[row]
        # Read the comic page once and save it, no matter status
        logging.info('Reading comic %s',comic.name)
        page_text = self.read_url(comic)
        comic.page = page_text
        if 0 == len(page_text) :
            # some problem reading the comic, mark it bad and quit.
            self.statusChanged.emit( row, BADCOMIC )
            logging.error('problem reading URL %s',comic.url)
            return

        # OK, this comic might could be new, so create a hash of the page we
        # read and see if it is different from the prior hash. See the
        # myParser class above for how we build a signature.

        # print('checking',comic.name) # dbg display hash texts
        # Create an HTML parser and feed it the page, line by line
        parsnip = myParser(self.hash.copy())
        page_as_file = io.StringIO(page_text)
        line = page_as_file.readline()
        while 0 < len(line):
            try:
                parsnip.feed(line)
            except Exception as wtf :
                # Some comics have javascript literals that HTMLParser chokes on.
                # It throws an exception. Just ignore it.
                parsnip.reset()
            line = page_as_file.readline()
        # The HTML parser has pushed all the img urls through the hasher.
        # Save the resulting hash signature as new_hash.
        comic.new_hash = parsnip.read_hash()
        if comic.old_hash != comic.new_hash :
            # The comic's web page has changed since it was displayed.
            self.statusChanged.emit( row, NEWCOMIC )
            logging.info('%s appears to be unread',comic.name)
        else :
            # It has not changed, hash is the same as last time.
            self.statusChanged.emit( row, OLDCOMIC )
            logging.info('%s appears to be old',comic.name)
        return

    # Given a comic, read the single html page at its url and return the page
    # as a (Unicode) string. If an error occurs, put an informative string in
    # comic.error.
    def read_url(self, comic) :
        global URLTIMEOUT, USERAGENT
        if 0 == len(comic.url.strip()) : # URL is a null or empty string
            return u'' # couldn't read that
        try:
            # Create an http "request" object for the URL
            ureq = urllib.request.Request(comic.url)
            # The commercial sites (comics.com) reject us unless we
            # show them a valid agent string.
            ureq.add_header('User-agent', USERAGENT)
            # Blog-based sites reject us with 403 unless we have this:
            ureq.add_header('Accept', 'text/html')
            #print('opening', comic.url) # dbg
            # Execute the request by opening it, creating a "file" to the page.
            # Use a timeout to avoid hang-like conditions on slow sites.
            furl = urllib.request.urlopen(ureq,None,URLTIMEOUT)
        except urllib.error.HTTPError as ugh :
            comic.error = 'URL open failed: HTTPError {0}, {1}'.format(ugh.code, ugh.reason)
            return u''
        except urllib.error.URLError as ugh :
            comic.error = 'URL open failed: URLError: ' + str(ugh.reason)
            return u''
        except Exception as wtf :
            comic.error = 'URL open failed: '+ str(wtf.args)
            return u''
        # opened the URL, now read it and convert to unicode. For that we need
        # the encoding. Per the W3C standards, either the entire page must be UTF-8
        # or, the first 1K must be UTF-8 and must contain a "charset" value.
        encoding = 'UTF-8'
        try:
            header = furl.read(1024).decode(encoding, errors='ignore')
            charset_match = self.charset_re.match(header)
            if charset_match : # there was a hit on charset='encoding'
                encoding = charset_match.group(2)
            trailer = furl.read().decode(encoding,errors='replace')
            page = header + trailer
        except Exception as ugh:
            comic.error = 'Read of open URL failed: '+str(ugh.args)
            page = ''
        finally:
            furl.close()
        return page

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the concrete list model by subclassing QAbstractListModel
# and gettin' real -- specifically by implementing these abstract methods
# (see qthelp:model-view-programming.html#model-subclassing-reference)
#
# Basic model/view methods:
#
#   rowCount() : return the number of items in the list.
#
#   flags() :
#      for list items return isEnabled | isSelectable | isEditable
#      for list items return isDragEnabled if worker thread is not active
#      for the list as a whole return only isDropEnabled
#
#   data(modelIndex, role) : return values for the display, tooltip,
#      statustip, whatsthis, textalignment, font, and several user roles
#
#   setData(modelIndex, role) : set the data at an index depending on
#      the role and emit the dataChanged signal
#
# Methods used by mainline code to load and save the model (not part of
# the standard model/view paradigm):
#
#   load(settings) : load the comics list from a settings object
#
#   save(settings) : save the comics list into a settings object
#
# Methods required to implement drag/drop reordering:
#
#   insertRows(row, count, parent-index) -- add empty rows
#   removeRows(row, count, parent-index) -- remove rows
#   itemData(modelIndex) -- return all values of a comic as a dict
#   setItemData(modelIndex, dict) -- fill in a comic from a dict of values
#
# Also implemented: a custom Item Delegate to perform editing. Its class
# definition follows ConcreteListModel.
#

#
# Qt calls the list model .data() member with an index and a "role" for the
# type of data it wants. Here define role numbers for the fields that the
# list view doesn't know about.
#

url_role = Qt.UserRole # data() request for URL
page_role = url_role + 1 # data() request for page content string
old_hash_role = page_role + 1 # data() request for old hash
new_hash_role = old_hash_role + 1 # data() request for new hash
status_role = new_hash_role + 1 # data() request for comic status

class ConcreteListModel ( QAbstractListModel ) :

    bogusSignal = pyqtSignal(QModelIndex,QModelIndex)

    # minimal __init__ but see load()
    def __init__(self, parent=None):
        super().__init__(parent)

    # Here we implement the methods of QAbstractListModel class that convert
    # this from an abstract list to a concrete one. First up, flags which
    # tells the View what can be done with any given item. All items are
    # enabled and allow editing, selecting, dragging. If the query is for the
    # list parent, NOT an ordinary list item, we allow dropping as well. This
    # is what enables drag-to-reorder the list.
    def flags(self, index) :
        global worker_working
        basic_flag = Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if not worker_working :
            # ok to do drag'n'drop
            if index.isValid() :
                # normal item, not the list itself
                basic_flag |= Qt.ItemIsDragEnabled
            else :
                # parent item, i.e. the whole list
                basic_flag |= Qt.ItemIsDropEnabled
        return basic_flag

    # Next, rowCount just says how many rows there are in the model data. We use this
    # from our own code later as well. Note the count of rows in an ordinary item is 0;
    # only the count for the whole list is meaningful.
    def rowCount(self, parent):
        global COMICS
        if parent.isValid() :
            return 0
        return len(COMICS)

    # The data method is called when Qt needs to (re)display the list data.
    # During initialization or after endResetModel, this gets called several
    # times for each item to (re)populate the list. Other calls come from the
    # custom item delegate to initialize the editor, or after a drop.
    def data(self, index, role) :
        global COMICS, FONTLIST, URLRole
        comic = COMICS[index.row()] # save a few method calls
        if role == Qt.DisplayRole :
            # Data for the visible comic, i.e. its name.
            return comic.name
        if role == Qt.TextAlignmentRole :
            # All names aligned left
            return Qt.AlignLeft
        if role == Qt.FontRole :
            # Font for name depends on status
            return FONTLIST[comic.status]
        if (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
            # Data for the tooltip (pops up on hover) is the URL
            return comic.url
        if role == url_role :
            # Custom delegate needs the URL string for editing
            return comic.url
        # not a role we know...
        return None

    # setData is the normal means of modifying model data. The View doesn't call
    # it directly; it is called from the item delegate when an item is edited,
    # and also by our main window code to implement File>New Comic, after creating an
    # empty Comic object. It is also called from the statusChanged slot to change the
    # status of a comic on a signal from the worker thread.
    #
    # Input is a model index, a role, and some data for that role. In C++ the
    # data would be a QVariant that we have to coerce, e.g. variant.toString(),
    # but in PyQt5 the platform converts any QVariant to its appropriate
    # Python type -- in these cases either string or integer -- so we just assume
    # the type is correct and store it.
    #
    # After any change that affects the displayed list (which is all of them), we
    # emit the dataChanged signal to tell the View to repaint this item.
    # The signal arguments are the top-left and bottom-right changed
    # items, which is simply the one changed item.

    def setData(self, index, variant, role) :
        global COMICS, OLDCOMIC, url_role, status_role
        comic = COMICS[index.row()]
        if role == status_role : # change the status of a comic
            # status code change results in font change, see data()
            comic.status = variant
            #print('status {0:03x} on row {1}'.format(variant,index.row()))#dbg
            #self.dataChanged.emit( index, index )
            self.bogusSignal.emit(index,index)
            return True
        elif role == Qt.DisplayRole : # Set a new or changed name
            comic.name = variant # should be Python ustring
            #self.dataChanged.emit( index, index )
            self.bogusSignal.emit(index,index)
            return True
        elif role == url_role :
            # user edited the URL string
            comic.url = variant # again expecting a string
            comic.page = u'' # don't know page contents any more
            comic.old_hash = b'\x00' # don't know either hash now
            comic.new_hash = b'\x00'
            comic.status = OLDCOMIC # assume not new until refreshed
            #self.dataChanged.emit( index, index )
            self.bogusSignal.emit(index,index)
            return True
        return False # unknown role

    # This slot receives the statusChanged(row,stat) signal from the worker
    # thread. It just passes that on to setData() above to set the status.
    # setData signals dataChanged, and that makes the view call data() for
    # the display role and font role, resulting in a change of font.
    def statusChangedSlot(self, row, status) :
        global status_role
        ix = self.createIndex(row, 0)
        self.setData(ix, status, status_role)

    # Enable drag/drop by returning supported actions.
    def supportedDragActions(self) :
        return Qt.MoveAction
    def supportedDropActions(self) :
        return Qt.MoveAction

    # The insertRows/removeRows methods are essential to internal drag and
    # drop. In order to not have any possibility of drag/drop taking place
    # while an item is being refreshed -- which could invalidate the index
    # that the worker thread is using -- these functions don't do anything
    # unless the worker thread is sleeping.
    def insertRows(self, row, count, parent) :
        global Comic, COMICS, worker_working
        #print('insertRows({0} for {1}: {0}..{2})'.format(row,count,row+count-1))
        if worker_working :
            return False
        # The worker thread is asleep and will not wake up until the user
        # requests a refresh which she cannot do while she is dragging an item.
        self.beginInsertRows(parent, row, row+count-1 )
        # have to do this one at a time to insert scalars, not a list
        for i in range(count):
            COMICS.insert(row,Comic())
        self.endInsertRows()
        return True

    def removeRows(self, row, count, parent) :
        global COMICS, worker_working
        #print('removeRows({0} for {1}: {0}..{2})'.format(row,count,row+count-1))
        if worker_working :
            return False
        self.beginRemoveRows(parent, row, row+count-1)
        COMICS[row : row+count ] = []
        self.endRemoveRows()
        return True

    # The itemData method is a shortcut for the view when it is dragging an
    # item: it calls itemData to get a collection of all an item's properties
    # in one bag. In the Qt docs, itemData returns a QMap, the Qt equivalent
    # of a dict. In PyQt, it just returns a dict. In this case, a dict that
    # contains all the fields of a given comic, so that setItemData can
    # reproduce that comic in a new row.
    # TODO: WALK THRU
    def itemData(self, index) :
        global COMICS, url_role, page_role, old_hash_role, new_hash_role, status_role
        comic = COMICS[index.row()]
        item_dict = {
            Qt.DisplayRole : comic.name,
            url_role  : comic.url,
            page_role : comic.page,
            old_hash_role : comic.old_hash,
            new_hash_role : comic.new_hash,
            status_role : comic.status,
        }
        #print('itemData row {0}'.format(index.row()))
        return item_dict

    # Here we receive the data prepared by itemData() above.
    #
    # The Qt docs say that setData() above must emit the dataChanged signal.
    # They do not say so for setItemData(), so I won't. After all, I think
    # this is only called by drag/drop, in which case Qt should darn well
    # know that data has been changed and needs to be redisplayed.
    # TODO: WALK THRU
    def setItemData(self, index, qdict) :
        global COMICS, url_role, page_role, old_hash_role, new_hash_role, status_role
        #print('setItemData row {0}'.format(index.row()))
        comic = COMICS[index.row()]
        comic.name = qdict[Qt.DisplayRole]
        comic.url = qdict[url_role]
        comic.page = qdict[page_role]
        comic.old_hash = qdict[old_hash_role]
        comic.new_hash = qdict[new_hash_role]
        comic.status = qdict[status_role]
        return True

    # Method to save the current list of comics:
    #
    # We save into the settings object, which in Windows means, into the
    # Registry under Tassosoft/Cobro (the company and app names set at
    # startup in the app object).
    #
    # In Mac OS, it's ~/Library/Preferences/tassos-oak.com/Cobro.plist
    #
    # In Linux it's $HOME/.config/Tassosoft/Cobro.conf
    #
    # We use the QSettings convenience function beginWriteArray to write
    # the array of comics as comics/1/name, comics/1/url, etc. Before saving
    # we use remove() to clear everything in that group, because if we don't,
    # deleted COMICS will come back like zombies next time we start up.
    def save(self, settings) :
        global COMICS
        settings.beginGroup(u'comiclist')
        settings.remove('')
        settings.endGroup()
        settings.sync() # not supposed to be needed but does no harm
        settings.beginGroup(u'comiclist')
        settings.beginWriteArray(u'comics')
        for i in range(len(COMICS)) :
            settings.setArrayIndex(i)
            settings.setValue(u'name', COMICS[i].name)
            settings.setValue(u'url', COMICS[i].url)
            settings.setValue(u'old_hash', COMICS[i].old_hash)
        settings.endArray()
        settings.endGroup()
        settings.sync() # not supposed to be needed but does no harm

    # Load the comics list from the saved settings, see save() above.
    # Since this completely loads the data model, inform the view that
    # things are changing/have changed.
    def load(self, settings) :
        global COMICS, Comic, OLDCOMIC
        self.beginResetModel()
        settings.beginGroup(u'comiclist')
        count = settings.beginReadArray(u'comics')
        for i in range(count) :
            settings.setArrayIndex(i)
            name = settings.value(u'name')
            url = settings.value(u'url')
            old_hash = settings.value(u'old_hash')
            comic = Comic(name,url,old_hash,OLDCOMIC)
            COMICS.append(comic)
        settings.endArray()
        settings.endGroup()
        self.endResetModel()

    # As a convenience to the main window, return a list of the model
    # indexes of all comics in order.
    def listOfAllComics(self):
        global COMICS
        n = len(COMICS)
        ixes = [self.createIndex(i,0) for i in range(n)]
        return ixes

# So, WTF is a custom delegate? A widget that represents a data item when
# when that item needs to be displayed or edited. When the user double-clicks
# an item in the view, the view instantiates a custom delegate to display and
# optionally edit the item's contents.
#
# Often a delegate is a simple widget e.g. a combobox or spinbox or lineedit.
# We need to offer two fields, the name and URL, so we make a little Widget
# with two lineEdits and matching labels. This same widget is also used by
# File > New Comic.

class EditWidget(QWidget) :
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nameEdit = QLineEdit()
        self.urlEdit = QLineEdit()
        hb1 = QHBoxLayout()
        hb1.addWidget(QLabel(u'Comic Name:'))
        hb1.addWidget(self.nameEdit)
        hb2 = QHBoxLayout()
        hb2.addWidget(QLabel(u'Comic URL : '))
        hb2.addWidget(self.urlEdit)
        vb1 = QVBoxLayout()
        vb1.addLayout(hb1)
        vb1.addLayout(hb2)
        self.setLayout(vb1)

# Ducks are now in a row so implement the Custom Delegate itself, which
# has to implement 3 methods:
#
# createEditor() returns the widget that will be shown to the user. The
# ListView positions it over the edited (double-clicked) item.
#
# setEditorData() loads up the editor widget with data to display.
#
# setModelData() is called when editing is complete, to get the possibly
# changed data out of the editor widget and put it back in the model.
#

class ItemDelegate(QStyledItemDelegate):
    # minimal init lets parent do its thing if any
    def __init__(self, parent=None):
        super().__init__(parent)

    # Create the editing widget with empty data
    def createEditor(self, parent, style, index):
        return EditWidget()

    # Load the edit widget with data from the given row
    def setEditorData(self, edit_widget, index) :
        global COMICS
        comic = COMICS[index.row()]
        edit_widget.nameEdit.setText(comic.name)
        edit_widget.urlEdit.setText(comic.url)

    # Return the data to the model. We do this by calling setData()
    # in the model, which is the concreteModel class defined above.
    # However, we check here that the user actually made
    # a change in the data before calling the model to update itself.
    def setModelData(self, edit_widget, model, index ) :
        global COMICS, url_role
        comic = COMICS[index.row()]
        edit_name = edit_widget.nameEdit.text()
        if edit_name != comic.name :
            # Name was edited: update the "display role" value
            model.setData( index, edit_widget.nameEdit.text(), Qt.DisplayRole )
        edit_url = edit_widget.urlEdit.text()
        if edit_url != comic.url :
            # URL was edited, update the url_role value
            model.setData( index, edit_widget.urlEdit.text(), url_role )

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the view onto the above list model. The QListView in Qt's scheme takes
# on all the responsibility for displaying the list, keeping it up to date when the
# model data changes, handling drag/drop, selecting and scrolling.
#TODO:why drag behavior?

class CobroListView(QListView) :
    def __init__(self, browser, parent=None):
        super().__init__(parent)
        # Save reference to our browser window for use in itemClicked()
        self.webview = browser
        # flag used to prevent a recursion loop on dataChanged signal!
        self.displaying = False
        # connect to the concrete model to display
        #self.setModel(model)
        #self.model().dataChanged.connect( self.dataChanged )
        # Set all the many properties of a ListView/AbstractItemView:
        #
        # Uniform item sizes
        self.setUniformItemSizes(True)
        #
        # list view: list, not icons
        self.setViewMode(QListView.ListMode)
        #
        # list view: allow movement (overrides static set by above)
        self.setMovement(QListView.Free)
        #
        # Alternate the colors of the list, like greenbar paper (nostalgia)
        self.setAlternatingRowColors(True)
        #
        # list view: resize mode to adjust on any resize
        self.setResizeMode(QListView.Adjust)
        #
        # allow ctl-click, shift-click, and drag for multi-selections
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        #
        # Scroll by pixels, not items
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        #
        # What starts an edit?
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        #
        # Create the custom delegate and save a pointer to it.
        self.setItemDelegate(ItemDelegate())
        #
        # auto-scroll on dragging/selecting, use an explicit margin because
        # the default seemed insensitive to me.
        self.setAutoScroll(True)
        self.setAutoScrollMargin(12)
        #
        # Trying to set up for internal drag/drop to reorder the list, that is,
        # a drag moves an item from one place in the list to another.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False) # default
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        ##### end of __init__

    # Intercept the selectionChanged event. The two arguments are
    # QItemSelection objects. The first lists the items that are newly
    # selected as the result of some event (like a shift-click). The second
    # lists the items that are no longer selected ditto, as in control-click.
    # These are pretty much useless for our purposes. What we want to know
    # is, what is selected now and is there just one item? If so, then
    # display that item. If 0, or more than one selected, do nothing.
    def selectionChanged(self, selected, deselected):
        list_of_indexes = self.selectedIndexes()
        if not 1 == len(list_of_indexes) :
            return
        self.itemDisplay(list_of_indexes[0])

    # Override the dataChanged slot in order to redisplay a web page, in the
    # event that the item being changed is exactly the one item selected, and
    # its status is OLD, NEW or BAD. The use case here is that the user has
    # clicked on a comic (selecting it) and keyed ^r to refresh. So the refresh
    # begins and  the status changes to WORKING, then later to NEWCOMIC and
    # it should refresh the page display right then, not require another click.
    # If the item being changed is NOT the single current selection, do nothing.

    def dataChanged(self, topLeft, bottomRight ) :
        if not self.displaying:
            # signal didn't come as a result of itemDisplay below
            top_left_row = topLeft.row()
            if top_left_row == bottomRight.row() :
                # just one item being changed
                selection = self.selectedIndexes()
                if len(selection) == 1 :
                    # just one item is selected
                    sel_item = selection[0]
                    if sel_item.row() == top_left_row :
                        # the item being changed is the one item currently
                        # highlited in the list is it in displayable state
                        # (or is it "working" or invalid)?
                        comic = COMICS[top_left_row]
                        if comic.status in [NEWCOMIC, BADCOMIC, OLDCOMIC] :
                            # yeah, so update the html display
                            self.itemDisplay(sel_item)
        # regardless, pass the signal on to the parent
        super().dataChanged(topLeft, bottomRight)

    # It is the time to display one item's URL in our web browser. Some
    # things we do here (changing the font) can trigger a dataChanged signal.
    # To avoid a recursive loop we set a flag self.displaying. Also at this
    # time, copy new_hash (the hash value of the page we display) into
    # old_hash and make the status OLDCOMIC.
    def itemDisplay(self, index) :
        global COMICS, OLDCOMIC, NEWCOMIC, BADCOMIC, status_role
        global ERROR_MSG, UNREAD_MSG, READING_MSG
        self.displaying = True
        comic = COMICS[index.row()]
        # Tell the web page, whatever it's working on, stop it.
        self.webview.page().triggerAction(QWebPage.Stop)
        if (comic.status == OLDCOMIC) or (comic.status == NEWCOMIC) :
            # i.e., not a bad comic or a working comic
            if len(comic.page) :
                # Pass the current page data into our web viewer.
                self.webview.setHtml( comic.page, QUrl(comic.url) )
                # set the font to show it has been seen.
                self.model().setData(index, OLDCOMIC, status_role)
                comic.old_hash = comic.new_hash
            else :
                # No page data has been read -- perhaps this is a new comic
                # just added? Put up an explanation in the browser window.
                self.webview.setHtml( UNREAD_MSG, QUrl() )
        elif comic.status == BADCOMIC :
            # Comic had an error on the last refresh, put up an explanation
            # with error message in the browser window.
            self.webview.setHtml( ERROR_MSG.format(comic.error), QUrl() )
        else:
            # Comic is being refreshed, plead for more time
            self.webview.setHtml( READING_MSG, QUrl() )
        self.displaying = False

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the web page display, based on QWebView with added behaviors.
# Initialize it with welcome/usage/license message.
#

class CobroWebPage(QWebView) :
    def __init__(self, status, bar, parent) :
        global FONTLIST, OLDCOMIC, WELCOME_MSG
        # Initialize the root class, incidentally creating a QWebPage
        super().__init__(parent)
        # Save access to the main window (our parent) and
        # separately to its status line and progress bar widgets
        self.main = parent
        self.statusLine = status
        self.progressBar = bar
        # Set up a flag used while updating status, see startBar, rollBar below
        self.needUrlStatus = False
        # make page unmodifiable
        self.page().setContentEditable(False)
        # set up the default font TODO IS THIS NEEDED/USEFUL?
        qfi = QFontInfo(FONTLIST[OLDCOMIC])
        self.settings().setFontFamily(QWebSettings.StandardFont, qfi.family())
        self.settings().setFontSize(QWebSettings.DefaultFontSize, 16)
        self.settings().setFontSize(QWebSettings.MinimumFontSize, 6)
        self.settings().setFontSize(QWebSettings.MinimumLogicalFontSize, 6)
        # set our zoom factor which is changed by keys ctl-plus/minus
        self.ourZoomFactor = 1.0
        # We no longer set textSizeMultiplier because doing so forces ON
        # the setting ZoomTextOnly. Just use zoomFactor.
        #self.setTextSizeMultiplier(self.ourZoomFactor)
        self.setZoomFactor(self.ourZoomFactor)
        # Disable scripting! Well, actually, quite a few comics need j'script,
        # including (darn it) the SMBC red button!
        self.settings().setAttribute(QWebSettings.JavascriptEnabled, True)
        self.settings().setAttribute(QWebSettings.JavaEnabled, False)
        # Enable plugins since many comic pages use Flash
        self.settings().setAttribute(QWebSettings.PluginsEnabled, True)
        # Private browsing, don't store crap in the webkit caches
        self.settings().setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
        # Let +/- zoom affect the image which is what we came for
        self.settings().setAttribute(QWebSettings.ZoomTextOnly, False)
        # Connect the load progress signals to our slots below.
        self.loadStarted.connect( self.startBar )
        self.loadProgress.connect( self.rollBar )
        self.loadFinished.connect( self.endBar )
        # Set our Page to "delegate" all links, that is, when a link is clicked do not
        # follow it but instead raise the linkClicked signal. Connect the signal.
        self.page().setLinkDelegationPolicy(QWebPage.DelegateExternalLinks)
        self.linkClicked.connect( self.link_clicked )
        # Connect the titleChanged signal to our slot.
        self.titleChanged.connect( self.newTitle )
        # Set up constants for key values so as not to bog down the keypress event.
        #  - mask to turn off keypad indicator, making all plus/minus alike
        self.keypadDeModifier = int(0xffffffff ^ Qt.KeypadModifier)
        #  - ctl-minus is the only unambiguous zoom key
        self.ctl_minus = Qt.ControlModifier | Qt.Key_Minus
        #  - list of all keys zoom-related
        self.zoomKeys = [Qt.ControlModifier | Qt.Key_Minus,
                            Qt.ControlModifier | Qt.Key_Equal,
                            Qt.ControlModifier | Qt.Key_Plus,
                            Qt.ShiftModifier | Qt.ControlModifier | Qt.Key_Equal,
                            Qt.ShiftModifier | Qt.ControlModifier | Qt.Key_Plus ]
        self.backKeys = [Qt.ControlModifier | Qt.Key_B,
                            Qt.ControlModifier | Qt.Key_Left,
                            Qt.ControlModifier | Qt.Key_BracketLeft]
        self.forwardKeys = [Qt.ControlModifier | Qt.Key_Right,
                            Qt.ControlModifier | Qt.Key_BracketRight]
        self.copyKeys = [Qt.ControlModifier | Qt.Key_C, Qt.Key_Copy ]
        # Load a greeting message
        self.setHtml(WELCOME_MSG)
        ##### end of __init__

    # Slot to receive the loadStarted signal: clear the bar to zero and show
    # the url in the status line. Problem: at loadStarted time, self.url()
    # returns the *previous* url, not the one actually being started. So to
    # avoid looking like a doofus, set it when updating the bar.
    def startBar(self) :
        self.progressBar.reset()
        self.needUrlStatus = True

    # Slot to receive the loadProgress signal. Set the progress bar value.
    # Also set the URL in the status line, but only if it hasn't been set
    # and only if we have some progress, otherwise it's the prior url.
    def rollBar(self, progress) :
        self.progressBar.setValue(progress)
        if self.needUrlStatus and progress > 10 :
            self.statusLine.setText(self.url().toString())
            self.needUrlStatus = False

    # Slot to receive the loadFinished signal. Clear the progress bar and
    # status line, but if the argument is False, something went wrong with
    # the page load.
    def endBar(self, ok) :
        self.progressBar.reset()
        self.statusLine.clear()
        if not ok :
            self.statusLine.setText(u"Some error")

    # Slot to receive the linkClicked signal. (In v.1 this was named
    # "linkClicked" but in PyQt5, signals are class variables, so this method
    # has to use a different name from the signal.) Stop any ongoing action.
    # Then complete the link action by calling self.setUrl.
    def link_clicked(self, url):
        #print(url.toString()) #dbg
        self.page().triggerAction(QWebPage.Stop)
        #self.settings().clearMemoryCaches()
        self.setUrl(url)

    # Slot to receive the titleChanged signal. Change the title of the
    # main window to match.
    def newTitle(self, qstitle):
        #print('new title',qstitle)
        self.main.setWindowTitle(qstitle)

    # Re-implement the parent's keyPressEvent in order to provide:
    # * font-size-zoom from ctl-plus/ctl-minus,
    # * browser back on ctl-[, ctl-b, ctl-left
    # * browser forward on ctl-], ctl-right
    # * copy selected to clipboard on ctl-c
    # For the font size, we initialize the view at 16 points and the zoom
    # factor at 1.0. Each time the user hits ctl-minus we deduct 0.0625 from
    # the multiplier, and for each ctl-+ we add 0.0625 (1/16) to the
    # multiplier. This ought to cause the view to change text sizes up or
    # down by about one point and images by a bit. We set limits of 0.375 (6
    # points) and 4.0 (64 points).
    def keyPressEvent(self, event):
        global WELCOME_MSG
        kkey = int( int(event.modifiers()) & self.keypadDeModifier) | int(event.key() )
        if (kkey in self.zoomKeys) : # ctrl-plus/minus
            event.accept()
            zfactor = 0.0625 # zoom in
            if (kkey == self.ctl_minus) :
                zfactor = -zfactor # zoom out
            zfactor += self.ourZoomFactor
            if (zfactor > 0.374) and (zfactor < 4.0) :
                self.ourZoomFactor = zfactor
                self.setZoomFactor(self.ourZoomFactor)
        elif (kkey in self.backKeys) :
            event.accept()
            if self.page().history().canGoBack() :
                self.page().history().back()
            else:
                self.setHtml(WELCOME_MSG)
        elif (kkey in self.forwardKeys) :
            event.accept()
            if self.page().history().canGoForward() :
                self.page().history().forward()
        elif (kkey in self.copyKeys) :
            event.accept()
            QApplication.clipboard().setText(self.selectedText())
        else: # not a key we support, so,
            event.ignore()
        super().keyPressEvent(event)

    # Re-implement the parent's contextMenuEvent handler to do our own context
    # menus in certain situations, but not all.
    def contextMenuEvent (self, cx_event) :
        main_frame = self.page().mainFrame()
        hit_test = main_frame.hitTestContent(cx_event.pos())
        hit_url = hit_test.linkUrl()
        if not hit_url.isEmpty() :
            # The right-click (or whatever) was upon a link. In this case we want to
            # offer a custom context menu with two actions: copy link url and
            # open link in default browser. Annoyingly, the predefined "copy link" action
            # provided by pageAction does not use the the global app clipboard. Since
            # we expect the user to paste a copied link in another app (e.g. browser)
            # we have to implement the copy action also.
            cx_event.accept()
            # First, save the target URL for our actions to use.
            self.contextUrl = hit_url.toString()
            # Next, create the custom two-action menu:
            ctx_menu = QMenu()
            # Action one is, copy link to clipboard
            ctx_copy = QAction( u'Copy link to clipboard', self )
            ctx_copy.triggered.connect( self.copyLinkToClipboard )
            ctx_menu.addAction(ctx_copy)
            # Action B is, open in another browser
            ctx_open = QAction( u'Open in default browser', self )
            ctx_open.triggered.connect( self.openInDefaultBrowser )
            ctx_menu.addAction(ctx_open)
            # Now show the menu.
            ctx_menu.exec_(cx_event.globalPos())
        else:
            # the thing right-clicked was not a link, so, meh.
            super().contextMenuEvent(cx_event)
    # Here are the slots for our two context menu actions.
    # The URL of the clicked link has been saved.
    def copyLinkToClipboard(self) :
        QApplication.clipboard().setText(self.contextUrl)
    def openInDefaultBrowser(self) :
        webbrowser.open_new(self.contextUrl)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the application window incorporating the list and webview.
# The one class of this object also catches shut-down.
#
# In order to have a standard menu bar we have to use QMainWindow.
# That class requires us to supply the real window contents as a widget
# (not just a layout) so we create that widget first.
#
class theAppWindow(QMainWindow) :
    def __init__(self, settings, parent=None) :
        super().__init__(parent)
        # Save the settings instance for use at shutdown (see below)
        self.settings = settings
        # Here store the last-used directory to start file selection dialogs
        self.starting_dir = os.getcwd()
        # Create the list model and keep a reference to it.
        self.model = ConcreteListModel(self)
        # Tell the list to load itself from the settings, this populates the list
        self.model.load(settings)
        # Create the central widget. Create everything else and
        # tuck them into a layout which the gets applied to central.
        central = QWidget()
        # Create a status line as a label.
        self.statusLine = QLabel(u'')
        # Create the progress bar.
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0,100)
        self.progressBar.setOrientation ( Qt.Horizontal)
        self.progressBar.setTextVisible(False)
        # Create the webrowser: a WebPage in a WebView. The web view needs
        # access to the progress and status bars so it can update them.
        self.page = CobroWebPage(self.statusLine, self.progressBar, self)
        # Create the List View, which needs access to the web view
        # (to display a comic)
        self.view =  CobroListView(self.page)
        # Connect the model's dataChanged signal to the view's dataChanged slot
        self.view.setModel(self.model)
        #self.model.dataChanged.connect(self.view.dataChanged)
        self.model.bogusSignal.connect(self.view.dataChanged)
        # Lay out our widget: the list on the left and webview on the right,
        # underneath it a status line and a progress bar.
        hb = QHBoxLayout() # hbox with list and webview
        hb.addWidget(self.view,0) # no stretch
        hb.addWidget(self.page,1) # all available stretch
        hb2 = QHBoxLayout() # hbox with status line and progress bar
        hb2.addWidget(self.statusLine,1) # all stretch
        hb2.addWidget(self.progressBar,0) # no stretch, squeezed to the right
        vb = QVBoxLayout() # vbox to stack the two hboxes
        vb.addLayout(hb,1) # all stretch to the good stuff
        vb.addLayout(hb2,0) # no stretch, status/progress squeezed to bottom
        central.setLayout(vb)
        # Make central our central widget
        self.setCentralWidget(central)
        # restore saved or default window geometry
        self.resize(self.settings.value( "cobro/size", QSize(600,400) ) )
        self.move(self.settings.value( "cobro/position", QPoint(100, 100) ) )
        # Create a menubar and populate it with our one (1) menu
        menubar = QMenuBar()
        menubar.setNativeMenuBar(True) # identify with OSX bar
        # Create the one menu, File
        file_menu = menubar.addMenu(u"File")
        # Create the File>New action, connect its signal, put in menu
        file_new_action = QAction(u"New Comic",self)
        file_new_action.setShortcut(QKeySequence.New)
        file_new_action.setToolTip(u"Define new comic at end of list")
        file_new_action.triggered.connect( self.newComic )
        file_menu.addAction(file_new_action)
        # Create the File>Refresh action, connect signal, put in menu
        file_refresh_action = QAction(u"Refresh",self)
        file_refresh_action.setShortcut(QKeySequence.Refresh) # == F5, ^r
        file_refresh_action.setToolTip(u"Reload the web pages of all or selected comics")
        file_refresh_action.triggered.connect( self.refresh )
        file_menu.addAction(file_refresh_action)
        # Create the File>Delete action, connect signal, put in menu
        file_delete_action = QAction(u"Delete",self)
        file_delete_action.setShortcut(QKeySequence.Delete) # DEL key
        file_delete_action.setToolTip(u"Delete the selected comics")
        file_delete_action.triggered.connect( self.delete )
        file_menu.addAction(file_delete_action)
        #  Create the File>Export action, connect signal, put in menu
        file_export_action = QAction(u"Export",self)
        file_export_action.setToolTip(u"Export all or selected comics")
        file_export_action.triggered.connect( self.file_export )
        file_menu.addAction(file_export_action)
        # Create the File>Import action
        file_import_action = QAction(u"Import",self)
        file_import_action.setToolTip(u"Import comics from a file")
        file_import_action.triggered.connect( self.file_import )
        file_menu.addAction(file_import_action)
        # Activate the menu and menu bar
        self.setMenuBar(menubar)
        # Create our worker thread and start it. Connect its signal to slots in both
        # the concrete model and the list view, and kick it off.
        self.worker = WorkerBee(self)
        self.worker.statusChanged.connect( self.model.statusChangedSlot )
        self.worker.start() # start the worker
        self.refreshAll() # give worker some work, lazy thing
        #### end of __init__

    # Do refresh-all -- not a menu action but done at startup after load
    # Put the model index of every row into the work queue for the worker thread.
    def refreshAll(self):
        ixes = self.model.listOfAllComics()
        work_queue_lock.lock()
        for ix in ixes :
            work_queue.appendleft(ix)
        work_queue_lock.unlock()
        worker_waits.wakeOne()

    # Implement the File > Refresh action, refresh selected. If no comic
    # selected, does nothing. (It's hard not to have at least 1 selected.)
    def refresh(self) :
        global work_queue, work_queue_lock, worker_waits
        # Get a list of the model indexes of the current selection
        ixes = self.view.selectedIndexes()
        # Run through the list and for each, do the refresh thing
        for ix in ixes :
            work_queue_lock.lock()
            work_queue.appendleft(ix)
            work_queue_lock.unlock()
        worker_waits.wakeOne()

    # Implement the File > New Comic action
    # We can't start if a refresh is in progress, because insertRows won't work.
    # If the worker thread is quiescent, create a custom dialog based on
    # the same edit widget as used by the custom delegate, but augmented with
    # OK and Cancel buttons. If the app. clipboard contains text that looks like
    # a URL, use it to initialize the dialog. Display the dialog.
    # If the dialog is accepted, call the model's insertRows method to add a
    # row at the end, then load that empty Comic from the dialog values.

    def newComic(self) :
        global worker_working
        if worker_working :
            warningMsg(u'Sorry, Update in progress','Please wait until all refreshes are done')
            return
        # Create the input dialog widget from the same class as used for the
        # custom item delegate.
        edwig = EditWidget()
        # Get the global clipboard text as a python string.
        clip = QApplication.clipboard().text()
        if len(clip) :
            # There is some text on the clipboard, does it look like a URL?
            if re.match(u'http://',clip,re.I) :
                # oh yeah. Stuff that puppy into the dialog's URL slot
                edwig.urlEdit.setText(clip)
                # also try to pick out the domain and put it in the name field
                domain_match = re.search(u'://(www\.)?([^\.]+)\.',clip,re.I)
                if domain_match :
                    edwig.nameEdit.setText(domain_match.group(2))
        # Set up a pair of OK/Cancel buttons
        bts = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # Stack the edit widget over the button row
        vb = QVBoxLayout()
        vb.addWidget(edwig)
        vb.addWidget(bts)
        # Create a dialog and lay it out with the above items. Connect the OK/Cancel
        # buttons' signals to the dialog's accept/reject slots. Blahdiblahdiblah gui.
        dlg = QDialog(self, Qt.Dialog)
        dlg.setLayout(vb)
        bts.accepted.connect( dlg.accept )
        bts.rejected.connect( dlg.reject )
        # Show that dialog and await wonderfulness.
        ans = dlg.exec_()
        if ans == QDialog.Accepted \
        and 0 < len(edwig.nameEdit.text()) \
        and 0 < len(edwig.urlEdit.text()) :
            # User clicked OK and entered some data. Note we do NOT check for
            # a duplicate comic name, if you want three comics named FOOBAR,
            # be my guest.
            j = self.model.rowCount(QModelIndex()) # count of rows now
            self.model.insertRows(j,1,QModelIndex()) # add a row number j, at the end
            ix = self.model.createIndex(j,0) # create model index of new row
            self.model.setData( ix, edwig.nameEdit.text(), Qt.DisplayRole )
            self.model.setData( ix, edwig.urlEdit.text(), url_role )

    # Implement the File > Delete action: Make sure the refresh worker
    # isn't running. Get the current selection as a list of model indexes.
    # Query the user if she's serious. If so, call the model one index at
    # a time, working from the end backward so as not to invalidate
    # the indexes, to remove the rows.
    def delete(self) :
        global worker_working
        if worker_working :
            warningMsg("Cannot delete during refresh",
                        "please wait until the refresh process finishes")
            return
        ix_list = self.view.selectedIndexes()
        nix = len(ix_list)
        # If nothing is selected, bail
        if 0 == nix : return
        # Give an appropriately-worded warning.
        # Start with the name of the first/only comic in the list
        msg = 'Delete comic "'
        name_zero = self.model.data(ix_list[0],Qt.DisplayRole)
        if nix == 1 :
            msg = msg + name_zero + u'"?'
        else :
            msg = msg + name_zero + u'" and {0} more?'.format( nix-1 )
        ok = okCancelMsg(msg, "This cannot be undone.")
        if not ok : return
        # Well all-righty then. Do not trust Qt to give us a selection list
        # in row order, it would be ascending anyway and we want descending
        # so use Python to sort it.
        ix_list.sort(key = QModelIndex.row, reverse = True)
        for ix in ix_list :
            self.model.removeRows(ix.row(), 1, QModelIndex())
        # and that's it
        return

    # Implement the File > Export action. Get the list of selected comic
    # indexes. If none are selected, get the list of all. Ask the user to
    # provide a file to write into. The starting directory is the last
    # directory we've used for export or import. Write a text file with one
    # line per selected comic.
    def file_export(self) :
        global COMICS, url_role, EXPORTBUMF
        ix_list = self.view.selectedIndexes()
        nix = len(ix_list)
        # If nothing is selected, get a list of all comics.
        if 0 == nix :
            ix_list = self.model.listOfAllComics()
            nix = len(ix_list)
        # If still nothing (all deleted, or first time we've run), quit
        if 0 == nix :
            return
        # A non-empty list is ready. Get a file.
        msg = 'Specify a text file to receive Comic definitions'
        # PyQt4/5 returns a tuple of which the first item is the path
        path = QFileDialog.getSaveFileName( self, msg, self.starting_dir )
        path = path[0]
        if 0 == len(path) :
            # user cancelled dialog, or anyway didn't select a file: quit
            return
        # note starting dir for next time
        self.starting_dir = os.path.dirname(path)
        try:
            fobj = open(ppath, 'w', encoding='UTF-8', errors='ignore')
        except :
            return # can't open it? assume the OS has given a message
        try:
            fobj.write(EXPORTBUMF)
            for ix in ix_list :
                fobj.write(
                    "'{0}', '{1}''\n".format(
                    self.model.data(ix, Qt.DisplayRole),
                    self.model.data(ix, url_role)
                    )
                )
        finally:
            fobj.close()

    # Implement the File > Import action. Tell the view to clear the selection.
    # Ask the user to specify a file to read. (Exit if cancel.) Use as the starting
    # directory the last directory we've used. Read the file by lines, testing each
    # against an RE. If the RE matches, create a new comic using the strings from the
    # match. Look for a comic with the same name and replace it if found, or append.
    def file_import(self) :
        global COMICS, url_role, worker_working
        if worker_working :
            warningMsg("Cannot import during refresh",
                        "please wait until the refresh process finishes")
            return
        # Parse the input data as follows:
        # - optional opening spaces ^\s*
        # - opening single or double quote or «
        # - at least one non-quote (capture 1, comic name)
        # - closing single double or », not checking for match to opening
        # - spaces or a comma with optional spaces (capture 2, not used)
        # - single or double quote or «
        # - at least one non-quote (capture 3, url)
        # - single or double quote or », not looking for a match
        # - optional spaces to end of line \s*$
        retext = '''^\\s*[\'"«]([^\'"»«]+)[\'"»](\s+|\s*,\s*)[\'"«]([^\'"»«]+)[\'"»]\\s*$'''
        line_test = re.compile(retext)
        msg = 'Choose a file of Comic definitions:'
        # The PyQt5 version returns a tuple, the first element is the path
        path = QFileDialog.getOpenFileName( self, msg, self.starting_dir )
        path = path[0]
        if 0 == len(path) :
            return # user cancelled dialog
        self.starting_dir = os.path.dirname(path) # note starting dir for next time
        try:
            fobj = open(path,'r',encoding='UTF-8',errors='ignore')
        except:
            return # can't open the file? screw it.
        self.view.clearSelection()
        try:
            line = fobj.readline()
            while len(line) :
                line_match = line_test.match(line)
                if line_match is not None:
                    # we have a comic definition line, get its parts.
                    line_name = line_match.group(1)
                    line_url = line_match.group(3)
                    # see if it exists already. search directly in the list rather than
                    # going all around the barn calling self.model.data().
                    j = len(COMICS)
                    for i in range(j) :
                        if COMICS[i].name == line_name :
                            j = i
                            break
                    if j == len(COMICS) :
                        # no match on name, append a row j
                        self.model.insertRows(j,1,QModelIndex())
                    # put the data from the line in the old or new Comic
                    ix = self.model.createIndex(j,0) # create model index of new row
                    self.model.setData( ix, line_name, Qt.DisplayRole )
                    self.model.setData( ix, line_url, url_role )
                line = fobj.readline()
        finally:
            fobj.close()

    # -----------------------------------------------------------------
    # reimplement QWidget::closeEvent() to save the current comics.
    def closeEvent(self, event):
        # make sure the webkit is in a clean state
        self.page.page().triggerAction(QWebPage.Stop)
        # Save window geometry in settings
        self.settings.setValue("cobro/size",self.size())
        self.settings.setValue("cobro/position", self.pos())
        self.model.save(self.settings)
        event.accept()

if __name__ == "__main__":

    import sys # for argv
    import logging
    import argparse

    # Create the App so all the other Qt stuff will work
    app = QApplication(sys.argv)
    # Set up the parameters of our QSettings, in which the comics
    # we know about are stored.
    app.setOrganizationName("Tassosoft")
    app.setOrganizationDomain("tassos-oak.com")
    app.setApplicationName("Cobro")
    app.setApplicationVersion("2.0")
    # Create the settings object to use in accessing the settings
    settings = QSettings()

    # setup the font globals
    setup_jolly_fonts()

    # Set the global default timeout value in a (probably vain) hope
    # of avoiding hangups on slow-loading web pages
    import socket
    if socket.getdefaulttimeout() is None :
        socket.setdefaulttimeout(10)

    # parse for command line arguments which currently relate only to
    # logging: --level=[INFO|ERROR] --logfile=filepath
    parser = argparse.ArgumentParser()
    parser.add_argument('--level',dest='level',
                        choices=['INFO','ERROR'],default='ERROR',
                        help='use INFO to see items hashed for each comic')
    parser.add_argument('--logfile',dest='logfile',type=argparse.FileType('w'),
                        help='specify a text file to receive log data in place of stderr',
                        default=None)
    args = parser.parse_args()

    # Set up simple logging to stderr...
    import logging
    lvl = logging.ERROR
    if args.level == 'INFO' :
        lvl = logging.INFO
    if args.logfile is None :
        logging.basicConfig( level=lvl )
    else :
        logging.basicConfig( level=lvl, stream=args.logfile )

    # Construct the GUI, passing it our Settings object to use for loading.
    main = theAppWindow(settings)

    # Get a valid User Agent string, without which many sites won't talk to us.
    # We need an actual QWebPage to do that, and we cannot use the one that
    # is part of the QWebView that is part of the main window, because it was
    # not created in Python so we don't have access to its "protected" function.
    # However the whole webkit initialization overhead is past and we can
    # quickly make another, use it, and discard it.
    wpage = QWebPage()
    USERAGENT = wpage.userAgentForUrl(QUrl(u'http://www.google.com'))
    wpage = None # toss the webpage


    # Display it, and run the app's event handling loop.
    main.show()
    app.exec_()
    # c'est tout!
