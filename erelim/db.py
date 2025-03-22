import sqlite3
from contextlib import contextmanager


class Database:
    def __init__(self, path):
        self.path = path

    @property
    def tables(self):
        SELECT_TABLES_SQL = "SELECT name FROM sqlite_master WHERE type = 'table'"
        with self.dbconn() as c:
            return [x[0] for x in c.execute(SELECT_TABLES_SQL).fetchall()]  # FIXME

    def create(self, table):
        with self.dbconn() as c:
            c.execute(table.get_create_sql())

    def save(self, instance):
        sql, values = instance.get_insert_sql()
        with self.dbconn() as c:
            cursor = c.execute(sql, values)
            instance.data["id"] = cursor.lastrowid  # TODO: simplify
            instance.id = cursor.lastrowid

    def get_all(self, table):
        # sql, fields = table._get_select_all_sql()
        sql, fields, _ = table.get_select_sql()
        with self.dbconn() as c:
            return [self.build_instance(fields, row, table) for row in c.execute(sql).fetchall()]

    def get_by_id(self, table, id_):
        sql, fields, params = table.get_select_sql(id=id_)
        with self.dbconn() as c:
            row = c.execute(sql, params).fetchone()
        return self.build_instance(fields, row, table) if row else None

    def filter(self, table, **kwargs):
        sql, fields, params = table.get_select_sql(**kwargs)
        with self.dbconn() as c:
            rows = c.execute(sql, params).fetchall()
        return [self.build_instance(fields, row, table) for row in rows] if rows else []

    def update(self, instance):
        sql, values = instance.get_update_sql()
        with self.dbconn() as c:
            c.execute(sql, values)

    def delete(self, table, id_):
        sql, params = table.get_delete_sql(id_)
        with self.dbconn() as c:
            c.execute(sql, params)

    def get(self, table):
        return QueryObject(db=self, table=table)

    def execute(self, sql, params):
        with self.dbconn() as c:
            return c.execute(sql, params).fetchall()

    def build_instance(self, fields, row, table):
        instance = table()
        for field, value in zip(fields, row):
            if field.endswith("_id"):
                field = field[:-3]
                fk = getattr(table, field)
                value = self.get_by_id(fk.table, id_=value)
            elif (table_field := getattr(table, field, None)) and table_field.type is bool:
                value = value == 1
            setattr(instance, field, value)
        return instance

    @contextmanager
    def dbconn(self):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        try:
            yield cursor
        except sqlite3.IntegrityError as e:
            print('Unexpected error: ', e)
        else:
            conn.commit()
        finally:
            # cursor.close()  # it'll be closed when out of scope anyway
            conn.close()


#########################################
class QueryObject:
    def __init__(self, db, table):
        # pointer to db instance to make possible calling "execute" method on queryObject ???
        self._db = db
        self._table = table
        self._order_dir = " ASC"
        self._order_criteria = None
        self._filter_data = None
        self._limit_count = None

    def where(self, **kwargs):
        self._filter_data = kwargs
        return self

    def order_by(self, criteria, desc=False):
        self._order_criteria = criteria
        if desc:
            self._order_dir = " DESC"
        return self

    def limit(self, count=None):
        if count:
            self._limit_count = count
        return self

    def execute(self):
        sql, fields, params = self._table.get_select_sql(**self._filter_data)
        if self._order_criteria:
            sql += f" ORDER BY {self._order_criteria}"  # TODO: parametrize order_criteria
            sql += self._order_dir
        if self._limit_count:
            sql += " LIMIT ?"
            params.append(self._limit_count)

        rows = self._db.execute(sql, params)
        return [self._db.build_instance(fields, row, self._table) for row in rows] if rows else []
