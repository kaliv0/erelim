import inspect


SQLITE_TYPE_MAP = {
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    bytes: "BLOB",
    bool: "INTEGER", # NB: actually recognizes "TRUE" and "FALSE" as aliases for 1 and 0
}


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


########################################


class Table:
    def __init__(self, **kwargs):
        # TODO: probably should be private
        self.data = {
            "id": None,  # TODO: don't hardcode 'id' -> support other PK's
            **kwargs,
        }

    def __getattribute__(self, key):
        data = super().__getattribute__("data")  # TODO: probably should be private
        if key in data:
            return data[key]
        return super().__getattribute__(key)

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if key in self.data:
            self.data[key] = value

    @classmethod
    def get_create_sql(cls):
        CREATE_TABLE_SQL = "CREATE TABLE IF NOT EXISTS {name} ({fields})"
        fields = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]

        for name, field in inspect.getmembers(cls):
            if isinstance(field, Column):
                fields.append(f"{name} {field.sql_type}")
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id INTEGER")
        return CREATE_TABLE_SQL.format(name=cls.__name__.lower(), fields=", ".join(fields))

    def get_insert_sql(self):
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
    def get_select_sql(cls, **kwargs):
        SELECT_WHERE_SQL = "SELECT {fields} FROM {name}{where_clause}"
        fields = ["id"]
        for name, field in inspect.getmembers(cls):
            if isinstance(field, Column):
                fields.append(name)
            elif isinstance(field, ForeignKey):
                fields.append(f"{name}_id")

        where_clause = " WHERE " + " AND ".join([f"{key} = ?" for key in kwargs]) if kwargs else ""

        sql = SELECT_WHERE_SQL.format(
            fields=", ".join(fields),
            name=cls.__name__.lower(),
            where_clause=where_clause,
        )
        params = list(kwargs.values())
        return sql, fields, params

    def get_update_sql(self):
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
    def get_delete_sql(cls, id_):
        DELETE_SQL = "DELETE FROM {name} WHERE id = ?"
        sql = DELETE_SQL.format(name=cls.__name__.lower())
        return sql, [id_]
