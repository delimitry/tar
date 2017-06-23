#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import ctypes
import datetime
import getpass
import locale
import math
import os
import stat
import sys
from io import BytesIO

locale.setlocale(locale.LC_ALL, '')
SYSTEM_ENCODING = locale.getlocale()[1]

PY3 = sys.version_info[0] == 3

TAR_TYPE_REGULAR_FILE = '0'  # Normal file
TAR_TYPE_REGULAR_FILE_ALIAS = '\x00'  # Normal file (alias)
TAR_TYPE_HARDLINK = '1'  # Hard link
TAR_TYPE_SYMLINK = '2'  # Symbolic link
TAR_TYPE_CHAR = '3'  # Character special
TAR_TYPE_BLOCK = '4'  # Block special
TAR_TYPE_DIR = '5'  # Directory
TAR_TYPE_FIFO = '6'  # FIFO
TAR_TYPE_CONTIGUOUS = '7'  # Contiguous file

TYPE_FLAGS = {
    TAR_TYPE_REGULAR_FILE: '-',
    TAR_TYPE_REGULAR_FILE_ALIAS: '-',
    TAR_TYPE_HARDLINK: 'h',
    TAR_TYPE_SYMLINK: 'l',
    TAR_TYPE_CHAR: 'c',
    TAR_TYPE_BLOCK: 'b',
    TAR_TYPE_DIR: 'd',
    TAR_TYPE_FIFO: 'p',
}


class TarHeader(ctypes.Structure):
    """
    Tar Header
    POSIX 1003.1-1988 (ustar) format
    """
    _pack_ = 1
    _fields_ = [
        ('name', ctypes.c_char * 100),  # name of file
        ('mode', ctypes.c_char * 8),  # file mode
        ('uid', ctypes.c_char * 8),  # owner user ID
        ('gid', ctypes.c_char * 8),  # owner group ID
        ('size', ctypes.c_char * 12),  # length of file in bytes
        ('mtime', ctypes.c_char * 12),  # modify time of file
        ('chksum', ctypes.c_char * 8),  # checksum for header
        ('typeflag', ctypes.c_char),  # type of file
        ('linkname', ctypes.c_char * 100),  # name of linked file
        ('magic', ctypes.c_char * 6),  # magic
        ('version', ctypes.c_char * 2),  # version
        ('uname', ctypes.c_char * 32),  # owner user name
        ('gname', ctypes.c_char * 32),  # owner group name
        ('devmajor', ctypes.c_char * 8),  # device major number
        ('devminor', ctypes.c_char * 8),  # device minor number
        ('prefix', ctypes.c_char * 155),  # prefix for file name
        ('pad', ctypes.c_char * 12),
    ]


def permission_bits(str_value, typeflag):
    """Format type flag and permission bits"""
    value = int(str_value, 8)
    res = TYPE_FLAGS.get(chr(ord(typeflag)), '?')
    # user
    res += 'r' if (value >> 6) & 0b100 else '-'
    res += 'w' if (value >> 6) & 0b010 else '-'
    res += 'x' if (value >> 6) & 0b001 else '-'
    # group
    res += 'r' if (value >> 3) & 0b100 else '-'
    res += 'w' if (value >> 3) & 0b010 else '-'
    res += 'x' if (value >> 3) & 0b001 else '-'
    # other
    res += 'r' if value & 0b100 else '-'
    res += 'w' if value & 0b010 else '-'
    res += 'x' if value & 0b001 else '-'
    return res


def get_group_name(username):
    """Get group name for user"""
    try:
        import grp
        import pwd
    except ImportError:
        # return empty group name
        return ''
    gid = pwd.getpwnam(username).pw_gid
    return grp.getgrgid(gid).gr_name


def get_uid_and_gid(username):
    """Get uid and gid tuple"""
    try:
        import pwd
    except ImportError:
        # return empty uid, gid
        return '', ''
    return pwd.getpwnam(username).pw_uid, pwd.getpwnam(username).pw_gid


def is_hard_link(filename):
    """Check if hardlink"""
    file_stat = os.stat(filename)
    if not stat.S_ISLNK(file_stat.st_mode):
        return False
    linkname = os.path.realpath(filename)
    link_file_stat = os.stat(linkname)
    return file_stat[stat.ST_DEV] == link_file_stat[stat.ST_DEV] and \
        file_stat[stat.ST_INO] == link_file_stat[stat.ST_INO]


