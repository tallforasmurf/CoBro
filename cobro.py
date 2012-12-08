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
    QModelIndex,
    QMutex,
    QPoint,
    QRegExp,
    QSettings,
    QSize,
    QString,
    QStringList,
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
    QFont,
    QFontInfo,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMenu,
    QMenuBar,
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
import collections
    
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
# string of 7 characters with '-' meaning "no update".

class UpDays() :
    dayLetters = 'MTWTFSS' # actual values unimportant as long as not '-'
    def __init__(self, setup = '-------' ) :
	self.days = setup + u'' # force a copy of the string parameter
	if len(self.days) != 7 : # e.g. it's a null string
	    self.days = '-------' 
    # Return true for a day that isn't a hyphen
    def testDay(self, day) :
	return self.days[day] != '-'
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
#   lastread : date on which we last read it, or 0
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
    def __init__(self, n=u'', s=0, u=u'', h=u'', d=u'-------', l=0 ) :
        self.name = n
        self.status = s
        self.url = u
        self.page = u''
        self.sha1 = h
        self.updays = UpDays(d)
	self.lastread = l

#
# The list is initialized when the model is created, see ConcreteListModel.load()
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

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Given a comic, read the single html page at its url and save it in
# the comic's page string. Note that the commercial sites (comics.com,
# ucomics.com, gocomics.com) will not reply without a valid user-agent
# string. The solo sites (smbc, xkcd etc) don't seem to care.

import urllib2

def read_url(comic) :    
    if 0 == len(comic.url) : # URL is not a null string
	return False
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
    # Eventually we need to read the first 1K bytes and look for
    # an "encoding=whatever" and read the rest using that encoding,
    # but for now just assume it's good old Latin-1.
    encoding = u'ISO-8859-1'
    comic.page = u''
    try:
	comic.page = unicode(furl.read(), encoding, 'ignore')
    except:
	# TBS: error analysis and user notification (status bar?)
	pass
    finally:
	furl.close()
    return 0 != len(comic.page)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Synchronization between the main thread and the refresh thread.
# The main thread acquires the mutex work_queue_lock, and does two things:
# pushes model indexes onto the work_queue, and sets the flag worker_working.
# Then it releases the lock and posts the semaphore worker_waits. As long as
# worker_working is true, the list model will refuse to allow drag/drop
# to reorder the list, because that could mess with comics the worker is using.
#
# The refresh thread waits on worker_waits passing work_queue_lock, so when
# it wakes up it owns the work_queue_lock. It removes an item from the queue
# and releases the lock. After refreshing one comic, it comes back for more
# work. If the work_queue turns out to be empty, the thread sets worker_working
# false and sleeps.

work_queue = collections.deque() # queUE (misspelled) of items needing refresh

work_queue_lock = QMutex() # lock to allow updating the queue
worker_working = False # flag to block drag/drop reordering
worker_waits = QWaitCondition() # where the worker thread awaits work

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# TBS: Refresh thread code goes here

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
#   insertRow(modelIndex, parent) -- add an empty row
#   removeRow(modelIndex, parent) -- remove a row
#   itemData(modelIndex) -- return all values of a comic as a dict
#   setItemData(modelIndex, dict) -- fill in a comic from a dict of values
#
# Also implemented: a custom Item Delegate to perform editing. This
# class definition follows ConcreteListModel.
#

