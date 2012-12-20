# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.00.0"
__author__  = "David Cortesi"
__copyright__ = "Copyright 2012, 2013 David Cortesi"
__maintainer__ = "?"
__email__ = "tallforasmurf@yahoo.com"
__status__ = "first-draft"
__license__ = '''
 License (GPL-3.0) :
    This file is part of CoBro.

    CoBro is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You can find a copy of the GNU General Public License at:
    <http://www.gnu.org/licenses/>.
'''

'''
CoBro (Comic Browser) is a minimal web browser designed for
convenient reading of Web Comics. The main window has a list
of comic names on the left and a web page display on the right.

Associated with each comic in the list are these persistent items:
  * the user-selected name
  * the user-provided URL of the comic
  * the date the comic was last read
  * the days of the week it may be updated
  * the SHA-1 hash of the contents of the page at the URL last time it was read
These items are saved at shutdown and reloaded at startup.

Also associated with each comic but created dynamically as the program runs:
  * the contents of the page at the comic URL
  * the date last read
  * a status, one of:
     - comic has been seen
     - comic has not been seen since it was read
     - comic is being read
     - comic could not be read (error on http request or load)

All these data are maintained in memory as a list of Comic objects.
The list is displayed to the user using the Qt model/view classes. The Python
list of Comic objects is the model; a QListView derivative displays the list.

The comic names in the list are shown in different fonts to reflect the status,
normal for seen, bold for new, italic for being-read, and strikeout for error.

When the user clicks on a comic in the list, that comic's contents text
is loaded into the web page display with QWebView::setHTML() where it is
rendered. The displayed page can be used as in any browser, e.g. the user
can click on buttons and follow links in the page. Javascript is allowed
but java is not. Browsing is "private," no cookies or caches are kept.

The list supports the following operations:
  * single-click an item to select and display that comic in the web display
  * drag and drop a selected item to reorder the list
  * double-click an item to open an Edit Comic dialog which permits
        editing the name, URL, and updays.

There is a single menu, the File menu, with these commands:
  * New Comic
        opens a dialog to collect the name, URL and updays of a new comic,
        which is added to the list at the bottom.
  * Refresh
        Apply refresh to the selected comic if any, or to all comics if
	no selection. The refresh operation is described below.
  * Delete
        After querying for OK, delete the selected comic (if any).
  * Quit

When the app loads, or when File>Refresh is chosen, or when the URL of a
comic is edited, the app pushes the model index of all, or selected, or the
edited item onto a queue and triggers a QSemaphore. A separate QThread waits
on the semaphore. While there is work on the queue it

* pops the next model index qmi from the queue and:
* signals statusChanged(qmi, WORKING)
* initiates a page-load from the item's URL
* if the load ends it error it signals statusChanged(qmi, BADCOMIC)
* else it computes the hash of the loaded page.
* if the hash is the same as before, it signals statusChanged(qmi, OLDCOMIC)
* else it updates the model with the new page data and new hash and
   signals statusChanged(qmi, NEWCOMIC)

The statusChanged signal goes to a slot in the list model which updates the
status of the item and calls dataChanged(), with the result that the list view
will call data() for new display data.

In this way, shortly after launching, the user has a list of comics ready
to be read, with the yet-unseen ones in bold. 
'''

'''
Acknowledgements and Credits

First thanks to the Van Tols of spiny.com who created Comictastic, of which
I was a long-time user and from which I've stolen all the ideas herein.

Second to Mark Summerfield for the book "Rapid GUI Development with PyQt"
which really could be called "be an instant Qt expert in 8 hours of reading."
'''

from PyQt4.QtCore import (
    pyqtSignal,
    Qt,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QMutex,
    QPoint,
    QRegExp,
    QSettings,
    QSize,
    QString,
    QStringList,
    QThread,
    QUrl,
    QVariant,
    QWaitCondition,
    SIGNAL, SLOT    
)
from PyQt4.QtGui import (
    QAction,
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFont,
    QFontInfo,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QStyledItemDelegate,
    QHBoxLayout, QVBoxLayout,
    QWidget
)
from PyQt4.QtWebKit import(
    QWebFrame, QWebPage, QWebView, QWebSettings
)    

from PyQt4.QtCore import(QFile, QIODevice, QTextStream)
from PyQt4.QtGui import(QFileDialog)
import collections # for deque
import hashlib # for sha-1
import datetime # for today numbers
import urllib2 # for reading urls, duh
import re # regular expressions
import os # getcwd


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Some message routines.

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
# Set up global variables:  First, the status values of a comic.

OLDCOMIC = 0 # status of previously-seen comic
NEWCOMIC = 1 # status of an un-viewed comic (name in bold)
BADCOMIC = 2 # status when URL couldn't be read (name strikethrough)
WORKING = 3  # status while reading a url (name in italic)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Find out the nearest font to Comic Sans and store four versions of it
# in aptly-named globals for use in displaying the comic names (see 
# ConcreteListModel.data()). Called only from the main code during startup.

FontList = [None, None, None, None] # four QFonts ordered by status

def setup_jolly_fonts():
    global FontList
    qf = QFont()
    qf.setStyleStrategy(QFont.PreferAntialias+QFont.PreferQuality)
    qf.setStyleHint(QFont.SansSerif)
    # we may or may not get that family but something sans-serif
    qf.setFamily(QString(u'Comic Sans'))
    qf.setPointSize(16)
    qf.setWeight(QFont.Normal)
    qf.setStyle(QFont.StyleNormal)
    FontList[OLDCOMIC] = QFont(qf) # copy it as the old/normal font
    FontList[NEWCOMIC] = QFont(qf) # copy it as the new/bold font
    FontList[NEWCOMIC].setWeight(QFont.Bold) # ..and make it so
    FontList[WORKING] = QFont(qf) # copy as the working/italic font
    FontList[WORKING].setItalic(True) # and make it so
    FontList[BADCOMIC] = QFont(qf) # copy as the error/strike font
    FontList[BADCOMIC].setStrikeOut(True) # and make that true

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# A small class to represent the days of the week when a comic might be
# updated. We number days Monday=0 to Sunday=6. The class is basically a
# string of 7 characters with '-' meaning "no update", except that when
# the whole string is hyphens it's "don't know" and every day is an upday.