def get_header_checksum(header):
    """Get checksum"""
    stream = BytesIO()
    stream.write(header)
    stream.seek(0)
    data = stream.read()
    return sum(map(lambda x: x if PY3 else ord(x), data))


def read_file_in_chunks(in_file, file_size, chunk_size=8 * 1024):
    """Read file in chunks"""
    read_bytes = 0
    while True:
        if read_bytes > file_size - chunk_size:
            # read last chunk
            chunk = in_file.read(file_size - read_bytes)
        else:
            # read chunk
            chunk = in_file.read(chunk_size)
        read_bytes += len(chunk)
        if chunk:
            yield chunk
        else:
            return


def create(archive, file_or_dir, verbose=False):
    """Create archive"""
    if verbose:
        print('Creating archive "{}"'.format(archive))
    if not os.path.exists(file_or_dir):
        print('No such file or directory: "{}"'.format(file_or_dir))
        return False

    # overwrite file on archive creation
    open(archive, 'wb').close()

    result = True
    if os.path.isfile(file_or_dir):
        # add file
        result |= add(archive, file_or_dir, verbose=verbose)
    else:
        for dirname, dirs, files in os.walk(file_or_dir):
            # add directory
            result |= add(archive, dirname, verbose=verbose)
            for filename in files:
                # add file
                result |= add(archive, os.path.join(dirname, filename), verbose)
    return result


def extract(archive, dest_path='./out', verbose=False):
    """Extract files from archive"""
    if verbose:
        print('Extracting files from archive "{}"'.format(archive))
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    # TODO: update extract
    with open(archive, 'rb') as in_file:
        while True:
            tar_header = TarHeader()
            in_file.readinto(tar_header)
            name = tar_header.name
            if not name:
                break
            file_size = int(tar_header.size, 8)
            out_path = os.path.join(dest_path, name.decode(SYSTEM_ENCODING) if PY3 else name)
            if verbose:
                print('Extracting file "{}"'.format(out_path))
            if tar_header.typeflag.decode('latin') in (TAR_TYPE_REGULAR_FILE, TAR_TYPE_REGULAR_FILE_ALIAS):
                with open(out_path, 'wb') as f:
                    # write a file in chunks
                    for chunk in read_file_in_chunks(in_file, file_size):
                        f.write(chunk)
            elif tar_header.typeflag.decode('latin') == TAR_TYPE_DIR:
                try:
                    os.makedirs(out_path)
                except OSError:
                    pass
            padding_size = int(math.ceil(file_size / 512.0) * 512) - file_size
            in_file.read(padding_size)
    return True


def add(archive, filename, verbose=False):
    """Add file to archive"""
    if verbose:
        print('Adding file "{}"'.format(filename, archive))
    if not os.path.exists(filename):
        print('No such file: "{}"'.format(filename))
        return False

    # get current user, group and IDs
    username = getpass.getuser()
    group = get_group_name(username)
    uid, gid = get_uid_and_gid(username)

    # set file type
    linkname = ''
    typeflag = ''
    file_stat = os.stat(filename)
    file_mode = file_stat.st_mode
    if stat.S_ISREG(file_mode):
        typeflag = TAR_TYPE_REGULAR_FILE
    elif stat.S_ISLNK(file_mode):
        linkname = os.path.realpath(filename)
        # TODO: check hard link
        typeflag = TAR_TYPE_HARDLINK if is_hard_link(filename) else TAR_TYPE_SYMLINK
    elif stat.S_ISCHR(file_mode):
        typeflag = TAR_TYPE_CHAR
    elif stat.S_ISBLK(file_mode):
        typeflag = TAR_TYPE_BLOCK
    elif stat.S_ISDIR(file_mode):
        typeflag = TAR_TYPE_DIR
    elif stat.S_ISFIFO(file_mode):
        typeflag = TAR_TYPE_FIFO

    mode = 'ab' if os.path.exists(archive) else 'wb'
    with open(archive, mode) as out:
        tar_header = TarHeader()
        tar_header.name = filename[:99].encode(SYSTEM_ENCODING) if PY3 else filename[:99]
        tar_header.mode = '{:07o}'.format(file_stat.st_mode & 0o777).encode('latin')
        tar_header.uid = '{:07o}'.format(file_stat.st_uid).encode('latin')
        tar_header.gid = '{:07o}'.format(file_stat.st_gid).encode('latin')
        tar_header.size = '{:011o}'.format(file_stat.st_size if typeflag != TAR_TYPE_DIR else 0).encode('latin')
        tar_header.mtime = '{:o}'.format(int(file_stat.st_mtime)).encode('latin')
        tar_header.chksum = (' ' * 8).encode('latin')  # 8 spaces before real checksum calculation
        tar_header.typeflag = typeflag.encode('latin') if PY3 else typeflag
        tar_header.linkname = linkname[:99].encode(SYSTEM_ENCODING) if PY3 else linkname[:99]
        tar_header.magic = 'ustar\x00'.encode('latin')
        tar_header.version = '00'.encode('latin')
        tar_header.uname = username[:32].encode(SYSTEM_ENCODING) if PY3 else username[:32]
        tar_header.gname = group.encode('latin')
        tar_header.devmajor = '0000000\x00'.encode('latin')
        tar_header.devminor = '0000000\x00'.encode('latin')
        tar_header.prefix = ''.encode('latin')
        tar_header.pad = ''.encode('latin')
        # update checksum
        tar_header.chksum = '{:06o}'.format(get_header_checksum(tar_header)).encode('latin')
        # write header
        out.write(tar_header)
        # write data if any
        file_size = os.path.getsize(filename)
        # TODO: other modes
        if typeflag in (TAR_TYPE_REGULAR_FILE, TAR_TYPE_HARDLINK, TAR_TYPE_SYMLINK) and file_size:
            with open(filename, 'rb') as in_file:
                # write a file in chunks
                for chunk in read_file_in_chunks(in_file, file_size):
                    out.write(chunk)
        # add padding
        out.write(((int(math.ceil(file_size / 512.0) * 512) - file_size) * '\x00').encode('latin'))
    return True


