#!/usr/bin/env python3

import argparse
import configparser
import fnmatch
import json
import os
import pydoc
import shutil
import subprocess
import sys
import uuid

import datetime as dt
from math import floor, log10
from random import choice


__VERSION__ = '1.0.0'
EDITOR = 'vim'
HOME = os.getcwd()
EXTENSION = '.poi'
HISTORY = 'history.json'
LISTING = 'listing.json'
ENTRYFMT = '{index} {timestamp:%Y-%m-%d %a %H:%M}   {title}'

NOTEID = 0
TIMESTAMP = 1

#########
# Utils #
#########

def load(path):
    with open(path, 'r') as f:
        return json.load(f)

def dump(path, js):
    with open(path, 'w') as f:
        json.dump(js, f, sort_keys=True, indent=4)

def notepath(noteid):
    """
    Return the full filepath corresponding to noteid.
    """
    prefix = noteid[:2]
    suffix = noteid[2:]
    dirname = os.path.join(HOME, prefix)
    return os.path.join(dirname, suffix + EXTENSION)

def open_editor(noteid):
    fpath = notepath(noteid)
    subprocess.call(['/usr/bin/env', EDITOR, fpath])

def update_history(noteid, mode=None, delete=False):
    """
    Update history by changing a viewing or editing date, inserting a new
    records for a created note, or by deleting a record of a note.
    """
    history = load(HISTORY)

    if mode is not None:
        now = dt.datetime.now().isoformat()
        if mode == 'viewed':
            history[noteid]['viewed'] = now
        elif mode == 'edited':
            history[noteid]['edited'] = now
            history[noteid]['viewed'] = now
        elif mode == 'created':
            history[noteid] = {}
            history[noteid]['created'] = now 
            history[noteid]['edited'] = now 
            history[noteid]['viewed'] = now 

    if delete:
        del history[noteid]

    dump(HISTORY, history)

def fetch_noteid(args):
    # Type of N is str
    N = args.index 
    if N == '_':
        history = load(HISTORY)
        # Find the note with the most recent timestamp on some activity.
        note = max(history.items(),
                key=lambda x: max(x[TIMESTAMP]['created'], x[TIMESTAMP]['viewed'], x[TIMESTAMP]['viewed']))
        noteid = note[NOTEID]
        return noteid
    else: 
        listing = load(LISTING)
        if N in listing:
            noteid = listing[str(N)]
            return noteid
        else:
            print('poi: index {} not available in last listing'.format(N))
            sys.exit(0)

#######
# Add #
#######

def touch_file(fpath, content=''):
    if not os.path.exists(fpath):
        with open(fpath, 'w') as f:
            f.write(content)

def create_noteid():
    """
    Create a noteid that corresponds to a unique filepath in the file system.
    Create auxiliary subdirectory if necessary.
    """
    while True:
        # http://stackoverflow.com/a/20060712
        noteid = uuid.uuid4().hex
        fpath = notepath(noteid)
        dirname = os.path.dirname(fpath)

        if not os.path.exists(dirname):
            os.mkdir(dirname)
            break
        if not os.path.exists(fpath):
            break

    touch_file(fpath, content='')
    return noteid

def add_note(args):
    """
    Add note. Poi creates a fileid automatically.

    Note: the arguments args is not used, but required by argparse syntax.
    """
    noteid = create_noteid()
    viewupdate_history(noteid, mode='created')
    open_editor(noteid)


##########
# Delete #
#########E

def delete_file(noteid):
    """
    Delete a note file and its parent directory if it is empty.
    """
    fpath = notepath(noteid)
    os.remove(fpath)
    dirname = os.path.dirname(fpath)
    # Remove dir if it is empty, otherwise ignore.
    # http://stackoverflow.com/a/6215451
    try:
        os.rmdir(dirname)
    except OSError:
        pass

def delete_note(args):
    noteid = fetch_noteid(args)
    with open(notepath(noteid)) as f:
        text = f.read()
    print('---')
    print(text.strip())
    print('---')
    ans = input('poi: delete (y/n)? ')
    if ans != 'y':
        print('     cancelled')
        sys.exit(0)
    else:
        delete_file(noteid)
        print('     deleted')

    # Remove note from last listing
    listing = load(LISTING)
    for index, noteid_ in list(listing.items()):
        if noteid_ == noteid:
            del listing[index]
    dump(LISTING, listing)

    # Remove note from history
    update_history(noteid, delete=True)


