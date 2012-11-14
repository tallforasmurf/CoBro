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

    You can find a copy of the GNU General Public License in the file
    COPYING.TXT included in the distribution of this program, or see:
    <http://www.gnu.org/licenses/>.
'''

'''
CoBro (Comic Browser) is a minimal web browser designed for
convenient reading of Web Comics. The main window has a list
of comic names on the left and a web page display on the right.
Associated with each comic in the list are:
  * the user-selected name
  * the URL of the comic
  * the text of the contents most recently read from that URL
  * an SHA-1 hash of the contents text
  * a status: has/hasn't been viewed
When the user clicks on a comic in the list, that comic's contents text
is loaded into the web page display with QWebView::setHTML() and
rendered. The rendered page can be used as it would be in a common
browser, e.g. the user can click on buttons and follow links in the page.

There is a single menu, the File menu, with these commands:
  * New Comic
        opens a dialog to collect the name and URL of a new comic,
        which is added to the list at the bottom.
  * Refresh All
  * Refresh Selected
        The refresh operation is described below
  * Quit

The list supports the following operations:
  * single-click an item to display that comic in the web display
  * shift-click or control-/command-click to select multiple names
        for Refresh Selected
  * drag and drop items to reorder the list
  * double-click an item to open an Edit Comic dialog which permits
        editing the name or URL, and offers a Delete Comic button.

The list is implemented using Qt's model/view classes. The list data
is held in a Python lists of named-tuple items. This is presented to
Qt through a custom subclass of QAbstractListModel. The model is handed
to a QListView for display. When the list view decides edting is needed
it creates a custom item delegate that implements the edit/delete dialog.

When the app loads, or when File>Refresh All is chosen, or when 
File>Refresh Selected is chosen, the app proceeds to go through all/selected
comics and for each:
  * set a status message saying "reading <abbreviated url>"
  * set the comic name to italic font
  * set the comic status to has been read
  * attempt to read the http page at the given URL
  * if this fails for any reason, sets the comic name to strikethrough
    font and put a message in the status field
  * compute the SHA-1 hash of the received contents text 
  * if this is the same as the previous hash, the comic has been read before,
    set the comic name to normal font
  * the text is different, set the comic status to hasn't been seen,
    set the name to bold and save the hash and contents text

In this way, shortly after launching, the user has a list of comics ready
to be read with the unseen ones in bold. 
'''

'''
Acknowledgements and Credits

First to Steve Shulz (Thundergnat) who created and maintained Guiguts,
the program from which we have taken inspiration and lots of methods.

Second to Mark Summerfield for the book "Rapid GUI Development with PyQt"
without which we couldn't have done this.
'''
