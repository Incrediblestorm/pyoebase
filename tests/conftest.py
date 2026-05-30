"""Top-level pytest configuration and shared fixtures."""

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DLC = os.environ.get("DLC", "/usr/dlc")
SPORTS2000_SRC = Path(DLC) / "sports2000"

# Sample .df content used across unit tests
SAMPLE_DF = """\
ADD TABLE "Customer"
  AREA "Data Area"
  LABEL "Customer"
  TABLE-TYPE T
  DUMP-NAME "customer"

ADD FIELD "CustNum" OF "Customer" AS integer
  FORMAT "9999999"
  INITIAL "0"
  LABEL "Cust Num"
  COLUMN-LABEL "Cust Num"
  ORDER 10
  POSITION 1

ADD FIELD "Name" OF "Customer" AS character
  FORMAT "x(30)"
  INITIAL ""
  LABEL "Name"
  ORDER 20
  POSITION 2
  MAX-WIDTH 60

ADD FIELD "Active" OF "Customer" AS logical
  FORMAT "yes/no"
  INITIAL "yes"
  ORDER 30
  POSITION 3

ADD INDEX "CustNum" ON "Customer"
  AREA "Index Area"
  PRIMARY
  UNIQUE
  ACTIVE
  INDEX-FIELD "CustNum" ASCENDING

ADD INDEX "CustName" ON "Customer"
  AREA "Index Area"
  ACTIVE
  INDEX-FIELD "Name" ASCENDING
  INDEX-FIELD "CustNum" ASCENDING

ADD TABLE "Order"
  AREA "Data Area"
  LABEL "Order"
  TABLE-TYPE T
  DUMP-NAME "order"

ADD FIELD "OrderNum" OF "Order" AS integer
  FORMAT ">>>>>>9"
  INITIAL "0"
  ORDER 10
  POSITION 1

ADD FIELD "CustNum" OF "Order" AS integer
  FORMAT "9999999"
  INITIAL "0"
  ORDER 20
  POSITION 2

ADD INDEX "OrderNum" ON "Order"
  AREA "Index Area"
  PRIMARY
  UNIQUE
  ACTIVE
  INDEX-FIELD "OrderNum" ASCENDING

ADD SEQUENCE "OrderSeq"
  INITIAL 1
  INCREMENT 1
  CYCLE-ON-LIMIT
"""

SAMPLE_DF_DELTA = """\
ADD TABLE "Invoice"
  AREA "Data Area"
  LABEL "Invoice"
  TABLE-TYPE T

ADD FIELD "InvoiceNum" OF "Invoice" AS integer
  FORMAT ">>>>>>9"
  INITIAL "0"
  ORDER 10
  POSITION 1

ADD INDEX "InvoiceNum" ON "Invoice"
  AREA "Index Area"
  PRIMARY
  UNIQUE
  ACTIVE
  INDEX-FIELD "InvoiceNum" ASCENDING

UPDATE FIELD "Name" OF "Customer" AS character
  FORMAT "x(50)"

DELETE TABLE "Order"
"""


@pytest.fixture
def sample_df_file(tmp_path):
    """Write SAMPLE_DF to a temp file and return its Path."""
    df = tmp_path / "sample.df"
    df.write_text(SAMPLE_DF)
    return df


@pytest.fixture
def sample_delta_file(tmp_path):
    df = tmp_path / "delta.df"
    df.write_text(SAMPLE_DF_DELTA)
    return df


@pytest.fixture
def empty_df_file(tmp_path):
    df = tmp_path / "empty.df"
    df.write_text("")
    return df
