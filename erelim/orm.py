import inspect
import sqlite3


SQLITE_TYPE_MAP = {
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bytes: "BLOB",
    bool: "INTEGER",
}


class Database:
    def __init__(self, path):
        self.conn = sqlite3.Connection(path)

    @property
    def tables(self):
        SELECT_TABLES_SQL = "SELECT name FROM sqlite_master WHERE type = 'table'"
        return [x[0] for x in self.conn.execute(SELECT_TABLES_SQL).fetchall()]  # FIXME

    def create(self, table):
        self.conn.execute(table._get_create_sql())

    def save(self, instance):
        sql, values = instance._get_insert_sql()
        cursor = self.conn.execute(sql, values)
        instance._data["id"] = cursor.lastrowid  # TODO: simplify
        instance.id = cursor.lastrowid
        self.conn.commit()

    def get_all(self, table):
        sql, fields = table._get_select_all_sql()
        return [
            self._build_instance(fields, row, table) for row in self.conn.execute(sql).fetchall()
        ]

    def get_by_id(self, table, id):
        sql, fields, params = table._get_select_where_sql(id=id)
        row = self.conn.execute(sql, params).fetchone()
        if row:
            return self._build_instance(fields, row, table)
        return None

    def filter(self, table, **kwargs):
        sql, fields, params = table._get_select_where_sql(**kwargs)
        rows = self.conn.execute(sql, params).fetchall()
        if rows:
            return [self._build_instance(fields, row, table) for row in rows]
        return []

    def update(self, instance):
        sql, values = instance._get_update_sql()
        self.conn.execute(sql, values)
        self.conn.commit()

    def delete(self, table, id):
        sql, params = table._get_delete_sql(id)
        self.conn.execute(sql, params)
        self.conn.commit()

    def get(self, table):
        return QueryObject(db=self, table=table)

    def _build_instance(self, fields, row, table):
        instance = table()
        for field, value in zip(fields, row):
            if field.endswith("_id"):
                field = field[:-3]
                fk = getattr(table, field)
                value = self.get_by_id(fk.table, id=value)
            elif (table_field := getattr(table, field, None)) and table_field.type is bool:
                value = value == 1
            setattr(instance, field, value)
        return instance


######################################
class Table:
    def __init__(self, **kwargs):
        self._data = {
            "id": None,  # TODO: don't hardcode 'id' -> support other PK's
            **kwargs,
        }

    def __getattribute__(self, key):
        _data = super().__getattribute__("_data")
        if key in _data:
            return _data[key]
        return super().__getattribute__(key)

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if key in self._data:
            self._data[key] = value

    @classmethod
    def _get_create_sql(cls):
        CREATE_TABLE_SQL = "CREATE TABLE IF NOT EXISTS {name} ({fields})"
        fields = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]

        for name, field in inspect.getmembers(cls):
            if isinstance(field, Column):
                fields.append(f"{name} {field.sql_type}")
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id INTEGER")
        return CREATE_TABLE_SQL.format(name=cls.__name__.lower(), fields=", ".join(fields))

    def _get_insert_sql(self):
        INSERT_SQL = "INSERT INTO {name} ({fields}) VALUES ({placeholders})"

        cls = self.__class__
        fields = []
        placeholders = []
        values = []
        for name, field in inspect.getmembers(self.__class__):
            if isinstance(field, Column):
                fields.append(name)
                values.append(getattr(self, name))
                placeholders.append("?")
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id")
                values.append(getattr(self, name).id)
                placeholders.append("?")

        sql = INSERT_SQL.format(
            name=cls.__name__.lower(),
            fields=", ".join(fields),
            placeholders=", ".join(placeholders),
        )
        return sql, values

    @classmethod
    def _get_select_where_sql(cls, **kwargs):
        SELECT_WHERE_SQL = "SELECT {fields} FROM {name}{where_clause}"
        fields = ["id"]
        for name, field in inspect.getmembers(cls):
            if isinstance(field, Column):
                fields.append(name)
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id")

        where_clause = ""
        if kwargs:
            where_clause = " WHERE " + " AND ".join([f"{key} = ?" for key in kwargs])

        sql = SELECT_WHERE_SQL.format(
            name=cls.__name__.lower(),
            fields=", ".join(fields),
            where_clause=where_clause,
        )
        params = list(kwargs.values())
        return sql, fields, params

    @classmethod
    def _get_select_all_sql(cls):
        SELECT_ALL_SQL = "SELECT * FROM {name}"
        fields = ["id"]
        for name, field in inspect.getmembers(cls):
            if isinstance(field, Column):
                fields.append(name)
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id")

        sql = SELECT_ALL_SQL.format(name=cls.__name__.lower())
        return sql, fields

    def _get_update_sql(self):
        UPDATE_SQL = "UPDATE {name} SET {fields} WHERE id = ?"

        cls = self.__class__
        fields = []
        values = []
        for name, field in inspect.getmembers(cls):
            if isinstance(field, Column):
                fields.append(name)
                values.append(getattr(self, name))
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id")
                values.append(getattr(self, name).id)
        values.append(getattr(self, "id"))

        sql = UPDATE_SQL.format(
            name=cls.__name__.lower(), fields=", ".join([f"{field} = ?" for field in fields])
        )
        return sql, values

    @classmethod
    def _get_delete_sql(cls, id):
        DELETE_SQL = "DELETE FROM {name} WHERE id = ?"
        sql = DELETE_SQL.format(name=cls.__name__.lower())
        return sql, [id]


########################################
class Column:
    def __init__(self, column_type):
        self.type = column_type

    @property
    def sql_type(self):
        return SQLITE_TYPE_MAP[self.type]


########################################
class ForeignKey:
    def __init__(self, table):
        self.table = table  # TODO: rename


#########################################
class QueryObject:
    def __init__(self, db, table):
        # pointer to db instance to make possible calling "execute" method on queryObject ???
        self.db = db
        self.table = table
        self.order_dir = " ASC"
        self.order_criteria = None
        self.filter_data = None
        self.limit_count = None

    def where(self, **kwargs):
        self.filter_data = kwargs
        return self

    def order_by(self, criteria, desc=False):
        self.order_criteria = criteria
        if desc:
            self.order_dir = " DESC"
        return self

    def limit(self, count=None):
        if count is not None:
            self.limit_count = count
        return self

    def execute(self):
        # similar db.filter
        sql, fields, params = self.table._get_select_where_sql(**self.filter_data)
        if self.order_criteria:
            sql += f" ORDER BY {self.order_criteria}"  # TODO: parametrize order_criteria -> bug in sqlite!?
            sql += self.order_dir
        if self.limit_count:
            sql += " LIMIT ?"
            params.append(self.limit_count)

        rows = self.db.conn.execute(sql, params).fetchall()
        if rows:
            return [self.db._build_instance(fields, row, self.table) for row in rows]
        return []