class UpDays() :
    dayLetters = 'MTWTFSS' # actual values unimportant as long as not '-'
    empty = '-------'
    def __init__(self, setup = '-------' ) :
        self.days = setup + u'' # force a copy of the string parameter
        if len(self.days) != 7 : # e.g. it's a null string (or an error)
            self.days = UpDays.empty
    # Is this an update day? Yes if it isn't a hyphen or this is an empty object
    def testDay(self, day) :
        return (self.days == UpDays.empty) or (self.days[day] != '-')
    # Set a day to hyphen or not hyphen
    def setDay(self, day, onoff) :
        # str and unicode are immutable, so build a new string by slicing
        c = UpDays.dayLetters[day] if onoff else '-'
        self.days = self.days[:day] + c + self.days[day+1:]
    def __str__(self)  :
        return self.days
    def __repr__(self) : # just because we can...
        return 'UpDays( ' + self.__str__() + ' )'

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# The actual data behind the list model, a list of Comic objects each with
# these fields:
#   name : the name of the comic, set by the user, the display data
#          of the list.
#   url : the url of the comic as given by the user
#   sha1 : the SHA-1 hash of page ("hash" is a keyword)
#   lastwiewed : date number on which we last displayed it, or 0
#   updays : see above
#   status: old, new, bad, or working, see constants above
#   page : the contents of the single page at the url
#
# (n.b. initially I meant to use namedtuple for Comic but namedtuple is
# not really mutable except through the clumsy .replace syntax, so, just
# a stupid record class.)
#
# The string fields are --> Python ustrings <-- not QStrings.
# So when they are needed by Qt, they have to be cast to QString(thing).
# And we use Python regexes on them when needed, not QRegExps.
#

class Comic() :
    def __init__(self, n=u'', s=OLDCOMIC, u=u'', h='', d=u'-------', l=0 ) :
        self.name = n
        self.status = s
        self.url = u
        self.page = u''
        self.sha1 = bytes(h)
        self.updays = UpDays(d)
        self.lastread = l

#
# The list is initialized at startup, see ConcreteListModel.load()
#
comics = [] # list of Comic objects

#
# Qt calls the list model .data() member with an index and a "role"
# for the type of data it wants. Here define role numbers for the fields
# that the list view doesn't know about.
#

URLRole = Qt.UserRole # data() request for URL
PageRole = URLRole + 1 # data() request for page content string
HashRole = PageRole + 1 # data() request for hash string
StatusRole = HashRole + 1 # data() request for comic status
DaysRole =  StatusRole + 1 # data() request for updays
LastReadRole = DaysRole + 1 # data() request for lastread date

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Synchronization between the main thread and the refresh thread.
# The main thread acquires the mutex work_queue_lock then pushes model
# indexes onto the work_queue. Then it releases the lock and posts the
# semaphore worker_waits.
#
# The refresh thread waits on worker_waits passing work_queue_lock, so when
# it wakes up it owns the work_queue_lock. It sets worker_working true.
# It removes an item from the queue and releases the lock. After refreshing
# that one comic, it comes back for more. If the work_queue turns out to be
# empty, the thread sets worker_working false and sleeps again on worker_waits.
#
# As long as worker_working is true, the list model will refuse to allow
# drag/drop to reorder the list and File > Delete and File > Import actions,
# because they could invalidate the index the worker is using.
#

work_queue = collections.deque() # queUE (misspelled) of items needing refresh

work_queue_lock = QMutex() # lock to allow updating the queue

worker_working = False # flag to block drag/drop reordering

