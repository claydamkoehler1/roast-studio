import argparse
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.path.insert(0, str(Path(__file__).resolve().parent / '.deps'))
from roasting.server import serve

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Roast Studio')
    parser.add_argument('--port', type=int, default=8740)
    parser.add_argument('--database')
    args = parser.parse_args()
    serve(args.port, args.database)