class ConcreteListModel ( QAbstractListModel ) :
    # Flag returned for all items
    itemFlag = Qt.ItemIsEnabled \
            | Qt.ItemIsSelectable \
            | Qt.ItemIsEditable \
            | Qt.ItemIsDragEnabled \
            | Qt.ItemIsDropEnabled

    # minimal __init__ but see load()
    def __init__(self, parent=None):
        super(ConcreteListModel, self).__init__(parent)

    # Save the current list of comics. We save into the settings object, which
    # in Windows means, into the Registry under Tassosoft/Cobro (the company
    # and app names set at startup in the app object).
    # In Mac OS, see ~/Library/Preferences/tassos-oak.com/Cobro.plist
    # In Linux see $HOME/.config/Tassosoft/Cobro.conf
    # We use the QSettings convenience function beginWriteArray to write
    # the array of comics as comics/1/name, comics/1/url, etc.
    def save(self, settings) :
        global comics
	settings.beginWriteArray(u'comics')
	for i in range(len(comics)) :
	    settings.setArrayIndex(i)
	    settings.setValue(u'name', QString(comics[i].name))
	    settings.setValue(u'url', QString(comics[i].url))
	    settings.setValue(u'sha1', QString(comics[i].sha1))
	    settings.setValue(u'updays', QString(str(comics[i].updays)))
	    settings.setValue(u'lastread', QVariant(comics[i].lastread))
	settings.endArray()
	settings.sync() # not supposed to be needed but does not harm

    # Load the comics list from the saved settings, see save() below. What we
    # get via QSettings.value is QStrings, which we convert to python while
    # creating the Comic instance.
    
    def load(self, settings) :
        global comics, Comic
	self.beginResetModel()
	count = settings.beginReadArray(u'comics')
	for i in range(count) :
	    settings.setArrayIndex(i)
	    name = settings.value(u'name').toString()
	    url = settings.value(u'url').toString()
	    sha1 = settings.value(u'sha1').toString()
	    updays = settings.value(u'updays').toString()
	    lastread = settings.value(u'lastread').toInt()
	    comic = Comic(n = unicode(name),
	                  s = OLDCOMIC,
	                  u = unicode(url),
	                  h = unicode(sha1),
	                  d = unicode(updays),
	                  l = lastread)
	    comics.append(comic)
	self.endResetModel()

    def flags(self, index) :
        if index.isValid() :
            return ConcreteListModel.itemFlag
        return Qt.NoItemFlags

    def rowCount(self, index):
        global comics
        if not index.isValid() :
            return len(comics)
        return 0

    # This method is called when Qt needs to (re)display the list data.
    # After initialization, that is only when scrolling or if data changes.
    def data(self, index, role) :
        global comics, FontList
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
        return QVariant()

    # setData is a standard list model method that receives a model index,
    # a role, and a QVariant of data for that role. It can be called from the
    # edit delegate, to set the name and/or URL strings. Or it can be called
    # from the statusChanged slot to change the status for the worker thread.
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
	# If the visible list has changed, the list view should update.
	# The signal arguments are the top-left and bottom-right changed
	# items, which is simply the one changed item.
	if doSignal :
	    self.emit(SIGNAL('dataChanged'),index,index)

    # This slot receives the statusChanged(index,stat) signal from the worker
    # thread. It just passes that on to setData() above.
    def statusChangedSlot(self,index,status) :
	self.setData(index, QVariant(status), StatusRole)

    # The inserRow/removeRow methods are essential to internal drag and drop.
    # In order to not have any possibility of drag/drop taking place while
    # an item is being refreshed -- which could invalidate the index that the
    # refresh thread is using -- these functions don't do anything unless the
    # refresh thread is sleeping.
    #
    # n.b. the numbering scheme used in Qt's row insert/removal corresponds
    # perfectly to Python's slice notation.
    
    def insertRow(self, row, parent) :
        global Comic, comics, worker_working
	print('insertRow({0})'.format(row))
	if worker_working :
	    return False
	# The worker thread is asleep and will not wake up until the user
	# requests a refresh which she cannot do while she is dragging an item.
	comic = Comic()
	comics.insert(row,Comic())
	return True

    def removeRow(self, row, parent) :
        global comics, worker_working
	print('removeRow({0})'.format(row))
	if worker_working :
	    return False
	del comic[row]
        return True

    # In the Qt docs, itemData returns a QMap, the Qt equivalent of a dict.
    # In PyQt, it just returns a dict. In this case, a dict that contains
    # all the fields of a given comic, so that setItemData can reproduce that
    # comic in a new row.
    def itemData(self, index) :
        global comics
        comic = comics[index.row()]
	item_dict = {
            'name' : comic.name,
            'status' : comic.status,
            'url'  : comic.url,
            'page' : comic.page,
            'sha1' : comic.sha1,
	    'updays' : str(comic.updays),
	    'lastread' : comic.lastread
            }
	print('itemData row {0}'.format(index.row()))
	return item_dict

    # The Qt docs say that setData() above must emit the dataChanged signal.
    # They do not say so for setItemData(), so I won't. After all, I think
    # this is only called by drag/drop, in which case Qt should darn well 
    # know that data has been changed and needs to be redisplayed.
    def setItemData(self, index, vdict) :
        global comics, UpDays
	print('setItemData row {0}'.format(index.row()))
        comic = comics[index.row()]
        comic.name = unicode(vdict['name'])
        comic.status = vdict['status']
        comic.url = unicode(vdict['url'])
	comic.sha1
        comic.updays = UpDays(vdict['updays'])
        comic.lastread = vdict['lastread']

