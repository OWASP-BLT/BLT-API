import sqlite3, glob
dbs = glob.glob('.wrangler/**/*.sqlite', recursive=True)
if dbs:
  print(dbs[0])
  for r in sqlite3.connect(dbs[0]).execute('PRAGMA table_info(users);'):
    print(r)
