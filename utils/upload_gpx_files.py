#!/usr/bin/env python3
'''
Upload GPX files

Upload GPX files in a directory, or recursively, checking first if they
already exist on the server, and logging which files have been uploaded

Created on 2 Jul 2025

@author: simon
'''
import argparse
from collections import Counter
import logging
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse

from login_session import login_session, get_credentials
from upload_gpx import upload_gpx_file

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)



class GPXUploader:
    def __init__(self, args):
        self.args = args
        self.counts = Counter()

    def do_upload(self):
        with login_session(self.args.login_url, self.args.logout_url,
                           credentials=get_credentials('~/.credentials/bike')
                           ) as self.session:
            with sqlite3.Connection(self.args.db_filename) as self.db:
                self.create_uploaded_files_table()
                source = self.args.source
                if source.is_file():
                    self.check_upload_file(source)
                    return
                if self.args.recurse:
                    for root_dir, _dirnames, filenames in source.walk():
                        for filename in filenames:
                            file_path = root_dir / filename
                            if file_path.suffix == '.gpx':
                                self.check_upload_file(file_path)
                    return
                # a single directory without recursion
                for filename in source.glob('*.gpx'):
                    file_path = source / filename
                    if file_path.is_file():
                        self.check_upload_file(file_path)


    def create_uploaded_files_table(self):
        """ create the DB tables if they don't already exist """
        ddl = [
            """CREATE TABLE IF NOT EXISTS uploaded_files
            (host_server CHAR,
             filename CHAR)
            """,
            """ CREATE UNIQUE INDEX IF NOT EXISTS server_filename_index
            ON uploaded_files (host_server, filename) """
            ]
        for ddl_stmt in ddl:
            self.db.execute(ddl_stmt)

    def check_upload_file(self, source: Path):
        """ check the if the file has already been uploaded, by checking the DB
        and then checking if it exists on the server.  If not, upload it """
        if (not self.args.no_filename_filter
                and self.args.filename_filter.fullmatch(source.name)) is None:
            self.counts["filename didn't match filter"] += 1
            log.debug("didn't match filter: %r", source.name)
            return

        if self.track_is_logged_in_db(source):
            log.debug("track %s already uploaded according to DB", source)
            self.counts["already uploaded according to DB"] += 1
            return

        if self.test_track_exists(source):
            log.debug("track %s already uploaded according to server", source)
            self.record_track_uploaded(source)
            self.counts["already uploaded according to server"] += 1
            return

        if upload_gpx_file(self.session, self.args, source):
            log.info("Successfully uploaded %s", source)
            self.record_track_uploaded(source)
            self.counts["successfully uploaded"] += 1
        else:
            log.error("Failed to upload %s", source)
            self.counts["upload failed"] += 1

    def track_is_logged_in_db(self, source: Path) -> bool:
        """ check if the track is already logged in the DB """
        sql = """SELECT COUNT(1) FROM uploaded_files
                WHERE host_server = ? AND filename = ? """
        r = self.db.execute(sql,(self.args.target_server, source.name)
                            ).fetchone()[0]
        if r == 1:
            return True
        if r == 0:
            return False
        raise ValueError(f"Unexpected result from track_logged_in_db:  {r!r}")

    def test_track_exists(self, file: Path) -> bool:
        """ check if the track name is already uploaded to the server """
        response = self.session.head(f"{self.args.query_url}{file.name}")
        if response.status_code == 302:
            raise ValueError("Did login fail?  request redirected to "
                             f"{response.headers['Location']}")
        if response.status_code == 200:
            log.info("Track exists: size=%s", response.headers["Content-Length"])
            return True
        if response.status_code == 404:
            return False
        log.info("unexpected response=%s, status %d, reason#%s,\ncontent=%s,\nheaders=%s",
                 response.text, response.status_code, response.reason,
                 response.content, response.headers)
        raise ValueError(f"Unexpected response {response.status_code} from server")

    def record_track_uploaded(self, file: Path):
        """ log in the DB that the track has been uploaded """
        filename = file.name
        sql = """INSERT INTO uploaded_files (host_server, filename)
            VALUES(?, ?) """
        self.db.execute(sql, (self.args.target_server, filename))

def dir_or_file(arg: str) -> Path:
    """ check arg is an existing directory or gpx file """
    path = Path(arg)
    if not path.exists():
        raise argparse.ArgumentTypeError("file/directory not found")
    if path.is_file() and path.suffix.lower() != '.gpx':
        raise argparse.ArgumentTypeError("file type must be .gpx")
    return path


def re_pattern(arg:str) -> re.Pattern:
    try:
        return re.compile(arg)
    except re.PatternError as e:
        raise argparse.ArgumentTypeError(e)


def main():
    args = handle_args()
    uploader = GPXUploader(args)
    uploader.do_upload()
    print("Finished.", uploader.counts)


def handle_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=dir_or_file, help="file to upload, or a "
                        "directory containing files.  Only gpx files will be "
                        "uploaded")
    parser.add_argument("--recurse", "-r", action="store_true", help="recurse"
                        " into sub-directories (default: false)", default=False)
    parser.add_argument("--filename-filter", help="filter that filenames must "
                        "completely match to be uploaded, specified as a "
                        "regular expression. Default: %(default)",
                        type=re_pattern,
                        # 2019-05-30-09-30-15.gpx or 2019-05-30 09.05.15 Day.gpx
                        default=r"20(\d\d-){2}\d\d(( (\d\d.){2}\d\d Day)|"
                        r"(-(\d\d-){2}\d\d)).gpx")
    parser.add_argument("--no-filename-filter", action="store_true",
                        help="don't filter filenames")

    parser.add_argument(
        "--query_url", help="url to query if the track filename exists "
        "(default=%(default))",
        default="http://localhost:8000/routes/api/track?name=")
    parser.add_argument(
        "--login_path", help="the PATH only part of the path to login to server"
        " (the host name is assumed to be the same).   (default=%(default))",
        default="/accounts/login/")
    parser.add_argument(
        "--logout_path", help="the PATH only part of the logout url"
        " (the host name is assumed to be the same).  Default:%(default)",
        default="/routes/logout/")
    parser.add_argument(
        "--upload_path", help="the PATH only part of the upload url"
        " (the host name is assumed to be the same).  Default:%(default)",
        default="/routes/gpx/upload")
    parser.add_argument(
        "--db-filename", help="the filename of the db file that tracks which"
        " files have already been uploaded to the server.  Default:"
        " %(default)", default=Path(__file__).parent / 'gpx_upload_log.db')
    # add a few derived arguments: upload_path
    args = parser.parse_args()
    url = urlparse(args.query_url)._replace(query='')
    args.target_server = f"{url.hostname}:{url.port}"
    args.login_url = url._replace(path=args.login_path).geturl()
    args.upload_url = url._replace(path=args.upload_path).geturl()
    args.logout_url = url._replace(path=args.logout_path).geturl()
    return args


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    main()