worker_waits = QWaitCondition() # where the worker thread awaits work

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# This is the worker thread. Its code is in its run() method. It is
# started by a call to its start() method from the main code far below.
#
class WorkerBee ( QThread ) :
    def __init__(self, parent=None):
        super(WorkerBee, self).__init__(parent)
        # save a hash which will be duplicated for each comic read
        self.hash = hashlib.sha1()
        # save today's date ordinal number for comparisons
        self.today = datetime.date.today()
        self.ordinal_today = self.today.toordinal()
        # save the ordinal of a week ago
        self.a_week_ago = self.ordinal_today - 7
        # save the number of the day of the week: UpDay uses 0-6 for Mon-Sun,
        # which is one less than the ISO day of the week numbering.
        self.day_of_week = self.today.isoweekday() - 1

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
    # Test whether: 
    #    it is an upday for this comic, or 
    #    7 days have passed since it was last read, or
    #    an upday has passed since it was last read.
    # If not, there is no need to update the page and the hash, so signal it
    # as OLDCOMIC and exit.
    # Else, read the page at its URL. If any error, signal status of BADCOMIC & exit.
    # Compute the page hash and compare to the old hash.
    # If different, save the new hash and signal status of NEWCOMIC.
    # Else signal OLDCOMIC status.

    def process_one(self, ix) :
        global read_url, OLDCOMIC, NEWCOMIC, BADCOMIC, WORKING
        global comics
        row = ix.row()
        self.emit(SIGNAL('statusChanged'), row, WORKING)
        comic = comics[row]
        days_since_read = self.ordinal_today - comic.lastread
        if (days_since_read > 7) or (0 == len(comic.page))  :
            # 7 or more days since the comic was checked -- or it hasn't been read
	    # yet this run of the app -- so do fetch the page.
            read_it = True
        else:
            # 0 to 6 days since we read this comic. Want to test those days for 
            # update-days. Suppose it has been 5 days and today is Wednesday (day 2)
            # we want to test days 2, 1, 0, 6, 5 in order. We could stop at the first
            # hit but for this little loop that's not worth the extra test and break.
            read_it = comic.updays.testDay(self.day_of_week) # is TODAY an update day?
            for i in range (days_since_read) :
                read_it |= comic.updays.testDay( (self.day_of_week - i) % 7 )
        if not read_it : 
            # not an update day and recently seen
            self.emit(SIGNAL('statusChanged'), row, OLDCOMIC)
            return
        if not self.read_url(comic) :
            # some problem reading the comic, mark it bad and quit
            self.emit(SIGNAL('statusChanged'), row, BADCOMIC)
            return
        # Successful read, set the date of the new hash we are about to make
        comic.lastread = self.ordinal_today
        sha1 = self.hash.copy() # make a new, empty hash gizmo
        sha1.update(comic.page) # feed it the page we just read
        new_hash = bytes(sha1.digest()) # save the resulting hash signature
        if comic.sha1 != new_hash :
            # The comic's web page has changed since it was seen.
            comic.sha1 = new_hash
            self.emit(SIGNAL('statusChanged'), row, NEWCOMIC)
        else :
            # it has not changed.
            self.emit(SIGNAL('statusChanged'), row, OLDCOMIC)
        return

    # Given a comic, read the single html page at its url and save it in
    # the comic's page string. Note that the commercial sites (comics.com,
    # ucomics.com, gocomics.com) will not reply without a valid user-agent
    # string. The solo sites (smbc, xkcd etc) don't seem to care.
    
    def read_url(self,comic) :    
        if 0 == len(comic.url) : # URL is a null string
            return False # couldn't read that
        try:
            # Create an http "request" object and load it with a user-agent
            ureq = urllib2.Request(comic.url)
            ureq.add_header('User-agent', 'Mozilla/5.0')
            # Execute the request by opening it, returning a "file" to the page
            furl = urllib2.urlopen(ureq)
        except:
            # failed to open the URL: return False and do not change
            # the page value. TBS: error analysis and user notification!
            return False
        # opened the URL, now read it and convert to a u-string.
        # TBS: we need to read the first 1K bytes and look for
        # an "encoding=whatever" and read the rest using that encoding,
        # but for now just assume it's good old Latin-1.
        encoding = u'ISO-8859-1'
        comic.page = b''
        try:
            comic.page = bytes(furl.read())
        except:
            # TBS: error analysis and user notification (status bar?)
            pass
        finally:
            furl.close()
        return 0 != len(comic.page)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the concrete list model by subclassing QAbstractListModel
# and gettin' real -- specifically by implementing these abstract methods
# (see qthelp:model-view-programming.html#model-subclassing-reference)
#
# Basic model/view methods
#   flags : return isEnabled | isSelectable | isEditable ? isDragEnabled?
#   rowCount() : return the number of items in the list.
#   data(modelIndex, role) : return values for the display, tooltip,
#     statustip, whatsthis, textalignment, font, and user roles
#   setData(modelIndex, role) : set the data at an index and emit the
#     dataChanged signal -- used mainly by the worker thread
# Methods used by mainline code to load and save the model
#   load(settings) : load the comics list from a settings object
#   save(settings) : save the comics list into settings
# Methods required to implement drag/drop reordering
#   insertRows(modelIndex, parent) -- add an empty row
#   removeRows(modelIndex, parent) -- remove a row
#   itemData(modelIndex) -- return all values of a comic as a dict
#   setItemData(modelIndex, dict) -- fill in a comic from a dict of values
#
# Also implemented: a custom Item Delegate to perform editing. This
# class definition follows ConcreteListModel.
#

