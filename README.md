tar
===

A tar archiving utility in Python

Usage:
------
The usage of `tar.py`:
```
usage: tar.py [-h] [-a | -c | -t | -x] [-f FILE] [-v] [file/dir]

positional arguments:
  file/dir              file or directory to add/create/extract

optional arguments:
  -h, --help            show this help message and exit
  -a, --add             add file to the tar archive
  -c, --create          create a tar archive
  -t, --list            list the contents of an archive
  -x, --extract         extract files from an archive
  -f FILE, --file FILE  in/out tar file
  -v, --verbose         verbose mode
```

Examples:
Create `out.tar` from `some_dir` directory:  
```tar.py -cvf out.tar some_dir```

Add `123.txt` file to `out.tar`:  
```tar.py -avf out.tar 123.txt```

List the contents of an `out.tar`:  
```tar.py -tvf out.tar```

Extract files from `out.tar` to `out_dir` directory:  
```tar.py -xvf out.tar out_dir```

License:
--------
Released under [The MIT License](https://github.com/delimitry/tar/blob/master/LICENSE).
