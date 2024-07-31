import os
import pytest

from erelim import Database, Table, Column, ForeignKey


DB_PATH = "./tests/resources/test.db"


@pytest.fixture
def db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = Database(DB_PATH)
    return db


@pytest.fixture
def Author():
    class Author(Table):
        name = Column(str)
        age = Column(int)

    return Author


@pytest.fixture
def Book(Author):
    class Book(Table):
        title = Column(str)
        published = Column(bool)
        author = ForeignKey(Author)

    return Book


#########################################
@pytest.fixture
def Novel(Author):
    class Novel(Table):
        title = Column(str)
        published = Column(bool)
        year = Column(int)
        author = ForeignKey(Author)

    return Novel