class ConcreteListModel ( QAbstractListModel ) :

    # minimal __init__ but see load()
    def __init__(self, parent=None):
        super(ConcreteListModel, self).__init__(parent)

    # Save the current list of comics. We save into the settings object, which
    # in Windows means, into the Registry under Tassosoft/Cobro (the company
    # and app names set at startup in the app object).
    # In Mac OS, see ~/Library/Preferences/tassos-oak.com/Cobro.plist
    # In Linux see $HOME/.config/Tassosoft/Cobro.conf
    # We use the QSettings convenience function beginWriteArray to write
    # the array of comics as comics/1/name, comics/1/url, etc. Before saving
    # we use remove to clear everything in that group, because if we don't,
    # deleted comics will come back like zombies next time we start up.
    def save(self, settings) :
        global comics
        settings.beginGroup(u'comiclist')
        settings.remove('')
        settings.endGroup()
        settings.sync() # not supposed to be needed but does no harm
        settings.beginGroup(u'comiclist')
        settings.beginWriteArray(u'comics')
        for i in range(len(comics)) :
            settings.setArrayIndex(i)
            settings.setValue(u'name', QString(comics[i].name))
            settings.setValue(u'url', QString(comics[i].url))
            settings.setValue(u'sha1', QByteArray(comics[i].sha1))
            settings.setValue(u'updays', QString(str(comics[i].updays)))
            settings.setValue(u'lastread', QVariant(comics[i].lastread))
        settings.endArray()
        settings.endGroup()
        settings.sync() # not supposed to be needed but does no harm

    # Load the comics list from the saved settings, see save() below. What we
    # get via QSettings.value is QStrings, which we convert to python while
    # creating the Comic instance.
    def load(self, settings) :
        global comics, Comic
        self.beginResetModel()
        settings.beginGroup(u'comiclist')
        count = settings.beginReadArray(u'comics')
        for i in range(count) :
            settings.setArrayIndex(i)
            name = settings.value(u'name').toString()
            url = settings.value(u'url').toString()
            sha1 = settings.value(u'sha1').toByteArray()
            updays = settings.value(u'updays').toString()
            (lastread, ok) = settings.value(u'lastread').toInt()
            comic = Comic(n = unicode(name),
                          s = OLDCOMIC,
                          u = unicode(url),
                          h = bytes(sha1),
                          d = unicode(updays),
                          l = lastread)
            comics.append(comic)
        settings.endArray()
        settings.endGroup()
        self.endResetModel()

    # Here we implement the methods of QAbstractListModel class that convert this
    # from an abstract list to a concrete one. First up, flags which tells the view
    # what can be done with any given item. All items are enabled and allow editing,
    # selecting, dragging. If the query is for the list parent, NOT an ordinary list
    # item, we allow dropping as well. This is what enables drag-to-reorder the list.
    def flags(self, parent) :
        basic_flag = Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if parent.isValid() :
            return basic_flag
        return basic_flag | Qt.ItemIsDropEnabled

    # Next, rowCount just says how many rows there are in the model data. We use this
    # from our own code later as well. Note the count of rows in an ordinary item is 0;
    # only the count for the whole list is meaningful.
    def rowCount(self, parent):
        global comics
        if parent.isValid() :
            return 0
        return len(comics)

    # The data method is called when Qt needs to (re)display the list data.
    # After initialization, that is only when scrolling or if data changes.
    def data(self, index, role) :
        global comics, FontList, URLRole
        comic = comics[index.row()] # save a few method calls
        if role == Qt.DisplayRole :
            # Data for the visible comic, i.e. its name.
            return QString(comic.name)
        if role == Qt.TextAlignmentRole :
            return Qt.AlignLeft
        if role == Qt.FontRole :
            font = FontList[comic.status]
            return QVariant(font)
        if (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
            # Data for the tooltip (pops up on hover) is the URL
            return QString(comic.url)
        if role == URLRole :
            return QString(comic.url)
        if role == DaysRole :
            return str(comic.updays)
        return QVariant()

    # setData is the normal means of modifying model data. The list view doesn't call
    # it directly; it is called from the item delegate (below) when an item is edited,
    # and also by our main window code to implement File>New Comic, after creating an
    # empty Comic object. It is also called from the statusChanged slot to change the
    # status of a comic on a signal from the worker thread. The result of that is the
    # view will call data above to get the comic name and its font, changing the font
    # to reflect the status.
    # Input is a model index, a role, and a QVariant of data for that role.
    def setData(self, index, variant, role) :
        global comics, OLDCOMIC
        comic = comics[index.row()]
        doSignal = True # should we show data changed?
        if role == Qt.DisplayRole :
            # Set a new or changed name
            comic.name = unicode(variant.toString())
        elif role == URLRole :
            # user edited the URL string
            comic.url = unicode(variant.toString())
            comic.page = u'' # don't know contents now
            comic.hash_string = u'' # don't know the hash now
            comic.status = OLDCOMIC # assume not new until refreshed
        elif role == StatusRole :
            # change the status of a comic. QVariant.toInt returns both
            # the value and a boolean. Unlike QVariant.toString.
            (comic.status, ok) = variant.toInt()
        elif role == DaysRole :
            # user edited the days, we get a QVariant of a string of days.
            day_letters = unicode(variant.toString())
            comic.updays = UpDays(day_letters)
            doSignal = False # no change to visible list view
        elif role == LastReadRole :
            (comic.lastread, ok) = variant.toInt()
            doSignal = False # no change to visible
        # If the visible list has changed, the list view should update.
        # The signal arguments are the top-left and bottom-right changed
        # items, which is simply the one changed item.
        if doSignal :
            self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),index,index)

    # This slot receives the statusChanged(row,stat) signal from the worker
    # thread. It just passes that on to setData() above. It sets the status and
    # signals dataChanged, which makes the view repaint the item with a different font.
    def statusChangedSlot(self,row,status) :
        ix = self.createIndex(row,0)
        self.setData(ix, QVariant(status), StatusRole)

    # The inserRows/removeRows methods are essential to internal drag and drop.
    # In order to not have any possibility of drag/drop taking place while
    # an item is being refreshed -- which could invalidate the index that the
    # refresh thread is using -- these functions don't do anything unless the
    # refresh thread is sleeping.
    def insertRows(self, row, count, parent) :
        global Comic, comics, worker_working
        #print('insertRows({0} for {1}: {0}..{2})'.format(row,count,row+count-1))
        if worker_working :
            return False
        # The worker thread is asleep and will not wake up until the user
        # requests a refresh which she cannot do while she is dragging an item.
        self.beginInsertRows(parent, row, row+count-1 )
        # have to do this one at a time to insert scalars, not a list
        for i in range(count):
            comics.insert(row,Comic())
        self.endInsertRows()
        return True

    def removeRows(self, row, count, parent) :
        global comics, worker_working
        print('removeRows({0} for {1}: {0}..{2})'.format(row,count,row+count-1))
        if worker_working :
            return False
        self.beginRemoveRows(parent, row, row+count-1)
        comics[row : row+count ] = []
        self.endRemoveRows()
        return True

    # The itemData method is a shortcut for the view when it is dragging an item:
    # it calls itemData to get a collection of all an item's properties in one bag.
    # In the Qt docs, itemData returns a QMap, the Qt equivalent of a dict.
    # In PyQt, it just returns a dict. In this case, a dict that contains
    # all the fields of a given comic, so that setItemData can reproduce that
    # comic in a new row.
    def itemData(self, index) :
        global comics, StatusRole, URLRole, PageRole, HashRole, DaysRole, LastViewRole
        comic = comics[index.row()]
        item_dict = {
            Qt.DisplayRole : comic.name,
            StatusRole : comic.status,
            URLRole  : comic.url,
            PageRole : comic.page,
            HashRole : comic.sha1,
            DaysRole : str(comic.updays),
            LastReadRole : comic.lastread
        }
        print('itemData row {0}'.format(index.row()))
        return item_dict

    # Here we receive the data prepared by itemData() above. However by the
    # time it comes here it has been Qt-ized: still a Python dict with keys that
    # are ints (Role numbers) but the values are QVariants.
    #
    # The Qt docs say that setData() above must emit the dataChanged signal.
    # They do not say so for setItemData(), so I won't. After all, I think
    # this is only called by drag/drop, in which case Qt should darn well 
    # know that data has been changed and needs to be redisplayed.
    def setItemData(self, index, qdict) :
        global comics, UpDays
        print('setItemData row {0}'.format(index.row()))
        dbg = index.row()
        comic = comics[index.row()]
        comic.name = unicode( qdict[Qt.DisplayRole].toString() )
        (comic.status, ok) = qdict[StatusRole].toInt()
        comic.url = unicode( qdict[URLRole].toString() )
        comic.sha1 = unicode( qdict[HashRole].toString() )
        comic.updays = UpDays( unicode( qdict[DaysRole].toString() ) )
        (comic.lastread, ok) = qdict[LastReadRole].toInt()
        return True

