# -*- encoding: utf-8 -*-


def Thread(id, uri, title):
    return {
        "id": id,
        "uri": uri,
        "title": title
    }


class Threads(object):

    def __init__(self, db):

        self.db = db
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id INT NOT NULL AUTO_INCREMENT, 
                uri VARCHAR(256) UNIQUE, 
                title VARCHAR(256),
                PRIMARY KEY (id)
            )
        """)

    def __contains__(self, uri):
        return self.db.fetchone("SELECT uri FROM threads WHERE uri=%s", (uri, )) is not None

    def __getitem__(self, uri):
        return Thread(*self.db.fetchone("SELECT * FROM threads WHERE uri=%s", (uri, )))

    def get(self, id):
        return Thread(*self.db.fetchone("SELECT * FROM threads WHERE id=%s", (id, )))

    def new(self, uri, title):
        self.db.commit(
            "INSERT INTO threads (uri, title) VALUES (%s, %s)", (uri, title))
        return self[uri]
