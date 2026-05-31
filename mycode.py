#!/bin/python3
import sys
from pyoe.db import create_empty_db
from pyoe.schema import dump_schema, parse_df, sync_schema
from pyoe.sync import sync_many, print_progress

db_path = sys.argv[1] if len(sys.argv) > 1 else "/var/db/test3/sports"
df_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/sports1.df"
dump_schema(db_path, df_path)

outputfile = open(df_path, "r")
print(outputfile.read())