# So, WTF is a custom delegate? A widget that represents a data item when
# when that item needs to be displayed or edited. When the user double-clicks an item
# in the view, the view instantiates a custom delegate to display and optionally edit
# the item's contents.
# We implement this in stages. First, a class UpDayWidget that encapsulates the Qt
# definition of 7 checkboxes with day name abbreviations above them, plus
# methods for loading and reading-out the boxes.

class UpDayWidget(QWidget) :
    def __init__(self, parent=None):
        super(UpDayWidget, self).__init__(parent)
        self.cbs = [QCheckBox(),QCheckBox(),QCheckBox(),QCheckBox(),
                    QCheckBox(),QCheckBox(),QCheckBox()]
        hb = QHBoxLayout()
        hb.addStretch(1) # stretch left and right keeps them all together
        for i in range(7) :
            vb = QVBoxLayout()
            vb.addWidget(QLabel(['Mo','Tu','We','Th','Fr','Sa','Su'][i]))
            vb.addWidget(self.cbs[i])
            hb.addLayout(vb)
        hb.addStretch(1)
        self.setLayout(hb)
    # Load the widget from an UpDays instance
    def loadFromUpday(self, upday) :
        for i in range(7) :
            self.cbs[i].setChecked(upday.testDay(i))
    # Create an UpDays instance loaded from the seven checkboxes
    def returnUpday(self):
        ud = UpDays()
        for i in range(7):
            ud.setDay(i, self.cbs[i].isChecked())
        return ud

# Often a delegate is a simple widget e.g. a combobox or spinbox or lineedit.
# We need to offer three fields, the name, URL, and the 7 days, so we make a
# little Widget with two lineEdits and matching labels, and an UpDayWidget
# underneath.  This same widget is also used by File > New Comic.

class EditWidget(QWidget) :
    def __init__(self, parent=None):
        super(EditWidget, self).__init__(parent)
        self.nameEdit = QLineEdit()
        self.urlEdit = QLineEdit()
        hb1 = QHBoxLayout()
        hb1.addWidget(QLabel(QString(u'Comic Name:')))
        hb1.addWidget(self.nameEdit)
        hb2 = QHBoxLayout()
        hb2.addWidget(QLabel(QString(u'Comic URL : ')))
        hb2.addWidget(self.urlEdit)
        vb1 = QVBoxLayout()
        vb1.addLayout(hb1)
        vb1.addLayout(hb2)
        self.udWidget = UpDayWidget()
        vb1.addWidget(self.udWidget)
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
        super(ItemDelegate, self).__init__(parent)

    # Create the editing widget with empty data
    def createEditor(self, parent, style, index):
        return EditWidget()

    # Load the edit widget with data from the given row
    def setEditorData(self, edit_widget, index) :
        global comics
        comic = comics[index.row()]
        edit_widget.nameEdit.setText(QString(comic.name))
        edit_widget.urlEdit.setText(QString(comic.url))
        edit_widget.udWidget.loadFromUpday(comic.updays)

    # Return the data to the model. We do this by calling setData()
    # in the model, which is the concreteModel class defined above.
    # However, we check here that the user actually made
    # a change in the data before calling the model to update itself.
    def setModelData(self, edit_widget, model, index ) :
        global comics, URLRole, DaysRole
        comic = comics[index.row()]
        edit_name = unicode(edit_widget.nameEdit.text())
        if edit_name != comic.name :
            model.setData( index, QVariant(edit_widget.nameEdit.text()), Qt.DisplayRole )
        edit_url = unicode(edit_widget.urlEdit.text())
        if edit_url != comic.url :
            model.setData( index, QVariant(edit_widget.urlEdit.text()), URLRole )
        model.setData( index, QVariant(str(edit_widget.udWidget.returnUpday())), DaysRole )

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the view onto the above list model. The QListView in Qt's scheme takes
# on all the responsibility for displaying the list, keeping it up to date when the
# model data changes, handling drag/drop, selecting and scrolling.

