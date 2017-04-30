#!/usr/bin/env python3

import argparse
import configparser
import fnmatch
import glob
import json
import os
import pydoc
import random
import re
import shutil
import subprocess
import sys
import uuid

import datetime as dt
from math import floor, log10
from random import choice


__VERSION__ = '2.0.0'
EDITOR = 'vim'
HOME = os.getcwd()
EXTENSION = '.poi'
LISTING = 'listing.json'
LASTNOTE = 'lastnote'
ENTRYFMT = '{index} {timestamp:%Y-%m-%d %a %H:%M}   {title}'

NOTEID = 0
TIMESTAMP = 1

#########
# Utils #
#########

def load_lastnote():
    if not os.path.exists(LASTNOTE):
        return None
    else:
        with open(LASTNOTE, 'r') as f:
            name = f.read().strip()
        return parse_noteinfo(name)


def load_listing():
    with open(LISTING, 'r') as f:
        return json.load(f)


def open_editor(path):
    subprocess.call(['/usr/bin/env', EDITOR, path])


def update_info(note, mode):
    old = note
    new = old.copy()
    now = dt.datetime.now().strftime('%Y%m%d%H%M%S')
    if mode == 'viewed':
        new['viewed'] = now
    elif mode == 'edited':
        new['edited'] = now
        new['viewed'] = now
    else:
        pass
    new['name'] = new['created'] + new['edited'] + new['viewed'] + EXTENSION

    shutil.move(old['name'], new['name']) 

    # Update lastnote
    with open(LASTNOTE, 'w') as f:
        f.write(new['name'] + '\n')

    # Update information in listing
    listing = load_listing()
    for index, name in listing.items():
        if name == old['name']:
            listing[index] = new['name']
    with open(LISTING, 'w') as f:
        json.dump(listing, f)

    return new


def fetch_note(args):
    # Type of N is str
    N = args.index 
    if N == '_':
        note = load_lastnote()
        if note is None:
            print('poi: last note is not available')
            sys.exit(0)
        else:
            return note
    else: 
        listing = load_listing()
        try:
            name = listing[N]
            note = parse_noteinfo(name)
        except:
            print('poi: index {} not available in last listing'.format(N))
            sys.exit(0)
        else:
            return note 


def parse_noteinfo(name):
    note = {}
    note['name'] = name
    note['created'] = name[:14]
    note['edited'] = name[14:28]
    note['viewed'] = name[28:42]
    return note


def load_notes():
    notes = []
    filenames = glob.glob('*' + EXTENSION)
    for filename in filenames:
        note = parse_noteinfo(filename) 
        notes.append(note)
    return notes


#######
# Add #
#######

def touch_file(path, content=''):
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(content)


def create_file():
    """
    Create a filepath that corresponds to a unique filepath in the file system.
    Create auxiliary subdirectory if necessary.
    """
    delta = dt.timedelta(seconds=1)
    now = dt.datetime.now()
    while True:
        ts = now.strftime('%Y%m%d%H%M%S')
        filename = ts + ts + ts + EXTENSION 
        if not os.path.exists(filename):
            break
        else:
            now += delta
    touch_file(filename, content='')
    return filename


def add_note(args):
    """
    Add note. Poi creates a fileid automatically.

    Note: the arguments args is not used, but required by argparse syntax.
    """
    path = create_file()
    open_editor(path)


##########
# Delete #
#########E

def delete_file(filepath):
    """
    Delete a note file and its parent directory if it is empty.
    """
    os.remove(filepath)
    # remove child directory of 2017/04 if its empty, but keep 2017/
    dirname = os.path.dirname(filepath)
    # Remove dir if it is empty, otherwise ignore.
    # http://stackoverflow.com/a/6215451
    try:
        os.rmdir(dirname)
    except OSError:
        pass

def delete_note(args):
    note = fetch_note(args)
    with open(note['name']) as f:
        text = f.read()
    print('---')
    print(text.strip())
    print('---')
    ans = input('poi: delete (y/n)? ')
    if ans != 'y':
        print('     cancelled')
        sys.exit(0)
    else:
        delete_file(note['name'])
        print('     deleted')

    # Remove note from last listing
    listing = load_listing()
    for index, name in list(listing.items()):
        if name == note['name']:
            del listing[index]
    with open(LISTING, 'w') as f:
        json.dump(listing, f)


########
# Edit #
########


def edit_note(args):
    note = fetch_note(args)
    note = update_info(note, mode='edited')
    open_editor(note['name'])


##########
# list #
##########

