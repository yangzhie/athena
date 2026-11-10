"""Administrator-only provisioning for account-free lecturer access."""
import argparse
import os
from pathlib import Path

from ..env import load_dotenv
from .service import StudySpaces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['create-lecturer-invite'])
    parser.parse_args()
    load_dotenv()
    spaces = StudySpaces(Path(os.environ.get('ATHENA_DB', 'data/athena.db')))
    try:
        print(spaces.create_lecturer_invite())
    finally:
        spaces.close()


if __name__ == '__main__':
    main()
