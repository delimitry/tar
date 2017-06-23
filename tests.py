#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
import os
import shutil
import sys
import tempfile
import unittest
from tar import *
from contextlib import contextmanager
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

locale.setlocale(locale.LC_ALL, '')
SYSTEM_ENCODING = locale.getlocale()[1]

PY3 = sys.version_info[0] == 3

@contextmanager
def captured_output():
    new_out = StringIO()
    old_out = sys.stdout
    try:
        sys.stdout = new_out
        yield sys.stdout
    finally:
        sys.stdout = old_out


class Tests(unittest.TestCase):
    """Test cases for functions"""

    def test_permission_bits(self):
        self.assertEqual(permission_bits('0', TAR_TYPE_REGULAR_FILE), '----------')
        self.assertEqual(permission_bits('0', TAR_TYPE_REGULAR_FILE_ALIAS), '----------')
        self.assertEqual(permission_bits('777', TAR_TYPE_DIR), 'drwxrwxrwx')
        self.assertEqual(permission_bits('111', TAR_TYPE_DIR), 'd--x--x--x')
        self.assertEqual(permission_bits('007', TAR_TYPE_SYMLINK), 'l------rwx')
        self.assertEqual(permission_bits('555', TAR_TYPE_HARDLINK), 'hr-xr-xr-x')

    def test_get_header_checksum(self):
        tar_header = TarHeader()
        self.assertEqual(get_header_checksum(tar_header), 0)
        tar_header = TarHeader()
        tar_header.chksum = (' ' * 8).encode('latin')  # 8 spaces before real checksum calculation
        self.assertEqual(get_header_checksum(tar_header), 256)
        tar_header = TarHeader()


class TestTar(unittest.TestCase):
    """Test cases for Tar"""

    @classmethod
    def setUpClass(cls):
        # create temporary directory and files
        cls.test_dir = tempfile.mkdtemp()
        cls.out_tar = os.path.join(cls.test_dir, 'out.tar')
        cls.in_file_1 = os.path.join(cls.test_dir, '123.txt')
        cls.in_dir_1 = os.path.join(cls.test_dir, 'some_dir')
        if not os.path.exists(cls.in_dir_1):
            os.mkdir(cls.in_dir_1)
        cls.data_1 = '123\r\naaa\r\nzzz'
        with open(cls.in_file_1, 'wb') as f:
            f.write(cls.data_1.encode('latin'))

    @classmethod
    def tearDownClass(cls):
        # move to root (to remove temp dir)
        os.chdir('/')
        # remove temporary directory and files
        shutil.rmtree(cls.test_dir)

    def test_create(self):
        self.assertEqual(create(self.out_tar, self.in_file_1, verbose=False), True)
        # in_file_2 = os.path.join(self.test_dir, 'äèö.txt').encode('utf-8').decode(SYSTEM_ENCODING) if PY3 else os.path.join(self.test_dir, 'äèö.txt')
        # with open(in_file_2, 'wb') as f:
        #     data = 'äèöê'
        #     f.write(data.encode('utf-8') if PY3 else data)
        # self.assertEqual(create(self.out_tar, in_file_2, verbose=False), True)
        #list_content(self.out_tar, verbose=False)

    def test_add(self):
        self.assertEqual(create(self.out_tar, self.in_file_1, verbose=False), True)
        self.assertEqual(add(self.out_tar, self.in_file_1, verbose=False), True)
        self.assertEqual(add(self.out_tar, self.in_file_1, verbose=False), True)
        self.assertEqual(add(self.out_tar, self.in_dir_1, verbose=False), True)
        # capture stdout and check
        with captured_output() as out:
            list_content(self.out_tar, verbose=False)
        lines = out.getvalue().strip().split('\n')
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0] == lines[1] == lines[2], True)
        self.assertEqual(lines[2] != lines[3], True)

    def test_content_list(self):
        # create and add files/dirs to archive
        self.assertEqual(create(self.out_tar, self.in_file_1, verbose=False), True)
        self.assertEqual(add(self.out_tar, self.in_dir_1, verbose=False), True)
        # capture stdout and check
        with captured_output() as out:
            list_content(self.out_tar, verbose=False)
        # check file output
        file_1_stat = os.stat(self.in_file_1)
        file_1_mode = '{:07o}'.format(file_1_stat.st_mode & 0o777).encode('latin')
        file_1_out_line = '{:10} {}/{} {:12} {} {}'.format(
            permission_bits(file_1_mode, TAR_TYPE_REGULAR_FILE), file_1_stat.st_uid, file_1_stat.st_gid,
            file_1_stat.st_size, datetime.datetime.fromtimestamp(int(file_1_stat.st_mtime)), self.in_file_1)
        self.assertEqual(out.getvalue().strip().split('\n')[0], file_1_out_line.strip())
        # check dir output
        dir_1_stat = os.stat(self.in_dir_1)
        dir_1_mode = '{:07o}'.format(dir_1_stat.st_mode & 0o777).encode('latin')
        dir_1_out_line = '{:10} {}/{} {:12} {} {}'.format(
            permission_bits(dir_1_mode, TAR_TYPE_DIR), dir_1_stat.st_uid, dir_1_stat.st_gid,
            0, datetime.datetime.fromtimestamp(int(dir_1_stat.st_mtime)), self.in_dir_1)
        self.assertEqual(out.getvalue().strip().split('\n')[1], dir_1_out_line.strip())

    def test_extract(self):
        # set the current working directory to "test_dir"
        os.chdir(self.test_dir)
        # create and add files/dirs to archive
        self.assertEqual(create(self.out_tar, os.path.relpath(self.in_file_1, self.test_dir), verbose=False), True)
        self.assertEqual(add(self.out_tar, os.path.relpath(self.in_dir_1, self.test_dir), verbose=False), True)
        # add one more file to "in_dir_1"
        in_file_2 = os.path.join(self.in_dir_1, 'other.txt')
        with open(in_file_2, 'wb') as f:
            data = '1234'
            f.write(data.encode('utf-8') if PY3 else data)
        self.assertEqual(add(self.out_tar, os.path.relpath(in_file_2, self.test_dir), verbose=False), True)
        # extract files
        out_dir = os.path.join(self.test_dir, 'out_dir')
        self.assertEqual(extract(self.out_tar, out_dir, verbose=False), True)
        self.assertIn('out_dir', os.listdir(self.test_dir))
        self.assertEqual(sorted(os.listdir(out_dir)), sorted(['123.txt', 'some_dir']))
        self.assertEqual(['other.txt'], os.listdir(os.path.join(out_dir, 'some_dir')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
