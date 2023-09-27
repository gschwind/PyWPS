##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

import platform
from pathlib import Path
from typing import Union
from urllib.parse import urlparse
import os
import fcntl
import logging

LOGGER = logging.getLogger('PYWPS')

is_windows = platform.system() == 'Windows'


def uri_to_path(uri) -> str:
    p = urlparse(uri)
    path = p.path
    if is_windows:
        path = str(Path(path)).lstrip('\\')
    return path


class FileOpenGuard:
    """Open and Lock the file for exclusive read/write (binary)"""

    def __init__(self, path):
        self._file = os.open(path, os.O_RDWR | os.O_CREAT)

    def __enter__(self):
        fcntl.lockf(self._file, fcntl.LOCK_EX)
        return self._file

    def __exit__(self, exc_type, exc_val, exc_tb):
        fcntl.lockf(self._file, fcntl.LOCK_UN)

    def __del__(self):
        os.close(self._file)


def trim_directory_if_needed(dn, min_size, max_size, size):
    """Check if the size (dir_size) of stored data into the directory 'dir'
    plus size is greater than max_size, if this is the case trim data from the
    directory until the size of stored data goes below min_size. In any case
    update the dir_size cached to match the actual dir_size"""

    dir_size_tracker_file = os.path.join(dn, ".filestorage.pywps.txt")

    # # Ensure that the file dir_size_tracker_file exists
    # try:
    #     with FileOpenGuard(open(dir_size_tracker_file, "xb")) as f:
    #         f.seek(0, 0)
    #         f.truncate(0)
    #         f.write(str(0).encode("utf-8"))
    # except FileExistsError:
    #     pass

    # Lock the storage tracker file
    with FileOpenGuard(dir_size_tracker_file) as f:
        # Go to begining of the file
        os.lseek(f, 0, 0)
        # Read at most 4096 digit
        data = os.read(f, 4096)

        try:
            current_size = int(data.decode("utf-8"))
        except Exception:
            # Force trim to update the size value to accurate value
            current_size = max_size

        if current_size + size < max_size:
            # nothing to do other than updating dir_size
            LOGGER.debug(f"write new size: {current_size+size}")
            os.lseek(f, 0, 0)
            os.truncate(f, 0)
            os.write(f, str(current_size + size).encode("utf-8"))
            return

        # List files and there size
        lst = list()
        for root, dirs, files in os.walk(dn):
            for fx in files:
                fn = os.path.join(root, fx)
                if fn == dir_size_tracker_file:
                    continue
                st = os.stat(fn)
                lst.append((fn, st.st_size, st.st_mtime))

        # TODO: Check if reverse order is faster
        # Sort file by their last modification time
        lst.sort(key=lambda x: x[2])
        sz = 0
        while len(lst) > 0:
            if sz + lst[0][1] > min_size:
                break
            sz += lst.pop(0)[1]

        for fn, s, _ in lst:
            LOGGER.debug(f"unlink '{fn}' of {s} bytes")
            os.unlink(fn)

        # Write the new size
        LOGGER.debug(f"write new size: {sz+size}")
        os.lseek(f, 0, 0)
        os.truncate(f, 0)
        os.write(f, str(sz + size).encode("utf-8"))
