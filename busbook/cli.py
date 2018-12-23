import argparse
from datetime import datetime
from pathlib2 import Path
from zipfile import ZipFile

from busbook.gtfs import load_gtfs
from busbook.render import render

from transitfeed.loader import Loader


def main():
    argp = argparse.ArgumentParser(
        description='Generate an HTML bus book from a GTFS feed.')
    argp.add_argument('file', metavar='GTFS file', type=argparse.FileType('rb', 0))
    argp.add_argument(
        '--date', '-d',
        help="view service for a specific date (format: '2019-01-02', default: today)")
    argp.add_argument(
        '--output', '-o',
        default='./out',
        help='output directory (default: ./out)')
    args = argp.parse_args()

    gtfs = load_gtfs(args.file)
    print 'Loading complete.'

    if args.date is None:
        date = datetime.today()
    else:
        date = datetime.strptime(args.date, '%Y-%m-%d')
    render(gtfs, date=date, outdir=Path(args.output))


def load_gtfs(fd):
    l = Loader(zip=ZipFile(fd))
    return l.Load()

