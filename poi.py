#!/usr/bin/env python3

import argparse
import configparser
import fnmatch
import glob
import json
import os
import pathlib
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


__VERSION__ = '2.1.0'

## Defaults
###########

LISTING =  os.path.join('.poi', 'listing.json')
LASTNOTE = os.path.join('.poi', 'lastnote')
ENTRYFMT = '{index} {timestamp:%Y-%m-%d %a %H:%M}   {title}'
EDITOR = 'vim'
EXTENSION = '.poi'


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
    if not os.path.exists(LISTING):
        return None
    with open(LISTING, 'r') as f:
        return json.load(f)


def open_editor(path):
    subprocess.call(['/usr/bin/env', EDITOR, path])


def get_path(name):
    """
    YYYYMMDDYYYYMMDDYYYYMMDD.poi -> YYYY/MM/YYYYMMDDYYYYMMDDYYYYMMDD.poi
    """
    year = name[:4]
    month = name[4:6]
    directory = os.path.join(year, month)
    path = os.path.join(directory, name)
    return path


def update_info(note, mode):

    # Update note's fiename
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
    new['path'] = os.path.join(os.path.dirname(old['path']), new['name'])

    shutil.move(old['path'], new['path'])

    # Update lastnote
    with open(LASTNOTE, 'w') as f:
        f.write(new['path'] + '\n')

    # Update information in listing
    listing = load_listing()
    for index, name in listing.items():
        if name == old['path']:
            listing[index] = new['path']
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
        listing = load_listing()
        try:
            name = listing[N]
            note = parse_noteinfo(name)
        except:
            print(
              'poi: note at index {} not available in last listing'.format(N))
            sys.exit(0)
    with open(LASTNOTE, 'w') as f:
        f.write(note['path'] + '\n')
    return note


def parse_noteinfo(path):
    note = {}
    try:
        name = os.path.basename(path)
        note['name'] = name
        note['path'] = path
        note['created'] = name[:14]
        note['edited'] = name[14:28]
        note['viewed'] = name[28:42]
    except:
        print('invalid filename:', name)
    return note


def load_notes():
    notes = []
    filepaths = glob.glob('**/*' + EXTENSION, recursive=True)
    for filepath in filepaths:
        note = parse_noteinfo(filepath)
        notes.append(note)
    return notes


########
# Init #
########

def init(args):
    if os.path.exists('.poi'):
        print('This directory seems to have been initialized already')
    else:
        os.mkdir('.poi')
        config = configparser.ConfigParser()
        config.add_section('core')
        config.set('core', 'editor', EDITOR)
        config.set('core', 'extension', EXTENSION)
        with open(os.path.join('.poi', 'config'), 'w') as f:
            config.write(f)
        print('Poi initialized!')


#######
# Add #
#######

def create_file():
    delta = dt.timedelta(seconds=1)
    now = dt.datetime.now()
    while True:
        ts = now.strftime('%Y%m%d%H%M%S')
        filename = ts + ts + ts + EXTENSION
        year = ts[:4]
        month = ts[4:6]
        directory = pathlib.Path(year, month)
        directory.mkdir(exist_ok=True, parents=True)
        path = directory.joinpath(filename)
        if not path.exists():
            path.write_text('')
            break
        else:
            now += delta
    return path


def add_note(args):
    path = create_file()
    open_editor(path)

##########
# Delete #
##########


def delete_note(args):
    note = fetch_note(args)
    with open(note['path']) as f:
        text = f.read()
    print('---')
    print(text.strip())
    print('---')
    ans = input('poi: delete (y/n)? ')
    if ans != 'y':
        print('--->  cancelled')
        sys.exit(0)
    else:
        os.remove(note['path'])
        print('---> deleted')

    # Remove note from last listing
    listing = load_listing()
    if listing is not None:
        for index, name in list(listing.items()):
            if name == note['name']:
                del listing[index]
        with open(LISTING, 'w') as f:
            json.dump(listing, f)

    # Remove last note if this was it
    lastnote = load_lastnote()
    if lastnote is not None:
        if note['name'] == lastnote['name']:
            os.remove(LASTNOTE)


########
# Edit #
########


def edit_note(args):
    note = fetch_note(args)
    note = update_info(note, mode='edited')
    open_editor(note['path'])


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

    if args.days_ago is not None:
        delta = dt.timedelta(days=1)
        now = dt.datetime.now()
        then = now - args.days_ago * delta
        since = then.strftime('%Y%m%d')
        before = (then + delta).strftime('%Y%m%d')
        notes = [note for note in notes if since <= note['created'] < before]

    if args.since:
        since = args.since.replace('-', '')
        notes = [note for note in notes if since <= note['created']]

    if args.before:
        before = args.before.replace('-', '')
        notes = [note for note in notes if before >= note['created']]

    path_name_title_and_timestamp = []

    for note in notes:
        with open(note['path']) as f:
            text = f.read().strip()
        title = text.strip().split('\n')[0].strip()

        if not args.case_sensitive:
            text = text.lower()

        for term in args.terms:
            if term not in text:
                break
        else:
            path_name_title_and_timestamp.append([note['path'], note['name'], title, note[mode]])

    N = len(path_name_title_and_timestamp)

    # if there are no notes, do not show anything
    if N == 0:
        return None

    index_width = int(floor(log10(N)) + 1)
    listing = {}

    if not args.filepath:
        print()

    for i, (path, name, title, timestamp) in enumerate(path_name_title_and_timestamp):
        try:
            timestamp = dt.datetime.strptime(timestamp[:14], '%Y%m%d%H%M%S')
        except:
            print('invalid filename:', name)
            continue
        if args.filepath:
            print(path)
        else:
            print(
                ENTRYFMT.format(index=str(N - 1 - i).ljust(index_width),
                                timestamp=timestamp, title=title))
        sys.stdout.flush()
        listing[N - 1 - i] = path

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
    operating_system = os.uname()[0]
    # Escape '\' so as to not disturb echo
    text = re.sub('"', r'\"', text)
    if operating_system == 'Darwin':
        subprocess.call(['echo "' + text + '" | pbcopy'], shell=True)
        return None
    elif operating_system == 'Linux':
        if shutil.which('xsel') is not None:
            subprocess.call(['echo "' + text + '" | xsel --clipboard --input'], shell=True)
            return None
        else:
            print('poi: copying to clipboard requires xsel to be installed.')
    else:
        print("poi: copying to clipboard is not implemented for your setup")


