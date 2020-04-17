# -*- encoding: utf-8 -*-

import mysql.connector
from mysql.connector import Error
import logging
import operator
import os.path

from collections import defaultdict

logger = logging.getLogger("isso")

from isso.compat import buffer

from isso.db.comments import Comments
from isso.db.threads import Threads
from isso.db.spam import Guard
from isso.db.preferences import Preferences


class MySQL:
    """DB-dependend wrapper around MySQL.

    Register a trigger for automated orphan removal.
    """


    def __init__(self, conf):
        self.conf = conf
        self.mysql_host = conf.get('mysql', 'host')
        self.mysql_db = conf.get('mysql', 'db')
        self.mysql_username = conf.get('mysql', 'username')
        self.mysql_password = conf.get('mysql', 'password')

        self.preferences = Preferences(self)
        self.threads = Threads(self)
        self.comments = Comments(self)
        self.guard = Guard(self)

        try:
            self.connection = mysql.connector.connect(host=self.mysql_host,
                                                      database=self.mysql_db,
                                                      user=self.mysql_username,
                                                      password=self.mysql_password)

        except Error as e:
            print("Init error %d: %s" % (e.args[0], e.args[1]))
 
    def __execute(self, query, parameters=[]):
        if isinstance(query, (list, tuple)):
            query = ' '.join(query)

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, parameters)
            return cursor
        except Error as e:
            print("Execute error %d: %s" % (e.args[0], e.args[1]))
 
    def __select(self, query, parameters):
        return self.__execute(query, parameters)
   
    def execute(self, query, parameters=[]):
        return self.__execute(query, parameters)
 
    def fetchall(self, query, parameters=[]):
        cursor = self.__select(query, parameters)
        return cursor.fetchall()
   
    def fetchone(self, query, parameters=[]):
        cursor = self.__select(query, parameters)
        return cursor.fetchone()
   
    def dispose(self):
        if self.connection:
            self.connection.close()

    @property
    def version(self):
        return self.fetchone("SELECT VERSION()")[0]