def list_notes(args):

    if args.edited:
        mode = 'edited'
    elif args.viewed:
        mode = 'viewed'
    else:  # default 
        mode = 'created'

    # Sort notes by type of date given by mode:
    notes = load_notes() 
    notes = sorted(notes, key=lambda x: x[mode])

    if args.since:
        notes = [note for note in notes if args.since <= note['created']]

    if args.before:
        notes = [note for note in notes if args.before >= note['created']]

    name_title_and_timestamp = []
    
    for note in notes:
        with open(note['name']) as f:
            text = f.read().strip()
        title = text.strip().split('\n')[0].strip()

        if not args.case_sensitive:
            text = text.lower()

        for term in args.terms:
            if term not in text:
                break
        else:
            name_title_and_timestamp.append([note['name'], title, note[mode]])

    N = len(name_title_and_timestamp)

    # if there are no notes, do not show anything
    if N == 0:
        return None


    index_width = int(floor(log10(N)) + 1)
    listing = {}


    if not args.filepath:
        print()

    for i, (name, title, timestamp) in enumerate(name_title_and_timestamp):
        timestamp = dt.datetime.strptime(timestamp[:14], '%Y%m%d%H%M%S')
        if args.filepath:
            print(path)
        else:
            print(ENTRYFMT.format(index=str(N - 1 - i).ljust(index_width), timestamp=timestamp, title=title))
        sys.stdout.flush()
        listing[N - 1 - i] = name 

    with open(LISTING, 'w') as f:
        json.dump(listing, f)

    infobar = '\ntotal: {}'.format(N)
    if not args.filepath:
        print(infobar)
        print()


##########
# Random #
##########


def random_note(args):
    notes = load_notes()
    N = len(notes)
    i = random.randint(0, N - 1)
    note = notes[i]
    note = update_info(note, mode='viewed')
    with open(note['name']) as f:
        text = f.read()
    pydoc.pager(text)

########
# View #
########

def copy_to_clipboard(text):
    if os.uname()[0] == 'Darwin':
        # Escape '\' so as to not distrurb echo
        text = re.sub('"', r'\"', text)
        subprocess.call(['echo "' + text + '" | pbcopy'], shell=True)
    else:
        print("poi: currently clipboard only implemented for Mac")


def view_note(args):
    note = fetch_note(args)
    note = update_info(note, mode='viewed')

    if args.info:
        print('\t' + 'filepath'.rjust(10) + ':', note['name'])
        for mode in ['created', 'edited', 'viewed']:
            timestamp = dt.datetime.strptime(note[mode][:16], '%Y%m%d%H%M%S')
            print('\t' + mode.rjust(10) + ':', timestamp.strftime('%Y-%m-%d %a %H:%M'))
    else:
        if args.filepath:
            print(note['name'])
        else:

            with open(note['name']) as f:
                text = f.read().strip()

            if args.line_numbers:
                text = '\n'.join(str(i) + '\t' + line for i, line in enumerate(text.split('\n'), start=1))

            if args.include_lines:
                numbers = args.include_lines.split(',')
                lines = text.splitlines()
                newtext = ''
                for i in numbers:
                    try:
                        if i.isdigit():
                            newtext += lines[int(i) - 1] + '\n'
                        else:
                            s, e = i.split('-')
                            if e == '':
                                newtext += '\n'.join(lines[int(s) - 1:]) 
                            else:
                                newtext += '\n'.join(lines[int(s) - 1:int(e)]) 
                    except:
                        print("poi: invalid range specification")
                        sys.exit(0)
                text = newtext
            if args.clipboard:
                copy_to_clipboard(text)
            elif args.print:
                print(text)
            else:
                pydoc.pager(text)

########
# Main #
########

def main():

    # parse_arguments()
    parser = argparse.ArgumentParser(description='poi: Points of Interest')
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

    # poi list 
    list_parser = subparsers.add_parser('list', help='list notes')
    list_parser.add_argument('terms', help='list notes that include each of TERMS', nargs='*')
    list_parser.add_argument('-c', '--case-sensitive',
            help="don't ignore case", default=False, action='store_true')
    list_parser.add_argument('-f', '--filepath',
            help='only list filepaths', default=False, action='store_true')
    list_parser.add_argument('-e', '--edited',
            help='sort by day edited', default=False, action='store_true')
    list_parser.add_argument('-v', '--viewed',
            help='sort by day viewed', default=False, action='store_true')
    list_parser.add_argument('-s', '--since',
            help='only list notes created since (inclusive)')
    list_parser.add_argument('-b', '--before',
            help='only list notes created before (exclusive)')
    list_parser.set_defaults(func=list_notes)


    # poi random 
    random_parser = subparsers.add_parser('random', help='show a random note')
    random_parser.set_defaults(func=random_note)

    
    # poi view
    view_parser = subparsers.add_parser('view', help='view note')
    view_parser.add_argument('index', help='view entry at INDEX')
    view_parser.add_argument('-p', '--print',
            help='print note on the screen', default=False, action='store_true')
    view_parser.add_argument('-f', '--filepath',
            help='only show filepath', default=False, action='store_true')
    view_parser.add_argument('-i', '--info',
            help='show information about this note', default=False, action='store_true')
    view_parser.add_argument('-l', '--include-lines',
            help='only include given lines')
    view_parser.add_argument('-n', '--line-numbers',
            help='show line numbers', default=False, action='store_true')
    view_parser.add_argument('-c', '--clipboard',
            help='copy to clipboard', default=False, action='store_true')
    view_parser.set_defaults(func=view_note)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
