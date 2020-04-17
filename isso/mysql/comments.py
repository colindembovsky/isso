# -*- encoding: utf-8 -*-

import time

from isso.utils import Bloomfilter
from isso.compat import buffer


class Comments:
    """Hopefully DB-independend SQL to store, modify and retrieve all
    comment-related actions.  Here's a short scheme overview:

        | tid (thread id) | id (comment id) | parent | ... | voters | remote_addr |
        +-----------------+-----------------+--------+-----+--------+-------------+
        | 1               | 1               | null   | ... | BLOB   | 127.0.0.0   |
        | 1               | 2               | 1      | ... | BLOB   | 127.0.0.0   |
        +-----------------+-----------------+--------+-----+--------+-------------+

    The tuple (tid, id) is unique and thus primary key.
    """

    fields = ['tid', 'id', 'parent', 'created', 'modified',
              'mode',  # status of the comment 1 = valid, 2 = pending,
                       # 4 = soft-deleted (cannot hard delete because of replies)
              'remote_addr', 'text', 'author', 'email', 'website',
              'likes', 'dislikes', 'voters', 'notification']

    def __init__(self, db):

        self.db = db
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                tid INT,
                id INT NOT NULL AUTO_INCREMENT,
                parent INT,
                created FLOAT NOT NULL,
                modified FLOAT,
                mode INT,
                remote_addr VARCHAR(250),
                text VARCHAR(10000),
                author VARCHAR(250),
                email VARCHAR(250),
                website VARCHAR(250),
                likes INT,
                dislikes INT,
                voters BLOB NOT NULL,
                notification INT,
                PRIMARY KEY (id),
                FOREIGN KEY (tid)
                    REFERENCES threads(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (parent)
                    REFERENCES comments(id)
            );
            """)

    def add(self, uri, c):
        """
        Add new comment to DB and return a mapping of :attribute:`fields` and
        database values.
        """

        if c.get("parent") is not None:
            ref = self.get(c["parent"])
            if ref.get("parent") is not None:
                c["parent"] = ref["parent"]

        self.db.execute([
            'INSERT INTO comments (',
            '    tid, parent,'
            '    created, modified, mode, remote_addr,',
            '    text, author, email, website, voters, notification)',
            'SELECT',
            '    threads.id, %s,',
            '    %s, %s, %s, %s,',
            '    %s, %s, %s, %s, %s, %s',
            'FROM threads WHERE threads.uri = %s;'], (
            c.get('parent'),
            c.get('created') or time.time(), None, c["mode"], c['remote_addr'],
            c['text'], c.get('author'), c.get('email'), c.get('website'), buffer(
                Bloomfilter(iterable=[c['remote_addr']]).array), c.get('notification'),
            uri)
        )

        return dict(zip(Comments.fields, self.db.execute(
            'SELECT *, MAX(c.id) FROM comments AS c INNER JOIN threads ON threads.uri = %s',
            (uri, )).fetchone()))

    def activate(self, id):
        """
        Activate comment id if pending.
        """
        self.db.execute([
            'UPDATE comments SET',
            '    mode=1',
            'WHERE id=%s AND mode=2'], (id, ))

    def is_previously_approved_author(self, email):
        """
        Search for previously activated comments with this author email.
        """

        # if the user has not entered email, email is None, in which case we can't check if they have previous comments
        if email is not None:
            # search for any activated comments within the last 6 months by email
            # this SQL should be one of the fastest ways of doing this check
            # https://stackoverflow.com/questions/18114458/fastest-way-to-determine-if-record-exists
            rv = self.db.execute([
                'SELECT CASE WHEN EXISTS(',
                '    select * from comments where email=%s and mode=1 and ',
                '    created > DATE_SUB(CURDATE(), INTERVAL 6 MONTH)',
                ') THEN 1 ELSE 0 END;'], (email,)).fetchone()
            return rv[0] == 1
        else:
            return False

    def unsubscribe(self, email, id):
        """
        Turn off email notifications for replies to this comment.
        """
        self.db.execute([
            'UPDATE comments SET',
            '    notification=0',
            'WHERE email=%s AND (id=%s OR parent=%s);'], (email, id, id))

    def update(self, id, data):
        """
        Update comment :param:`id` with values from :param:`data` and return
        updated comment.
        """
        self.db.execute([
            'UPDATE comments SET',
            ','.join(key + '=' + '%s' for key in data),
            'WHERE id=%s;'],
            list(data.values()) + [id])

        return self.get(id)

    def get(self, id):
        """
        Search for comment :param:`id` and return a mapping of :attr:`fields`
        and values.
        """
        rv = self.db.execute(
            'SELECT * FROM comments WHERE id=%s', (id, )).fetchone()
        if rv:
            return dict(zip(Comments.fields, rv))

        return None

    def count_modes(self):
        """
        Return comment mode counts for admin
        """
        comment_count = self.db.execute(
            'SELECT mode, COUNT(comments.id) FROM comments '
            'GROUP BY comments.mode').fetchall()
        return dict(comment_count)

    def fetchall(self, mode=5, after=0, parent='any', order_by='id',
                 limit=100, page=0, asc=1):
        """
        Return comments for admin with :param:`mode`.
        """
        fields_comments = ['tid', 'id', 'parent', 'created', 'modified',
                           'mode', 'remote_addr', 'text', 'author',
                           'email', 'website', 'likes', 'dislikes']
        fields_threads = ['uri', 'title']
        sql_comments_fields = ', '.join(['comments.' + f
                                         for f in fields_comments])
        sql_threads_fields = ', '.join(['threads.' + f
                                        for f in fields_threads])
        sql = ['SELECT ' + sql_comments_fields + ', ' + sql_threads_fields + ' '
               'FROM comments INNER JOIN threads '
               'ON comments.tid=threads.id '
               'WHERE comments.mode = %s ']
        sql_args = [mode]

        if parent != 'any':
            if parent is None:
                sql.append('AND comments.parent IS NULL')
            else:
                sql.append('AND comments.parent=%s')
                sql_args.append(parent)

        # custom sanitization
        if order_by not in ['id', 'created', 'modified', 'likes', 'dislikes', 'tid']:
            sql.append('ORDER BY ')
            sql.append("comments.created")
            if not asc:
                sql.append(' DESC')
        else:
            sql.append('ORDER BY ')
            sql.append('comments.' + order_by)
            if not asc:
                sql.append(' DESC')
            sql.append(", comments.created")

        if limit:
            sql.append('LIMIT %s,%s')
            sql_args.append(page * limit)
            sql_args.append(limit)

        rv = self.db.execute(sql, sql_args).fetchall()
        for item in rv:
            yield dict(zip(fields_comments + fields_threads, item))

    def fetch(self, uri, mode=5, after=0, parent='any',
              order_by='id', asc=1, limit=None):
        """
        Return comments for :param:`uri` with :param:`mode`.
        """
        sql = ['SELECT comments.* FROM comments INNER JOIN threads ON',
               '    threads.uri=%s AND comments.tid=threads.id AND (%s | comments.mode) = %s',
               '    AND comments.created > %s']

        sql_args = [uri, mode, mode, after]

        if parent != 'any':
            if parent is None:
                sql.append('AND comments.parent IS NULL')
            else:
                sql.append('AND comments.parent=?')
                sql_args.append(parent)

        # custom sanitization
        if order_by not in ['id', 'created', 'modified', 'likes', 'dislikes']:
            order_by = 'id'
        sql.append('ORDER BY ')
        sql.append(order_by)
        if not asc:
            sql.append(' DESC')

        if limit:
            sql.append('LIMIT ?')
            sql_args.append(limit)

        rv = self.db.execute(sql, sql_args).fetchall()
        for item in rv:
            yield dict(zip(Comments.fields, item))

    def _remove_stale(self):

        sql = ('DELETE FROM',
               '    comments',
               'WHERE',
               '    mode=4 AND id NOT IN (',
               '        SELECT',
               '            parent',
               '        FROM',
               '            comments',
               '        WHERE parent IS NOT NULL)')

        while self.db.execute(sql).rowcount:
            continue

    def delete(self, id):
        """
        Delete a comment. There are two distinctions: a comment is referenced
        by another valid comment's parent attribute or stand-a-lone. In this
        case the comment can't be removed without losing depending comments.
        Hence, delete removes all visible data such as text, author, email,
        website sets the mode field to 4.

        In the second case this comment can be safely removed without any side
        effects."""

        refs = self.db.execute(
            'SELECT * FROM comments WHERE parent=%s', (id, )).fetchone()

        if refs is None:
            self.db.execute('DELETE FROM comments WHERE id=%s', (id, ))
            self._remove_stale()
            return None

        self.db.execute('UPDATE comments SET text=%s WHERE id=%s', ('', id))
        self.db.execute('UPDATE comments SET mode=%s WHERE id=%s', (4, id))
        for field in ('author', 'website'):
            self.db.execute('UPDATE comments SET %s=%s WHERE id=%s', (field, None, id))

        self._remove_stale()
        return self.get(id)

    def vote(self, upvote, id, remote_addr):
        """+1 a given comment. Returns the new like count (may not change because
        the creater can't vote on his/her own comment and multiple votes from the
        same ip address are ignored as well)."""

        rv = self.db.execute(
            'SELECT likes, dislikes, voters FROM comments WHERE id=%s', (id, )) \
            .fetchone()

        if rv is None:
            return None

        likes, dislikes, voters = rv
        if likes + dislikes >= 142:
            return {'likes': likes, 'dislikes': dislikes}

        bf = Bloomfilter(bytearray(voters), likes + dislikes)
        if remote_addr in bf:
            return {'likes': likes, 'dislikes': dislikes}

        bf.add(remote_addr)
        self.db.execute([
            'UPDATE comments SET',
            '    likes = likes + 1,' if upvote else 'dislikes = dislikes + 1,',
            '    voters = %s'
            'WHERE id=%s;'], (buffer(bf.array), id))

        if upvote:
            return {'likes': likes + 1, 'dislikes': dislikes}
        return {'likes': likes, 'dislikes': dislikes + 1}

    def reply_count(self, url, mode=5, after=0):
        """
        Return comment count for main thread and all reply threads for one url.
        """

        sql = """
                SELECT
                    c.parent, count(*)
                FROM comments AS c
                    INNER JOIN threads AS t
                    ON t.uri=%s AND c.tid = t.id AND
                    (%s | c.mode = %s) AND
                  c.created > %s
               GROUP BY c.parent
               """

        return dict(self.db.execute(sql, [url, mode, mode, after]).fetchall())

    def count(self, *urls):
        """
        Return comment count for one ore more urls..
        """

        threads = dict(self.db.execute("""
            SELECT 
                t.uri, COUNT(c.id)
            FROM comments AS c
                LEFT OUTER JOIN threads AS t
                ON t.id = c.tid AND c.mode = 1
            GROUP BY t.uri
            """
        ).fetchall())

        return [threads.get(url, 0) for url in urls]

    def purge(self, delta):
        """
        Remove comments older than :param:`delta`.
        """
        self.db.execute([
            'DELETE FROM comments WHERE mode = 2 AND DATEDIFF(%s, created) > %s;'
        ], (time.time(), delta))
        self._remove_stale()