def view_note(args):
    note = fetch_note(args)
    note = update_info(note, mode='viewed')

    if args.info:
        print('\t' + 'filepath'.rjust(10) + ':', note['path'])
        for mode in ['created', 'edited', 'viewed']:
            timestamp = dt.datetime.strptime(note[mode][:16], '%Y%m%d%H%M%S')
            print('\t' + mode.rjust(10) + ':',
                  timestamp.strftime('%Y-%m-%d %a %H:%M'))
    else:
        if args.filepath:
            print(note['path'])
        else:

            with open(note['path']) as f:
                text = f.read().strip()

            if args.line_numbers:
                text = '\n'.join(str(i) + '\t' + line for i, line
                                 in enumerate(text.split('\n'), start=1))

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


## Sweep
########


def sweep(args):
    for note in load_notes():
        name = note['name']
        year = name[:4]
        month = name[4:6]
        newdir = pathlib.Path(year, month).mkdir(exist_ok=True, parents=True)
        newpath = os.path.join(year, month, name)
        if note['path'] != newpath:
            shutil.move(note['path'], newpath)
            print(note['path'], '--->', newpath)


########
# Main #
########


def parse_arguments():

    parser = argparse.ArgumentParser(description='poi: Points of Interest')
    parser.add_argument("-v", "--version", action='version',
                        version=__VERSION__)
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

    # poi initialize
    init_parser = subparsers.add_parser('init', help='initialize poi directory')
    init_parser.set_defaults(func=init)

    # poi list
    list_parser = subparsers.add_parser('list', help='list notes')
    list_parser.add_argument('terms',
                             help='list notes that include each of TERMS',
                             nargs='*')
    list_parser.add_argument('-c', '--case-sensitive',
                             help="don't ignore case", default=False,
                             action='store_true')
    list_parser.add_argument('-f', '--filepath',
                             help='only list filepaths', default=False,
                             action='store_true')
    list_parser.add_argument('-e', '--edited',
                             help='sort by day edited', default=False,
                             action='store_true')
    list_parser.add_argument('-v', '--viewed',
                             help='sort by day viewed', default=False,
                             action='store_true')
    list_parser.add_argument('-s', '--since',
                             help='only list notes created since (inclusive)')
    list_parser.add_argument('-b', '--before',
                             help='only list notes created before (exclusive)')
    list_parser.add_argument('-y', '--days-ago', type=int,
                             help='only list notes created number of days ago')
    list_parser.set_defaults(func=list_notes)

    # poi random
    random_parser = subparsers.add_parser('random', help='show a random note')
    random_parser.set_defaults(func=random_note)

    # poi sweep
    sweep_parser = subparsers.add_parser('sweep', help='organize files')
    sweep_parser.set_defaults(func=sweep)

    # poi view
    view_parser = subparsers.add_parser('view', help='view note')
    view_parser.add_argument('index', help='view entry at INDEX')
    view_parser.add_argument('-p', '--print',
                             help='print note on the screen', default=False,
                             action='store_true')
    view_parser.add_argument('-f', '--filepath',
                             help='only show filepath', default=False,
                             action='store_true')
    view_parser.add_argument('-i', '--info',
                             help='show information about this note',
                             default=False, action='store_true')
    view_parser.add_argument('-l', '--include-lines',
                             help='only include given lines')
    view_parser.add_argument('-n', '--line-numbers',
                             help='show line numbers', default=False,
                             action='store_true')
    view_parser.add_argument('-c', '--clipboard',
                             help='copy to clipboard', default=False,
                             action='store_true')
    view_parser.set_defaults(func=view_note)

    args = parser.parse_args()
    return args, parser


def main():

    args, parser = parse_arguments()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(0)

    if args.func.__name__ == 'init':
        args.func(args)
        sys.exit(0)

    # Check environment
    if not os.path.exists('.poi'):
        print('Not a poi directory. Initialize with "poi init"')
        sys.exit(0)
    global EDITOR
    global EXTENSION
    config = configparser.ConfigParser()
    config.read('.poi/config')

    try:
        EDITOR = config['core']['editor']
    except:
        pass

    try:
        EXTENSION = config['core']['extension']
    except:
        pass

    args.func(args)


if __name__ == '__main__':
    main()