class CobroListView(QListView) :
    def __init__(self, model, browser, parent=None):
        super(CobroListView, self).__init__(parent)
        # Save reference to our browser window for use in itemClicked
        self.webview = browser
        # Set all the many properties of a ListView/AbstractItemView in
        # alphabetic order as listed in the QAbstractItemView class ref.
        # alternate the colors of the list, like greenbar paper (nostalgia)
        self.setAlternatingRowColors(True)
        # auto-scroll on dragging/selecting, use an explicit margin because
        # the default seemed insensitive to me
        self.setAutoScroll(True)
        self.setAutoScrollMargin(12)
        # Trying to set up for internal drag/drop to reorder the list.
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        # What starts an edit? 
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        # The following creates the custom delegate and sets a pointer to it.
        self.setItemDelegate(ItemDelegate())
        # connect to the concrete model to display
        self.setModel(model)
        # list view: resize mode
        self.setResizeMode(QListView.Adjust)
        # allow ctl-click, shift-click, and drag for multi-selections
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # not setting: selection model, tab key behavior, text elide mode
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        # list view: uniform item sizes
        self.setUniformItemSizes(True)
        # list view: list, not icons
        self.setViewMode(QListView.ListMode)
        # list view: allow movement (overrides static set by above)
        self.setMovement(QListView.Free)
        # handle click-on-item to display a comic
        self.connect(self,SIGNAL('clicked(QModelIndex)'),self.itemClicked)

    # If I read the doc correctly, this signal is generated as a result of
    # a mouseReleaseEvent when the mouse is over a list item (and not over
    # something else, like a scrollbar). This is the time to display the
    # item URL in our web browser.

    def itemClicked(self, index) :
        global comics, OLDCOMIC, NEWCOMIC, BADCOMIC, StatusRole, LastViewRole
        comic = comics[index.row()]
        if (comic.status == OLDCOMIC) or (comic.status == NEWCOMIC) :
            # so, not a bad comic or a working comic
            if len(comic.page) :
                # Pass the current page data into our web viewer. First tell
                # it to stop, if it happens to be loading something else.
                self.webview.page().triggerAction(QWebPage.Stop)
                self.webview.setHtml( QString(comic.page), QUrl(QString(comic.url)) )
                self.model().setData(index, QVariant(OLDCOMIC), StatusRole)
            else :
                # No page data has been read, put up a default message
                self.webview.setHtml( QString('''
		<p style='text-align:center;margin-top:8em;'>
		Sorry, I have no data for this comic. Try refreshing it.
		</p>'''),QUrl())
        elif comic.status == BADCOMIC :
            # Comic had an error on the last refresh
            self.webview.setHtml( QString('''
	    <p style='text-align:center;margin-top:8em;'>
	    Sorry, there was some problem reading the URL for that comic.
	    Try refreshing it or test its URL in another browser.</p>'''),
                                  QUrl())
        else:
            # Comic is being refreshed
            self.webview.setHtml( QString('''
	    <p style='text-align:center;margin-top:8em;'>
	    I'm working on it, alright? Geez, gimme a sec...</p>'''),
                                  QUrl())

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the web page display, based on QWebView with added behaviors.
# Initialize it with welcome/usage/license message.
#
class CobroWebPage(QWebView) :
    def __init__(self, status, bar, parent=None) :
        global FontList, OLDCOMIC
        super(CobroWebPage, self).__init__(parent)
        self.statusLine = status
        self.needUrlStatus = False
        self.progressBar = bar
        # make page unmodifiable
        self.page().setContentEditable(False)
        # set up the default font
        qfi = QFontInfo(FontList[OLDCOMIC])
        self.settings().setFontFamily(QWebSettings.StandardFont, qfi.family())
        self.settings().setFontSize(QWebSettings.DefaultFontSize, 16)
        self.settings().setFontSize(QWebSettings.MinimumFontSize, 6)
        self.settings().setFontSize(QWebSettings.MinimumLogicalFontSize, 6)
        self.textZoomFactor = 1.0
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
        self.connect( self, SIGNAL(u'loadStarted()'), self.startBar )
        self.connect( self, SIGNAL(u'loadProgress(int)'), self.rollBar )
        self.connect( self, SIGNAL(u'loadFinished(bool)'), self.endBar )
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
        # Load a greeting message
        self.setHtml(QString(u'''<div style='text-align:center;'>
<h2>Welcome to CoBro!</h2>
<p>Use File &gt; New Comic to specify a comic by name and URL.</p>
<p>Single-click a comic to display its page in this browser. When browsing,
use ctl-[ for "back" and ctl-] for "forward" (cmd-[ and cmd-] on a mac).</p>
<p>Change the list order by dragging and dropping.</p>
<p>Double-click a comic to edit	its name, URL, or publication days.</p>
<p>To "refresh" a comic means to read its web page and see if it is
different from the last time.</p><ul><li>
While it is being read its name is <i>italic</i>.</li><li>
After reading, if we think it is different from the last tiem, its name turns <b>bold</b>.
</li><li>If there is a problem reading it, its name is <strike>lined-out</strike>.</li></ul>
<p>All comics are refreshed at startup. Use File > Refresh to refresh a new or edited comic.</p>
<p>Comic definitions are saved in some magic settings place
(Registry, Library/Preferences, ~/.config)</p>
<p>Use File > Export to write definitions of the selected comics to a text file.</p>
<p>Use File > Import to read definitions from a text file and add them to the list
(or to replace them when the name's the same).</p>
<p>That's it! Enjoy!</p>
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
                             '''))
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

    # Re-implement the parent's keyPressEvent in order to provide
    # font-size-zoom from ctl-plus/minus, and browser back/forward.
    # For the font size, we initialize the view at 16 points and
    # the textSizeMultiplier at 1.0. Each time the user hits ctl-minus
    # we deduct 0.0625 from the multiplier, and for each ctl-+ we add 0.0625
    # (1/16) to the multiplier. This ought to cause the view to change up or
    # down by about one point. We set a limit of 0.375 (6 points) at the low
    # end and 4.0 (64 points) at the top.
    def keyPressEvent(self, event):
	kkey = int( int(event.modifiers()) & self.keypadDeModifier) | int(event.key())
	if (kkey in self.zoomKeys) : # ctrl-plus/minus
	    event.accept()
	    zfactor = 0.0625 # zoom in
	    if (kkey == self.ctl_minus) :
		zfactor = -zfactor # zoom out
	    zfactor += self.textZoomFactor
	    if (zfactor > 0.374) and (zfactor < 4.0) :
		self.textZoomFactor = zfactor
		self.setTextSizeMultiplier(self.textZoomFactor)
	elif (kkey in self.backKeys) :
	    event.accept()
	    if self.page().history().canGoBack() :
		self.page().history().back()
	elif (kkey in self.forwardKeys) :
	    event.accept()
	    if self.page().history().canGoForward() :
		self.page().history().forward()
	else: # not a key we support, so,
	    event.ignore()
	super(CobroWebPage, self).keyPressEvent(event)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the application window incorporating the list and webview.