# So, WTF is a custom delegate? A widget that represents a data item when
# when that item needs to be displayed or edited. We implement the custom
# delegate in stage. First, a class UpDayWidget that encapsulates the Qt
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
	model.setData( index, edit_widget.udWidget.returnUpday(), DaysRole )
            
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Implement the view onto the above list model.

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
        global comics, OLDCOMIC, NEWCOMIC, BADCOMIC
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
	# Load a greeting message
	self.setHtml(QString(u'''<div style='text-align:center;'>
	<h2>Welcome to CoBro!</h2>
	<p>Use File &gt; New Comic to specify a comic by name and URL.</p>
	<p>Single-click a comic to display its page in this browser.</p>
	<p>Double-click a comic to edit	its name, URL, or publication days.</p>
	<p>Change the list order by dragging and dropping.</p>
	<p>To "refresh" a comic means to read its web page and see if it is
	different from the last time.
	While it is being read its name is <i>italic</i>.
	After reading, if it is different, its name turns <b>bold</b>.
	If there is a problem reading it, its name is <strike>lined-out</strike>.</p>
	<p>All comics are refreshed at startup. Or select one or more names
	and hit File &gt; Refresh to read them again.</p>
	<p>Comic definitions are saved in some magic settings place
	(Registry, Library/Preferences, ~/.config)</p>
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
	
    # TBS: capture key events to implement +/- zoom and back/forward

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
	file_delete_action.setToolTip(u"Delete the selected comic")
	self.connect(file_delete_action, SIGNAL(u"triggered()"), self.delete)
	file_menu.addAction(file_delete_action)
	self.setMenuBar(menubar)
	
    # Implement the File > New Comic action:
    def newComic(self) :
	pass
    # Implement the File > Refresh action:
    def refresh(self) :
	global comics, NEWCOMIC, BADCOMIC
	# Get a list of the model indexes of the current selection
	ixlist = self.view.selectedIndexes()
	# Run through the list and for each, do the refresh thing
	for ix in ixlist :
	    comic = comics[ix.row()]
	    new_role = NEWCOMIC
	    if not read_url(comic) : # read failed, set bad
		new_role = BADCOMIC
	    self.model.setData(ix, QVariant(new_role), StatusRole) 

    # Implement the File > Delete action:
    def delete(self) :
	pass
    
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
'''
TO DO

X.  save window geometry during shutdown
X.  restore window geometry on startup
X.  implement model.save
       means figuring out what keys to save
X.  implement model.load
X.  create days-of-week check-box class
X.  add it to item editor and test
X.  add File menu with Refresh command
6.  move refresh out of temp code in item selected
9.  move refresh to a subtask
    implies working out the lock code, prob. means adding mutex to Comic
10. code startup refresh-all
11. refresh-all skips any comic where it is not a scheduled update day
    AND the last refresh was no more than 7 days back (i.e. if it has
    been >7 days since a refresh do it anyway even if it isn't an updayt)
    This implies adding a last-refresh date stamp to comic and saving it.
11. finish File menu
XX. Comics load slow - 
    X. add progress bar
    X. study use of webpage/view: options? reset before sethtml?
13. page-back, zoom in/out -- keys? buttons?
XX. comics.com, gocomics, ucomics (all commercial) error out.
15. ted rall fails unknown reason




'''