import sqlite3


def test_create_db(db):
    assert isinstance(db.conn, sqlite3.Connection)
    assert db.tables == []


def test_define_tables(Author, Book):
    assert Author.name.type is str
    assert Book.author.table == Author

    assert Author.name.sql_type == "TEXT"
    assert Author.age.sql_type == "INTEGER"


def test_create_tables(db, Author, Book):
    db.create(Author)
    db.create(Book)

    assert (
        Author._get_create_sql()
        == "CREATE TABLE IF NOT EXISTS author (id INTEGER PRIMARY KEY AUTOINCREMENT, age INTEGER, name TEXT)"
    )
    assert (
        Book._get_create_sql()
        == "CREATE TABLE IF NOT EXISTS book (id INTEGER PRIMARY KEY AUTOINCREMENT, author_id INTEGER, published INTEGER, title TEXT)"
    )
    for table in ("author", "book"):
        assert table in db.tables


#######################################
def test_create_author_instance(db, Author):
    db.create(Author)
    john = Author(name="John Doe", age=35)

    assert john.name == "John Doe"
    assert john.age == 35
    assert john.id is None


def test_save_author_instances(db, Author):
    db.create(Author)

    john = Author(name="John Doe", age=23)
    db.save(john)
    assert john._get_insert_sql() == (
        "INSERT INTO author (age, name) VALUES (?, ?)",
        [23, "John Doe"],
    )
    assert john.id == 1

    man = Author(name="Man Harsh", age=28)
    db.save(man)
    assert man.id == 2

    vik = Author(name="Vik Star", age=43)
    db.save(vik)
    assert vik.id == 3

    jack = Author(name="Jack Ma", age=39)
    db.save(jack)
    assert jack.id == 4


def test_get_all_authors(db, Author):
    db.create(Author)
    john = Author(name="John Doe", age=23)
    vik = Author(name="Vik Star", age=43)
    db.save(john)
    db.save(vik)

    authors = db.get_all(Author)

    assert Author._get_select_all_sql() == (
        # "SELECT id, age, name FROM author",
        "SELECT * FROM author",
        ["id", "age", "name"],
    )
    assert len(authors) == 2
    assert type(authors[0]) is Author
    assert {a.age for a in authors} == {23, 43}
    assert {a.name for a in authors} == {"John Doe", "Vik Star"}


def test_get_author_by_id(db, Author):
    db.create(Author)
    roman = Author(name="John Doe", age=43)
    db.save(roman)

    # case_0 => valid record
    john_from_db = db.get_by_id(Author, 1)

    assert Author._get_select_where_sql(id=1) == (
        "SELECT id, age, name FROM author WHERE id = ?",
        ["id", "age", "name"],
        [1],
    )
    assert type(john_from_db) is Author
    assert john_from_db.age == 43
    assert john_from_db.name == "John Doe"
    assert john_from_db.id == 1

    # case_1 => non-existent record
    invalid_author = db.get_by_id(Author, 200)
    assert invalid_author is None


def test_get_book_by_id_with_nested_data(db, Author, Book):
    db.create(Author)
    db.create(Book)
    john = Author(name="John Doe", age=43)
    book = Book(title="Building an ORM", published=False, author=john)
    db.save(john)
    db.save(book)

    book_from_db = db.get_by_id(Book, id=1)
    assert book_from_db.title == "Building an ORM"
    assert book_from_db.author.name == "John Doe"
    assert book_from_db.author.id == 1


def test_get_book_filter(db, Author, Book):
    db.create(Author)
    db.create(Book)
    john = Author(name="John Doe", age=43)
    arash = Author(name="Arash Kun", age=50)
    book = Book(title="Building an ORM", published=False, author=john)
    book2 = Book(title="Scoring Goals", published=True, author=arash)
    db.save(john)
    db.save(arash)
    db.save(book)
    db.save(book2)

    # case_0 => valid records
    filtered_books = db.filter(Book, id=2, published=True)
    book_from_db = filtered_books[0]
    assert book_from_db.title == "Scoring Goals"
    assert book_from_db.author.name == "Arash Kun"
    assert book_from_db.author.id == 2

    # case_1 => non-existent records
    invalid_books = db.filter(Book, title="FizzBuzz")
    assert invalid_books == []

    # TODO: case_2 => raises exception if invalid columns are given


def test_get_book_filter_alternative(db, Author, Novel):
    db.create(Author)
    db.create(Novel)
    john = Author(name="John Doe", age=43)
    arash = Author(name="Arash Kun", age=50)
    book = Novel(title="Burnt Sushi", published=True, year=1907, author=john)
    book2 = Novel(title="Building an ORM", published=True, year=1907, author=john)
    book3 = Novel(title="Scoring Goals", published=True, year=1907, author=arash)
    book4 = Novel(title="Lunar", published=False, year=None, author=arash)
    db.save(john)
    db.save(arash)
    db.save(book)
    db.save(book2)
    db.save(book3)
    db.save(book4)

    # case_0 => valid records
    filtered_books = (
        db.get(Novel).where(published=True, year=1907).order_by("id", desc=True).limit(2).execute()
    )
    assert len(filtered_books) == 2

    book_from_db1 = filtered_books[0]
    assert book_from_db1.id == 3
    assert book_from_db1.title == "Scoring Goals"
    assert book_from_db1.year == 1907
    assert book_from_db1.published == 1  # TODO: transform 1 to True
    assert book_from_db1.author.name == "Arash Kun"
    assert book_from_db1.author.id == 2

    book_from_db2 = filtered_books[1]
    assert book_from_db2.id == 2
    assert book_from_db2.title == "Building an ORM"
    assert book_from_db2.year == 1907
    assert book_from_db2.published == 1
    assert book_from_db2.author.name == "John Doe"
    assert book_from_db2.author.id == 1

    # case_1 => non-existent records
    # invalid_books = db.filter(Book, title="FizzBuzz")
    # assert invalid_books == []


def test_get_all_books_nested_data(db, Author, Book):
    db.create(Author)
    db.create(Book)
    john = Author(name="John Doe", age=43)
    arash = Author(name="Arash Kun", age=50)
    book = Book(title="Building an ORM", published=False, author=john)
    book2 = Book(title="Scoring Goals", published=True, author=arash)
    db.save(john)
    db.save(arash)
    db.save(book)
    db.save(book2)

    books = db.get_all(Book)
    assert len(books) == 2
    assert books[1].author.name == "Arash Kun"


def test_update_author(db, Author):
    db.create(Author)
    john = Author(name="John Doe", age=23)
    db.save(john)

    john.age = 43
    john.name = "John Wick"
    db.update(john)

    john_from_db = db.get_by_id(Author, id=john.id)
    assert john_from_db.age == 43
    assert john_from_db.name == "John Wick"


def test_delete_author(db, Author):
    db.create(Author)
    john = Author(name="John Doe", age=23)
    db.save(john)

    db.delete(Author, id=1)
    assert db.get_by_id(Author, 1) is None