# The one class of this object also catches shut-down.
#
# In order to have a standard menu bar we have to use QMainWindow.
# That class requires us to supply the real window contents as a widget
# (not just a layout) so we create that widget first.
#
class theAppWindow(QMainWindow) : # or maybe, QMainWindow?
    def __init__(self, settings, parent=None) :
        super(theAppWindow, self).__init__(parent)
        # Save the settings instance for use at shutdown (see below)
        self.settings = settings
        # Here store the last-used directory to start file selection dialogs
        self.starting_dir = os.getcwd()
        # Create the list model.
        self.model = ConcreteListModel()
        # Tell the list to load itself from the settings
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
        # access to the progress and status br
        self.page = CobroWebPage(self.statusLine, self.progressBar)
        # Create the List View, which needs access to the model (for comics)
        # and the web view (to display a comic)
        self.view =  CobroListView(self.model, self.page)
        # Lay out our widget: the list on the left and webview on the right,
        # underneath it a status line and a progress bar. 
        hb = QHBoxLayout()
        hb.addWidget(self.view,0) # no stretch
        hb.addWidget(self.page,1) # all available stretch
        vb = QVBoxLayout()
        vb.addLayout(hb,1) # all stretch
        hb2 = QHBoxLayout()
        hb2.addWidget(self.statusLine,1) # all stretch
        hb2.addWidget(self.progressBar,0)
        vb.addLayout(hb2,0) # no stretch
        central.setLayout(vb)
        # Make central our central widget
        self.setCentralWidget(central)
        # restore saved or default window geometry
        self.resize(self.settings.value("cobro/size",
                                        (QSize(600,400))).toSize() )	
        self.move(self.settings.value("cobro/position",
                                      QPoint(100, 100)).toPoint() )
        # Create a menubar and populate it with our one (1) menu
        menubar = QMenuBar()
        menubar.setNativeMenuBar (True) # identify with OSX bar
        file_menu = menubar.addMenu(u"File")
        #   Create the New action
        file_new_action = QAction(u"New Comic",self)
        file_new_action.setShortcut(QKeySequence.New)
        file_new_action.setToolTip(u"Define new comic at end of list")
        self.connect(file_new_action,SIGNAL(u"triggered()"),self.newComic)
        file_menu.addAction(file_new_action)
        #   Create the Refresh action
        file_refresh_action = QAction(u"Refresh",self)
        file_refresh_action.setShortcut(QKeySequence.Refresh) # == F5, ^r
        file_refresh_action.setToolTip(u"Reload the web pages of all or selected comics")
        self.connect(file_refresh_action, SIGNAL(u"triggered()"), self.refresh)
        file_menu.addAction(file_refresh_action)
        #   Create the Delete action
        file_delete_action = QAction(u"Delete",self)
        file_delete_action.setShortcut(QKeySequence.Delete) # DEL key
        file_delete_action.setToolTip(u"Delete the selected comics")
        self.connect(file_delete_action, SIGNAL(u"triggered()"), self.delete)
        file_menu.addAction(file_delete_action)
        #  Create the Export action
        file_export_action = QAction(u"Export selected",self)
        file_export_action.setToolTip(u"Export the selected comics")
        self.connect(file_export_action, SIGNAL(u"triggered()"), self.file_export)
        file_menu.addAction(file_export_action)
        #  Create the Import action
        file_export_action = QAction(u"Import",self)
        file_export_action.setToolTip(u"Import comic definitions from a file")
        self.connect(file_export_action, SIGNAL(u"triggered()"), self.file_import)
        file_menu.addAction(file_export_action)
        self.setMenuBar(menubar)
        # Create our worker thread and start it. Connect its signal to the
        # slot in the model, and kick it off.
        self.worker = WorkerBee()
        self.connect(self.worker,SIGNAL('statusChanged'),
                     self.model.statusChangedSlot)
        self.worker.start() # start the worker
        self.refreshAll() # give worker some work, lazy thing

    # Do refresh-all -- not a menu action but done at startup after load
    def refreshAll(self):
        n = self.model.rowCount(QModelIndex())
        work_queue_lock.lock()
        for i in range(n) :
            ix = self.model.createIndex(i,0)
            work_queue.appendleft(ix)
        work_queue_lock.unlock()
        worker_waits.wakeOne()
            
    # Implement the File > Refresh action:
    def refresh(self) :
        global work_queue, work_queue_lock, worker_waits
        
        # Get a list of the model indexes of the current selection
        ixlist = self.view.selectedIndexes()
        # Run through the list and for each, do the refresh thing
        for ix in ixlist :
            work_queue_lock.lock()
            work_queue.appendleft(ix)
            work_queue_lock.unlock()
        worker_waits.wakeOne()
            

    # Implement the File > New Comic action: Create a custom dialog based on
    # the same edit widget as used by the custom delegate, but augmented with
    # OK and Cancel buttons. Display it. If the dialog is accepted, call the
    # model's insertRows method to add a row at the end, then load that empty
    # Comic from the dialog values. We can do this while the refresh thread
    # is running.

    def newComic(self) :
        dlg = QDialog(self, Qt.Dialog)
        edw = EditWidget()
        bts = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        vb = QVBoxLayout()
        vb.addWidget(edw)
        vb.addWidget(bts)
        dlg.setLayout(vb)
        self.connect(bts, SIGNAL('accepted()'), dlg, SLOT('accept()'))
        self.connect(bts, SIGNAL('rejected()'), dlg, SLOT('reject()'))
        ans = dlg.exec_()
        if ans == QDialog.Accepted :
            j = self.model.rowCount(QModelIndex()) # count of rows now
            self.model.insertRows(j,1,QModelIndex()) # append new row
            ix = self.model.createIndex(j,0) # create model index of new row
            self.model.setData( ix, QVariant(edw.nameEdit.text()), Qt.DisplayRole )
            self.model.setData( ix, QVariant(edw.urlEdit.text()), URLRole )
            self.model.setData( ix, QVariant(str(edw.udWidget.returnUpday())), DaysRole )

    # Implement the File > Delete action: Make sure the refresh worker
    # isn't running. Get the current selection as a list of model indexes.
    # Query the user if she's serious. If so call the model one index at
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
        warn_text = QString(u'Delete comic "')
        warn_text.append( self.model.data(ix_list[0],Qt.DisplayRole) )
        if nix == 1 :
            warn_text.append( u'"?' )
        else :
            warn_text.append( u'" and {0} more?'.format( nix-1 ) )
        ok = okCancelMsg(warn_text, "This cannot be undone.")
        if not ok : return  
        # Well OK then. Do not trust Qt to give us a selection list
        # in row order, it would be ascending anyway and we want descending
        # so use Python to sort it.
        ix_list.sort(key = QModelIndex.row, reverse = True)
        for ix in ix_list :
            self.model.removeRows(ix.row(), 1, QModelIndex())
        # and that's it
        return

    # Implement the File > Export action. Get the list of selected comic indexes.
    # (If it is empty, return.) Ask the user to provide a file to write into.
    # The starting directory is the last directory we've used for export or import.
    # Write a text file with one line per selected comic.
    def file_export(self) :
        global comics, URLRole, DaysRole
        # some text that we put in every file to document the syntax.
        boilerplate = '''
# A comic file is a latin-1 (ISO-8892-1) or ASCII file. In it, each
# comic is defined on a single line by two or three quoted strings.
# The first string is the comic name. The second string is its URL.
# The optional third string is exactly seven letters long and stands for the days
# of the week Monday to Sunday. A hyphen means "no update" and a non-hyphen
# means "updates this day" so: 'Bug Comic', 'http://www.bugcomic.com', 'MTWTF--'
# When the third string is omitted the default is "test for update every day".
# The strings are delimited by 'single' or "double" quotes (sorry no guillemets)
# and separated by spaces and/or commas. All lines that don't match are ignored
# and can be used as commentary, like these lines.
'''
        ix_list = self.view.selectedIndexes()
        nix = len(ix_list)
        # If nothing is selected, bail. (To export-all, select all first)
        if 0 == nix : return
        msg = QString(u'Specify a text file to receive Comic definitions')
        qpath = QFileDialog.getSaveFileName(self,msg,QString(self.starting_dir))
        if qpath.isNull() : return # user cancelled dialog
        ppath = unicode(qpath) # get python string.
        self.starting_dir = os.path.dirname(ppath) # note starting dir for next time
        try:
            # python 3.3: fobj = open(ppath, 'w', encoding='iso-8859-1', errors='ignore')
            fobj = open(ppath, 'w') # python 2.7
        except :
            return # can't open it? assume the OS has given a message
        try:
            fobj.write(boilerplate)
            for ix in ix_list :
                fobj.write("'{0}', '{1}', '{2}'\n".format(
                    str(self.model.data(ix,Qt.DisplayRole) ),
                    str(self.model.data(ix,URLRole) ),
                    str(self.model.data(ix,DaysRole) ) ) )
        finally:
            fobj.close()

    # Implement the File > Import action. Tell the view to clear the selection.
    # As the user to specify a file to read. (Exit if cancel.) Use as the starting
    # directory the last directory we've used. Read the file by lines, testing each
    # against an RE. If the RE matches, create a new comic using the strings from the
    # match. Look for a comic with the same name and replace it if found, or append.
    def file_import(self) :
        global comics, URLRole, DaysRole, worker_working
        if worker_working :
            warningMsg("Cannot import during refresh",
                       "please wait until the refresh process finishes")
            return
        retext = '''^\\s*[\'"]([^\'"]+?)[\'"][ ,]+[\'"]([^\']+?)[\'"]([ ,]+[\'"]([\\-A-Z]{7})[\'"])?\\s*$'''
        line_test = re.compile(retext)
        msg = QString(u'Choose a file of Comic definitions:')
        qpath = QFileDialog.getOpenFileName(self,msg,QString(self.starting_dir))
        if qpath.isNull() : return # user cancelled dialog
        ppath = unicode(qpath) # get python string.
        self.starting_dir = os.path.dirname(ppath) # note starting dir for next time
        try:
            # Python 3.3: fobj = open(ppath,'r',encoding='iso-8859-1',errors='ignore')
            fobj = open(ppath,'rU')
        except:
            return # can't open the file? screw it.
        self.view.clearSelection()
        try:
            line = fobj.readline()
            while len(line) :
                line_match = line_test.match(line)
                if line_match is not None:
                    # we have a comic line, get its parts.
                    line_name = line_match.group(1)
                    line_url = line_match.group(2)
                    line_days = line_match.group(4) if len(line_match.group(4)) else '-------'
                    # see if it exists already. search directly in the list rather than
                    # going all around the barn calling self.model.data().
                    j = self.model.rowCount(QModelIndex())
                    for i in range(j) :
                        if comics[i].name == line_name :
                            j = i
                            break
                    if j == self.model.rowCount(QModelIndex()) :
                        # no match on name, append a row j
                        self.model.insertRows(j,1,QModelIndex())
                    # put the data from the line in the old or new Comic
                    ix = self.model.createIndex(j,0) # create model index of new row
                    self.model.setData( ix, QVariant(line_name), Qt.DisplayRole )
                    self.model.setData( ix, QVariant(line_url), URLRole )
                    self.model.setData( ix, QVariant(line_days), DaysRole )
                line = fobj.readline()
        finally:
            fobj.close()
                
                
            
        
    # -----------------------------------------------------------------
    # reimplement QWidget::closeEvent() to save the current comics.
    def closeEvent(self, event):
        self.settings.setValue("cobro/size",self.size())
        self.settings.setValue("cobro/position", self.pos())
        self.model.save(self.settings)

if __name__ == "__main__":
    import sys
    # setup the font globals
    setup_jolly_fonts()
    # create an app
    app = QApplication(sys.argv)
    app.setOrganizationName("Tassosoft")
    app.setOrganizationDomain("tassos-oak.com")
    app.setApplicationName("Cobro")
    # access the settings
    settings = QSettings()
    # construct the GUI
    main = theAppWindow(settings) 
    main.show()
    app.exec_()
    # c'est tout!