########
# Edit #
########


def edit_note(args):
    noteid = fetch_noteid(args)
    update_history(noteid, mode='edited')
    open_editor(noteid)


##########
# Search #
##########

def search_notes(args):

    if args.edited:
        mode = 'edited'
    elif args.viewed:
        mode = 'viewed'
    else:  # default 
        mode = 'created'
    
    history = load(HISTORY)
    # Sort notes by type of date given by mode:
    notes = sorted(history.items(), key=lambda x: x[TIMESTAMP][mode])

    noteid_title_and_timestamp = []
    
    for noteid, timestamp in notes:
        with open(notepath(noteid)) as f:
            text = f.read().strip()
        title = text.strip().split('\n')[0].strip()

        if not args.case_sensitive:
            text = text.lower()

        for term in args.terms:
            if term not in text:
                break
        else:
            noteid_title_and_timestamp.append([noteid, title, timestamp[mode]])

    N = len(noteid_title_and_timestamp)

    # if there are no notes, do not show anything
    if N == 0:
        return None
    else:
        print()

    index_width = int(floor(log10(N)) + 1)
    listing = {}

    for i, (noteid, title, timestamp) in enumerate(noteid_title_and_timestamp):
        timestamp = dt.datetime.strptime(timestamp[:16], '%Y-%m-%dT%H:%M')
        if args.filepath:
            print(notepath(noteid))
        else:
            print(ENTRYFMT.format(index=str(N - 1 - i).ljust(index_width), timestamp=timestamp, title=title))
        sys.stdout.flush()
        listing[N - 1 - i] = noteid

    dump(LISTING, listing)
    infobar = '\ntotal: {}'.format(N)
    if not args.filepath:
        print(infobar)
    print()


########
# View #
########

def show_in_pager(noteid):
    with open(notepath(noteid)) as f:
        pydoc.pager(f.read().strip())

def print_note(noteid):
    with open(notepath(noteid)) as f:
        print(f.read().strip())

def view_note(args):
    noteid = fetch_noteid(args)
    update_history(noteid, mode='viewed')
    if args.print:
        print_note(noteid)
    else:
        show_in_pager(noteid)









########
# Main #
########

def main():
    # parse_arguments()
    parser = argparse.ArgumentParser(description='Points of Interest')
    parser.add_argument("-v", "--version", action='version', version=__VERSION__)
    subparsers = parser.add_subparsers()

    # poi add
    add_parser = subparsers.add_parser('add', help='add note')
    add_parser.set_defaults(func=add_note)

    # poi delete
    delete_parser = subparsers.add_parser('delete', help='delete note')
    delete_parser.add_argument('index', help='delete entry at INDEX')
    delete_parser.set_defaults(func=delete_note)

    # poi edit
    edit_parser = subparsers.add_parser('edit', help='edit note')
    edit_parser.add_argument('index', help='edit entry at INDEX')
    edit_parser.set_defaults(func=edit_note)


    # poi search 
    search_parser = subparsers.add_parser('search', help='search notes')
    search_parser.add_argument('terms', help='search notes withs TERMS', nargs='*')
    search_parser.add_argument('-c', '--case-sensitive',
            help='case-sensitive search', default=False, action='store_true')
    search_parser.add_argument('-f', '--filepath',
            help='only list filepaths', default=False, action='store_true')
    search_parser.add_argument('-e', '--edited',
            help='sort by day edited', default=False, action='store_true')
    search_parser.add_argument('-v', '--viewed',
            help='sort by day viewed', default=False, action='store_true')
    search_parser.set_defaults(func=search_notes)
    
    # poi view
    view_parser = subparsers.add_parser('view', help='view note')
    view_parser.add_argument('index', help='view entry at INDEX')
    view_parser.add_argument('-p', '--print',
            help='print note on the screen', default=False, action='store_true')
    view_parser.set_defaults(func=view_note)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
