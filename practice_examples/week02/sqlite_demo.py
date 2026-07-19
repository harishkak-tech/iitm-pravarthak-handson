"""sqlite_demo.py — Week 2 practice: SQLite in five lines (a database that's a file).
    python practice_examples/week02/sqlite_demo.py
"""
import sqlite3

con = sqlite3.connect("practice_examples/week02/demo.db")   # a file appears on disk
con.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, note TEXT, cost REAL)")
con.execute("INSERT INTO runs (note, cost) VALUES (?, ?)", ("first run", 0.0003))
con.commit()
for row in con.execute("SELECT * FROM runs"):
    print(row)
