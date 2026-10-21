"""Server-side account initialization and consistent SQLite backups."""
import argparse
import os
import sys
from pathlib import Path
from .db import Database


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',default=os.environ.get('DATABASE_PATH','/data/study.db'))
    sub=parser.add_subparsers(dest='command',required=True)
    account=sub.add_parser('create-admin');account.add_argument('--username',default='admin')
    account.add_argument('--password-stdin',action='store_true',required=True)
    backup=sub.add_parser('backup');backup.add_argument('target')
    args=parser.parse_args();db=Database(args.db)
    if args.command=='create-admin':
        # Read a credential through stdin, never argv/environment or logs.
        password=sys.stdin.read().rstrip('\r\n')
        if db.user_by_name(args.username):
            print('Account already exists; existing credentials unchanged.');return
        db.create_user(args.username,password,'admin')
        print('Administrator account created.')
    elif args.command=='backup':
        db.backup(Path(args.target));print('Database backup saved.')

if __name__=='__main__':
    main()