def list_content(archive, verbose=False):
    """List the contents of an archive"""
    with open(archive, 'rb') as f:
        while True:
            tar_header = TarHeader()
            f.readinto(tar_header)
            name = tar_header.name
            if not name:
                break
            file_size = int(tar_header.size, 8)
            print('{:10} {}/{} {:12} {} {}{}'.format(
                permission_bits(tar_header.mode, tar_header.typeflag),
                int(tar_header.uid, 8),
                int(tar_header.gid, 8),
                file_size,
                datetime.datetime.fromtimestamp(int(tar_header.mtime, 8)),
                name.decode(SYSTEM_ENCODING) if PY3 else name,
                ' -> {}'.format(tar_header.linkname.strip()) if tar_header.linkname.strip() else ''
            ))
            f.read(file_size)
            padding_size = int(math.ceil(file_size / 512.0) * 512) - file_size
            f.read(padding_size)
    return True


def main():
    # prepare argument parser
    parser = argparse.ArgumentParser()
    act_group = parser.add_mutually_exclusive_group()
    act_group.add_argument('-a', '--add', dest='add', action='store_true', help='add file to the tar archive')
    act_group.add_argument('-c', '--create', dest='create', action='store_true', help='create a tar archive')
    act_group.add_argument('-t', '--list', dest='list', action='store_true', help='list the contents of an archive')
    act_group.add_argument('-x', '--extract', dest='extract', action='store_true', help='extract files from an archive')
    parser.add_argument('-f', '--file', dest='file', help='in/out tar file')
    parser.add_argument('-v', '--verbose', dest='verbose', help='verbose mode', action='store_true', default=False)
    parser.add_argument('file_or_dir', metavar='file/dir', help='file or directory to add/create/extract', nargs='?')
    args = parser.parse_args()

    any_action = any([args.add, args.create, args.list, args.extract])
    if not any_action or (any_action and not args.file) or ((args.add or args.create) and not args.file_or_dir):
        parser.print_help()
        exit(1)

    if (args.extract and not args.file_or_dir):
        args.file_or_dir = './out'

    if not os.path.isfile(args.file):
        exit('No such file: "{}"'.format(args.file))

    result = True
    if args.create:
        result = create(args.file, args.file_or_dir, verbose=args.verbose)
    elif args.add:
        result = add(args.file, args.file_or_dir, verbose=args.verbose)
    elif args.extract:
        result = extract(args.file, args.file_or_dir, verbose=args.verbose)
    elif args.list:
        result = list_content(args.file, verbose=args.verbose)

    # something went wrong
    if not result:
        exit(1)


if __name__ == '__main__':
    main()
